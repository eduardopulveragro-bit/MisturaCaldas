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


_SYSTEM_PROMPT = """Você é um extrator de dados de ordens de pulverização agrícola brasileira.

TABELA DE ORDEM DE ADIÇÃO NA CALDA:
Pos | Sigla | Tipo                                               | Grupo
  1 | —     | Encher tanque com 70% de água                       | ÁGUA
  2 | —     | Adjuvantes Corretivos/Condicionadores (pH, quelat.) | ESPECIAIS
  3 | SG    | Granulado Solúvel                                   | SÓLIDOS
  4 | SP    | Pó Solúvel                                          | SÓLIDOS
  5 | WP    | Pó Molhável                                         | SÓLIDOS
  6 | WG    | Granulado Dispersível                               | SÓLIDOS
  7 | CS    | Suspensão de Encapsulado                            | SUSPENSÕES
  8 | SC    | Suspensão Concentrada                               | SUSPENSÕES
  9 | OD    | Dispersão de Óleo / Susp. Conc. em Óleo             | SUSPENSÕES
 10 | SE    | Suspo-Emulsão                                       | INTERMEDIÁRIO
 11 | EC    | Concentrado Emulsionável                            | EMULSÕES
 12 | —     | Adjuvantes em Óleo (óleo mineral/vegetal)            | EMULSÕES
 13 | EO    | Emulsão de Água em Óleo                             | EMULSÕES
 14 | EW    | Emulsão de Óleo em Água                             | EMULSÕES
 15 | ME    | Microemulsão                                        | EMULSÕES
 16 | SL    | Concentrado Solúvel                                 | ALTA SOLUBILIDADE
 17 | —     | Adjuvantes Surfactantes, Espalhantes, Estabiliz.    | ESPECIAIS
 18 | —     | Fertilizantes Foliares                              | ESPECIAIS
 19 | —     | Adjuvantes Redutores de Espuma                      | ESPECIAIS
 20 | —     | Terminar de encher tanque com água                   | ÁGUA

TAREFA: Extraia os produtos da mensagem. Retorne APENAS JSON válido.

Para CADA produto, extraia:
- produto: nome exato como aparece na mensagem
- dose: valor numérico
- unidade: L, mL, kg, g
- base: "ha" (por hectare) ou "L_calda" (por litro de calda)
- formulacao: a sigla da formulação (SG, SP, WP, WG, CS, SC, OD, SE, EC, EO, EW, ME, SL)

COMO DETERMINAR A FORMULAÇÃO:
1. Se o nome inclui a sigla (ex: "Score 250 EC"), use-a diretamente.
2. Se é um produto comercial conhecido, use a formulação da bula.
3. Se é um INGREDIENTE ATIVO sem nome comercial (ex: "mancozeb", "atrazina"):
   use a formulação MAIS COMUM para aquele ingrediente no Brasil.
   Exemplos: mancozeb → WP, glifosato → SL, atrazina → SC, 2,4-D → SL.
4. Se é um ADJUVANTE ou ÓLEO genérico, classifique pela natureza:
   - "adjuvante" genérico sem especificação → posição 17 (surfactante/espalhante)
   - "óleo" / "óleo mineral" / "óleo vegetal" / "óleo de laranja" → posição 12
   - "condicionador" / "corretor de pH" → posição 2
   - "espalhante" / "surfactante" → posição 17
   - "fertilizante foliar" / "aminoácidos" → posição 18
   - "antiespumante" → posição 19
5. Se realmente não sabe, use null — mas tente antes.

REGRAS:
- NÃO decida a ordem de adição — isso não é sua função.
- Se encontrar nome de pessoa, telefone, CPF ou fazenda identificável, retorne:
  {"erro": "dados_pessoais", "descricao": "dados pessoais detectados"}

ALERTAS (somente quando realmente ambíguo):
- "ambiguidade": unidade ambígua ("/ga" em vez de "/ha")
- "unidade_ausente": dose sem unidade
- "dose_estranha": dose improvável

FORMATO:
{
  "itens": [
    {"produto": "Nome", "dose": 2.5, "unidade": "L", "base": "ha", "formulacao": "SC"}
  ],
  "alertas": [
    {"tipo": "ambiguidade", "descricao": "descrição", "item": "produto"}
  ]
}"""

# Preços estimados claude-haiku-5-5 (USD por token)
_PRECO_INPUT_POR_TOKEN = 0.80 / 1_000_000
_PRECO_OUTPUT_POR_TOKEN = 4 / 1_000_000


def extrair_itens(mensagem: str, modelo: str = "claude-haiku-5-5") -> dict:
    """
    Chama a API Claude para extrair itens estruturados da mensagem.
    Loga tokens e custo estimado. Lança ValueError se encontrar dados pessoais.
    """
    cliente = _criar_cliente()
    inicio = datetime.now()

    resposta = cliente.messages.create(
        model=modelo,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": mensagem}],
    )
    duracao = (datetime.now() - inicio).total_seconds()

    tokens_in = resposta.usage.input_tokens
    tokens_out = resposta.usage.output_tokens
    custo_usd = tokens_in * _PRECO_INPUT_POR_TOKEN + tokens_out * _PRECO_OUTPUT_POR_TOKEN

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

    # Remove cercas de markdown (```json ... ```)
    if texto.startswith("```"):
        linhas = texto.split("\n")
        linhas = [l for l in linhas if not l.strip().startswith("```")]
        texto = "\n".join(linhas).strip()

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ValueError(f"API retornou JSON inválido: {e}\nTexto recebido: {texto[:300]}")

    if dados.get("erro") == "dados_pessoais":
        raise ValueError(f"STOP: {dados['descricao']}")

    dados.setdefault("itens", [])
    dados.setdefault("alertas", [])
    return dados
