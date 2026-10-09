"""
Integração WhatsApp via Z-API — recebe mensagens do grupo,
detecta @menção ao bot, processa a ordem e responde.
"""
import logging
import os
import re

import requests

from src.parser import extrair_itens
from src.ordenacao import ordenar_itens
from src.operacao import extrair_operacao, calcular_totais_tanque

logger = logging.getLogger(__name__)


def _parse_webhook(payload: dict) -> dict:
    return {
        "is_group": payload.get("isGroupMsg", False),
        "chat_id": payload.get("chatId", ""),
        "chat_name": payload.get("chatName", ""),
        "sender_name": payload.get("senderName", ""),
        "message": (payload.get("body") or "").strip(),
        "mentioned": payload.get("listMention") or [],
    }


def _bot_mencionado(info: dict) -> bool:
    bot_phone = os.environ.get("WHATSAPP_BOT_PHONE", "")
    if not bot_phone:
        return False
    for m in info.get("mentioned", []):
        if bot_phone in m:
            return True
    return f"@{bot_phone}" in info.get("message", "")


def _limpar_mensagem(texto: str) -> str:
    texto = re.sub(r"@\d{10,15}", "", texto)
    texto = re.sub(r"@\S+", "", texto, count=1)
    return texto.strip()


def _formatar_resposta(itens: list[dict], alertas: list[dict], operacao: dict | None = None) -> str:
    linhas = ["*Ordem de Mistura Corrigida*"]

    if operacao:
        partes = []
        if operacao.get("area_tanque_ha"):
            partes.append(f"Tanque: {operacao['area_tanque_ha']:.0f} ha")
        if operacao.get("vazao_L_ha"):
            partes.append(f"Vazao: {operacao['vazao_L_ha']:.0f} L/ha")
        if operacao.get("ponta"):
            partes.append(f"Ponta: {operacao['ponta']}")
        if operacao.get("pressao_bar"):
            partes.append(f"Pressao: {operacao['pressao_bar']} bar")
        if operacao.get("tipo_gota"):
            partes.append(f"Gota: {operacao['tipo_gota']}")
        if partes:
            linhas.append(f"_{' | '.join(partes)}_")

    linhas.append("")
    tem_totais = any(item.get("total_tanque") for item in itens)

    for i, item in enumerate(itens, 1):
        nome = item["produto"]
        form = item.get("formulacao") or ""
        dose = item.get("dose", "")
        unidade = item.get("unidade", "")

        dose_str = f" — {dose} {unidade}/ha" if dose else ""
        form_str = f" ({form})" if form and form != "DESCONHECIDA" else ""

        linha = f"{i}. *{nome}*{form_str}{dose_str}"

        if tem_totais and item.get("total_tanque"):
            linha += f" = *{item['total_tanque']} {item.get('total_unidade', '')}*"

        if item.get("alerta_prediluicao"):
            linha += f"\n    _>> {item['alerta_prediluicao']}_"

        if item.get("alerta_pendente"):
            linha += f"\n    _>> {item['alerta_pendente']}_"

        linhas.append(linha)

    if alertas:
        linhas.append("\n*Alertas:*")
        for a in alertas:
            desc = a.get("descricao", "")
            produto = a.get("item", "")
            linhas.append(f"- {desc}" + (f" ({produto})" if produto else ""))

    linhas.append("\n_Sugestao do sistema. Requer aprovacao do RT._")
    return "\n".join(linhas)


def _enviar_mensagem(chat_id: str, mensagem: str) -> bool:
    instance = os.environ.get("ZAPI_INSTANCE_ID", "")
    token = os.environ.get("ZAPI_TOKEN", "")
    client_token = os.environ.get("ZAPI_CLIENT_TOKEN", "")

    if not instance or not token:
        logger.error("ZAPI_INSTANCE_ID ou ZAPI_TOKEN nao configurados")
        return False

    url = f"https://api.z-api.io/instances/{instance}/token/{token}/send-text"
    headers = {"Client-Token": client_token} if client_token else {}

    try:
        resp = requests.post(
            url,
            json={"phone": chat_id, "message": mensagem},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Mensagem enviada para %s", chat_id)
        return True
    except Exception as e:
        logger.error("Erro ao enviar mensagem: %s", e)
        return False


def processar_webhook(payload: dict) -> dict:
    """Pipeline completo: webhook -> deteccao -> parser IA -> ordenacao -> resposta."""
    info = _parse_webhook(payload)

    if not _bot_mencionado(info):
        return {"status": "ignorado", "motivo": "bot nao mencionado"}

    texto = _limpar_mensagem(info["message"])
    if not texto:
        return {"status": "ignorado", "motivo": "mensagem vazia"}

    logger.info(
        "Processando ordem de %s no grupo %s",
        info["sender_name"],
        info["chat_name"],
    )

    try:
        dados = extrair_itens(texto)
    except EnvironmentError:
        _enviar_mensagem(info["chat_id"], "Chave da API nao configurada. Contate o administrador.")
        return {"status": "erro", "motivo": "api_key"}
    except ValueError as e:
        _enviar_mensagem(info["chat_id"], f"Erro ao processar: {e}")
        return {"status": "erro", "motivo": str(e)}

    itens = dados.get("itens", [])
    alertas = dados.get("alertas", [])

    if not itens:
        _enviar_mensagem(
            info["chat_id"],
            "Nao encontrei produtos na mensagem. Envie a lista com doses (ex: Roundup 2L/ha, Score 0,5L/ha).",
        )
        return {"status": "sem_itens"}

    itens_ordenados = ordenar_itens(itens)

    operacao = extrair_operacao(texto)
    area = operacao.get("area_tanque_ha")
    if area:
        calcular_totais_tanque(itens_ordenados, area)

    resposta = _formatar_resposta(itens_ordenados, alertas, operacao or None)
    _enviar_mensagem(info["chat_id"], resposta)

    return {"status": "ok", "produtos": len(itens_ordenados)}
