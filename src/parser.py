"""
Extração de itens da mensagem via API Claude.
Único ponto de contato com IA. A ordem NÃO é definida aqui.
"""
import json
import logging
import os
from datetime import datetime

import anthropic

logger = logging.getLogger(__name__)

def _criar_cliente() -> anthropic.Anthropic:
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise EnvironmentError("ANTHROPIC_API_KEY não definida")
    headers = {}
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if workspace:
        headers["anthropic-workspace-id"] = workspace
    return anthropic.Anthropic(api_key=chave, default_headers=headers)


_SYSTEM_PROMPT = """Extraia produtos de uma mensagem de pulverização agrícola. Retorne APENAS JSON.

Para CADA produto extraia:
- produto: nome exato como aparece na mensagem
- dose: valor numérico (null se ausente)
- unidade: L, mL, kg, g (null se ausente)
- base: "ha" ou "L_calda" (null se ausente)
- formulacao: sigla se aparecer no nome (ex: "Score 250 EC" → "EC"), senão null

REGRAS:
- Extraia o nome do produto como escrito, sem corrigir.
- Se a dose usa vírgula como decimal (ex: "0,5 L"), converta para ponto: 0.5
- Se encontrar nome de pessoa, telefone, CPF ou fazenda, retorne:
  {"erro": "dados_pessoais", "descricao": "dados pessoais detectados"}

FORMATO:
{"itens": [{"produto": "Nome", "dose": 2.5, "unidade": "L", "base": "ha", "formulacao": "EC"}], "alertas": []}

Alertas só quando ambíguo: "unidade_ausente", "dose_estranha"."""

_PRECOS_POR_MODELO = {
    "claude-haiku-5-5": (1.0 / 1_000_000, 5.0 / 1_000_000),
}
_PRECO_FALLBACK = (1.0 / 1_000_000, 5.0 / 1_000_000)


def _limpar_markdown(texto: str) -> str:
    """Remove apenas a primeira e última cerca de markdown."""
    linhas = texto.split("\n")
    if linhas and linhas[0].strip().startswith("```"):
        linhas = linhas[1:]
    if linhas and linhas[-1].strip().startswith("```"):
        linhas = linhas[:-1]
    return "\n".join(linhas).strip()


def extrair_itens(mensagem: str, modelo: str = "claude-haiku-5-5") -> dict:
    """
    Chama a API Claude para extrair itens estruturados da mensagem.
    Loga tokens e custo estimado. Lança ValueError se encontrar dados pessoais.
    """
    cliente = _criar_cliente()
    inicio = datetime.now()

    resposta = cliente.messages.create(
        model=modelo,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": mensagem}],
    )
    duracao = (datetime.now() - inicio).total_seconds()

    tokens_in = resposta.usage.input_tokens
    tokens_out = resposta.usage.output_tokens
    preco_in, preco_out = _PRECOS_POR_MODELO.get(modelo, _PRECO_FALLBACK)
    custo_usd = tokens_in * preco_in + tokens_out * preco_out

    logger.info(
        "chamada_api id=%s modelo=%s tokens_in=%d tokens_out=%d custo_usd=%.6f duracao_s=%.2f",
        resposta.id,
        modelo,
        tokens_in,
        tokens_out,
        custo_usd,
        duracao,
    )

    texto = ""
    for bloco in resposta.content:
        if bloco.type == "text":
            texto = bloco.text.strip()
            break
    if not texto:
        raise ValueError("API não retornou texto na resposta")

    texto = _limpar_markdown(texto)

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ValueError(f"API retornou JSON inválido: {e}\nTexto recebido: {texto[:300]}")

    if dados.get("erro") == "dados_pessoais":
        raise ValueError(f"STOP: {dados['descricao']}")

    dados.setdefault("itens", [])
    dados.setdefault("alertas", [])
    return dados
