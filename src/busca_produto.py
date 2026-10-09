"""
Busca informações de produtos não cadastrados via IA e salva em produtos.csv.
Usa o conhecimento do modelo sobre bulas e registros MAPA.
Resultado fica marcado como "pendente confirmação" até o agrônomo validar.
"""
import csv
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

_PROMPT_BUSCA = """Você é um especialista em defensivos agrícolas registrados no Brasil (MAPA/Agrofit).

TABELA DE ORDEM DE ADIÇÃO NA CALDA (fonte: Spray Tech):
Pos. | Código | Descrição                                          | Grupo
  1  | —      | Encher o tanque com 70% de água                    | ÁGUA
  2  | —      | Adjuvantes Corretivos/Condicionadores (pH, quelat.) | ESPECIAIS
  3  | SG     | Granulado Solúvel                                  | SÓLIDOS
  4  | SP     | Pó Solúvel                                         | SÓLIDOS
  5  | WP     | Pó Molhável                                        | SÓLIDOS
  6  | WG     | Granulado Dispersível                              | SÓLIDOS
  7  | CS     | Suspensão de Encapsulado                           | SUSPENSÕES
  8  | SC     | Suspensão Concentrada                              | SUSPENSÕES
  9  | OD     | Dispersão de Óleo / Susp. Conc. em Óleo            | SUSPENSÕES
 10  | SE     | Suspo-Emulsão                                      | INTERMEDIÁRIO
 11  | EC     | Concentrado Emulsionável                           | EMULSÕES
 12  | —      | Adjuvantes em Óleo (óleo mineral/vegetal)           | EMULSÕES
 13  | EO     | Emulsão de Água em Óleo                            | EMULSÕES
 14  | EW     | Emulsão de Óleo em Água                            | EMULSÕES
 15  | ME     | Microemulsão                                       | EMULSÕES
 16  | SL     | Concentrado Solúvel                                | ALTA SOLUBILIDADE
 17  | —      | Adjuvantes Surfactantes, Espalhantes, Estabiliz.   | ESPECIAIS
 18  | —      | Fertilizantes Foliares                             | ESPECIAIS
 19  | —      | Adjuvantes Redutores de Espuma                     | ESPECIAIS
 20  | —      | Terminar de encher o tanque com água                | ÁGUA

SUA TAREFA: Dado o nome de um produto agrícola, identifique a formulação e posição na tabela.

O nome pode ser:
- Um PRODUTO COMERCIAL (ex: "Score", "Engeo Pleno S") → busque a formulação da bula
- Um INGREDIENTE ATIVO genérico (ex: "mancozeb", "atrazina") → use a formulação MAIS COMUM
  no Brasil. Exemplos: mancozeb → WP (pos 5), glifosato → SL (pos 16), atrazina → SC (pos 8)
- Um ADJUVANTE ou ÓLEO genérico → classifique pela natureza:
  "adjuvante" genérico → posicao 17 (surfactante/espalhante é o mais comum)
  "óleo" / "óleo mineral" / "óleo vegetal" / "óleo de laranja" → posicao 12
  "condicionador de pH" / "quelatizante" → posicao 2
  "espalhante" / "surfactante" → posicao 17
  "fertilizante foliar" / "aminoácido" → posicao 18
  "antiespumante" → posicao 19

REGRAS:
- Retorne APENAS JSON válido.
- Use seu conhecimento de bulas e registros MAPA.
- Para ingredientes ativos genéricos, use a formulação MAIS COMUM no mercado brasileiro.
- Para adjuvantes genéricos, use a posição pela natureza do produto.
- Retorne {"encontrado": false} SOMENTE se realmente não consegue determinar a formulação.

FORMATO para defensivos:
{
  "encontrado": true,
  "nome_completo": "Score 250 EC",
  "formulacao": "EC",
  "posicao": 11,
  "registro_mapa": "número ou null",
  "ingrediente_ativo": "difenoconazol",
  "tipo_adjuvante": null
}

FORMATO para adjuvantes:
{
  "encontrado": true,
  "nome_completo": "Nimbus",
  "formulacao": "EC",
  "posicao": 12,
  "registro_mapa": null,
  "ingrediente_ativo": "óleo mineral",
  "tipo_adjuvante": "óleo mineral"
}"""


def buscar_produto_ia(nome: str) -> dict | None:
    """
    Consulta a IA sobre um produto não cadastrado.
    Retorna dict com dados do produto ou None se não encontrado.
    """
    from src.parser import _criar_cliente
    try:
        cliente = _criar_cliente()
    except EnvironmentError:
        return None

    try:
        resposta = cliente.messages.create(
            model="claude-haiku-5-5",
            max_tokens=512,
            system=_PROMPT_BUSCA,
            messages=[{"role": "user", "content": f"Produto: {nome}"}],
        )
    except Exception as e:
        logger.error("Erro ao buscar produto '%s': %s", nome, e)
        return None

    tokens_in = resposta.usage.input_tokens
    tokens_out = resposta.usage.output_tokens
    logger.info("busca_produto nome='%s' tokens_in=%d tokens_out=%d", nome, tokens_in, tokens_out)

    texto = ""
    for bloco in resposta.content:
        if bloco.type == "text":
            texto = bloco.text.strip()
            break

    if texto.startswith("```"):
        linhas = texto.split("\n")
        linhas = [l for l in linhas if not l.strip().startswith("```")]
        texto = "\n".join(linhas).strip()

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return None

    if not dados.get("encontrado"):
        return None

    return dados


def salvar_produto(nome_original: str, dados_ia: dict) -> dict:
    """
    Salva produto encontrado pela IA em produtos.csv.
    Retorna o dict do produto salvo (com posicao).
    """
    from src.ordenacao import _FORMULACAO_PARA_POSICAO

    formulacao = (dados_ia.get("formulacao") or "").upper()
    posicao_ia = dados_ia.get("posicao")

    # Usa posição retornada pela IA (que já cruzou bula × tabela)
    # Fallback: mapa formulação → posição
    if posicao_ia and isinstance(posicao_ia, int) and 1 <= posicao_ia <= 20:
        posicao = posicao_ia
    else:
        posicao = _FORMULACAO_PARA_POSICAO.get(formulacao, 999)

    registro = dados_ia.get("registro_mapa") or ""
    nome_completo = dados_ia.get("nome_completo", nome_original)
    ingrediente = dados_ia.get("ingrediente_ativo", "")
    hoje = datetime.now().strftime("%Y-%m-%d")

    produto = {
        "nome": nome_completo,
        "nomes_alternativos": nome_original if nome_original.lower() != nome_completo.lower() else "",
        "registro_mapa": registro,
        "formulacao": formulacao,
        "posicao": str(posicao),
        "fonte": f"consulta_ia (ingrediente: {ingrediente}) — pendente confirmação",
        "data_conferencia": f"pendente ({hoje})",
        "principio_ativo": ingrediente,
    }

    caminho = DATA_DIR / "produtos.csv"
    try:
        with open(caminho, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["nome", "nomes_alternativos", "registro_mapa",
                                                    "formulacao", "posicao", "fonte", "data_conferencia",
                                                    "principio_ativo"])
            writer.writerow(produto)
        logger.info("Produto salvo: %s (%s, posicao %d)", nome_completo, formulacao, posicao)
    except OSError:
        logger.warning("Filesystem read-only — produto '%s' nao persistido", nome_completo)
    return produto
