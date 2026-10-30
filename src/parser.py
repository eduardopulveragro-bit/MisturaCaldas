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
- produto: SOMENTE o nome comercial, SEM dose, SEM unidade, SEM "/ha". Ex: "Glifosato 2 l/ha" → produto="Glifosato". Ex: "Score 250 EC 0,5 L" → produto="Score 250 EC"
- dose: valor numérico (null se ausente)
- unidade: L, mL, kg, g (null se ausente)
- base: "ha" (por hectare), "L_calda" (por litro de calda), "tanque" (dose total por carga/tanque), null se omitido
- formulacao: sigla se aparecer no nome (ex: "Score 250 EC" → "EC"), senão null

REGRAS:
- produto: APENAS o nome, nunca dose ou unidade junto.
- Use base="tanque" quando a mensagem indicar "por tanque", "por carga", "por tq", "carga cheia" ou similar.
- Se não houver indicação de base (ex: "Drive 2.5 L"), use base=null — não assuma.
- Dose com vírgula decimal (ex: "0,5 L") → converta para ponto: 0.5
- Se encontrar nome de pessoa, telefone, CPF ou fazenda: {"erro":"dados_pessoais","descricao":"dados pessoais detectados"}

FORMATO:
{"itens":[{"produto":"Nome","dose":2.5,"unidade":"L","base":"ha","formulacao":"EC"}],"alertas":[]}

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
        system=[{
            "type": "text",
            "text": _SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
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
    for item in dados["itens"]:
        if not item.get("base"):
            item["base"] = "ha"
    return dados
