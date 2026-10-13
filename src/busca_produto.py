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

from src.parser import _limpar_markdown, _PRECOS_POR_MODELO, _PRECO_FALLBACK
from src.ordenacao import _FORMULACAO_PARA_POSICAO, _FORM_ESPECIAL_POSICAO

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

_PROMPT_BUSCA = """Você é um consultor de registro de defensivos agrícolas no Brasil (MAPA/Agrofit).

TAREFA: Dado o nome de um produto, identifique com precisão sua CLASSE, FORMULAÇÃO e POSIÇÃO na tabela de ordem de adição na calda.

═══════════════════════════════════════════════════════════════
ETAPAS OBRIGATÓRIAS — siga TODAS na ordem, sem pular nenhuma:
═══════════════════════════════════════════════════════════════

ETAPA 1 — CLASSIFICAR O PRODUTO:
Primeiro determine a CLASSE do produto. As classes possíveis são:
  - herbicida, fungicida, inseticida, acaricida, nematicida, regulador (= DEFENSIVO)
  - adjuvante, óleo mineral, óleo vegetal, condicionador, espalhante, surfactante (= ADJUVANTE)
  - fertilizante foliar, aminoácido, bioestimulante (= FERTILIZANTE)

⚠️  ATENÇÃO: A MAIORIA dos produtos agrícolas são DEFENSIVOS (herbicidas, fungicidas, inseticidas).
    NÃO assuma que um produto é adjuvante só porque o nome parece genérico.
    Exemplos de DEFENSIVOS que podem parecer adjuvantes:
    - Zethamaxx Evo → herbicida SE (s-metolacloro+flumioxazina+imazetapir)
    - Dual Gold → herbicida EC (s-metolacloro)
    - Permit → herbicida WG (halosulfurom)
    - Verdict → herbicida EC (haloxifop)
    SÓ classifique como adjuvante se tiver CERTEZA de que o produto NÃO possui ingrediente ativo defensivo.

ETAPA 2 — BUSCAR FORMULAÇÃO NA BULA:
Para DEFENSIVOS: A formulação vem da BULA do produto registrado no MAPA.
  - Muitos produtos trazem a sigla no nome: "Score 250 EC" → EC, "Heat 70 WG" → WG
  - Se a sigla não está no nome, busque na bula pelo tipo físico da formulação
  - As siglas válidas são: SG, SP, WP, WG, CS, SC, OD, SE, EC, EO, EW, ME, SL
  - NUNCA invente uma formulação. Se não sabe, retorne {"encontrado": false}

Para ADJUVANTES genéricos (sem formulação de bula):
  - Óleo mineral/vegetal → use "OLEO"
  - Condicionador/corretor de pH → use "ADJUVANTE"
  - Surfactante/espalhante → use "ADJUVANTE"
  - Antiespumante → use "ADJUVANTE"

Para FERTILIZANTES FOLIARES: use "FERTILIZANTE"

ETAPA 3 — DETERMINAR POSIÇÃO na tabela:
A posição é determinada pela FORMULAÇÃO, usando esta tabela:

Pos | Sigla | Tipo                                               | Uso
  2 | —     | Adjuvantes Corretivos/Condicionadores               | SÓ adjuvantes pH/quelat.
  3 | SG    | Granulado Solúvel                                   | defensivos SG
  4 | SP    | Pó Solúvel                                          | defensivos SP
  5 | WP    | Pó Molhável                                         | defensivos WP
  6 | WG    | Granulado Dispersível                               | defensivos WG
  7 | CS    | Suspensão de Encapsulado                            | defensivos CS
  8 | SC    | Suspensão Concentrada                               | defensivos SC
  9 | OD    | Dispersão de Óleo                                   | defensivos OD
 10 | SE    | Suspo-Emulsão                                       | defensivos SE
 11 | EC    | Concentrado Emulsionável                            | defensivos EC
 12 | —     | Óleos (mineral/vegetal)                              | SÓ adjuvantes óleo
 13 | EO    | Emulsão de Água em Óleo                             | defensivos EO
 14 | EW    | Emulsão de Óleo em Água                             | defensivos EW
 15 | ME    | Microemulsão                                        | defensivos ME
 16 | SL    | Concentrado Solúvel                                 | defensivos SL
 17 | —     | Surfactantes/Espalhantes/Estabilizantes              | SÓ adjuvantes
 18 | —     | Fertilizantes Foliares                              | SÓ fertilizantes
 19 | —     | Redutores de Espuma                                 | SÓ antiespumantes

REGRA: Posições 2, 12, 17, 18, 19 são EXCLUSIVAS para adjuvantes/fertilizantes.
       DEFENSIVOS (herbicidas, fungicidas, inseticidas etc.) NUNCA vão nessas posições.
       Um defensivo SE vai na posição 10, um EC na 11, um SC na 8, etc.

ETAPA 4 — VALIDAÇÃO CRUZADA (antes de responder):
  ✓ Se classe=defensivo, a posição DEVE ser 3-11, 13-16 (posições com sigla)
  ✓ Se classe=adjuvante, a posição DEVE ser 2, 12, 17, ou 19
  ✓ Se classe=fertilizante, a posição DEVE ser 18
  ✓ A formulação e a posição devem ser compatíveis (ex: SC→8, EC→11, WG→6)
  ✓ Se qualquer validação falhar, revise sua classificação antes de responder

═══════════════════════════════════════════════════════════════
FORMATO DE RESPOSTA — apenas JSON válido, sem texto adicional:
═══════════════════════════════════════════════════════════════

Para DEFENSIVOS:
{
  "encontrado": true,
  "nome_completo": "Zethamaxx Evo",
  "classe": "herbicida",
  "formulacao": "SE",
  "posicao": 10,
  "registro_mapa": "45924",
  "ingrediente_ativo": "s-metolacloro+flumioxazina+imazetapir",
  "tipo_adjuvante": null,
  "confianca": "alta"
}

Para ADJUVANTES:
{
  "encontrado": true,
  "nome_completo": "Nimbus",
  "classe": "adjuvante",
  "formulacao": "OLEO",
  "posicao": 12,
  "registro_mapa": null,
  "ingrediente_ativo": "óleo mineral",
  "tipo_adjuvante": "óleo mineral",
  "confianca": "alta"
}

CAMPO "confianca":
  - "alta": produto conhecido, formulação confirmada pela bula
  - "media": produto provável mas sem certeza da formulação exata
  - "baixa": chute — prefira retornar {"encontrado": false} em vez de chutar

Se NÃO consegue identificar com confiança média ou alta:
{"encontrado": false, "motivo": "explicação curta"}"""


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
    preco_in, preco_out = _PRECOS_POR_MODELO.get("claude-haiku-5-5", _PRECO_FALLBACK)
    custo_usd = tokens_in * preco_in + tokens_out * preco_out
    logger.info(
        "busca_produto id=%s nome='%s' tokens_in=%d tokens_out=%d custo_usd=%.6f",
        resposta.id, nome, tokens_in, tokens_out, custo_usd,
    )

    texto = ""
    for bloco in resposta.content:
        if bloco.type == "text":
            texto = bloco.text.strip()
            break

    texto = _limpar_markdown(texto)

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return None

    if not dados.get("encontrado"):
        logger.info("busca_produto nome='%s' nao_encontrado motivo='%s'", nome, dados.get("motivo", ""))
        return None

    if dados.get("confianca") == "baixa":
        logger.warning("busca_produto nome='%s' confianca=baixa — descartado", nome)
        return None

    formulacao = (dados.get("formulacao") or "").upper()
    posicao = dados.get("posicao")
    classe = (dados.get("classe") or "").lower()

    if not _validar_resposta(classe, formulacao, posicao):
        logger.warning(
            "busca_produto nome='%s' VALIDACAO_FALHOU classe=%s form=%s pos=%s — descartado",
            nome, classe, formulacao, posicao,
        )
        return None

    return dados


_POSICOES_DEFENSIVO = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16}
_POSICOES_ADJUVANTE = {2, 12, 17, 19}


def _validar_resposta(classe: str, formulacao: str, posicao) -> bool:
    """Valida que classe, formulação e posição são compatíveis."""
    if not isinstance(posicao, int) or not (1 <= posicao <= 20):
        return False

    defensivos = {"herbicida", "fungicida", "inseticida", "acaricida", "nematicida", "regulador"}
    adjuvantes = {"adjuvante", "óleo mineral", "óleo vegetal", "condicionador", "espalhante", "surfactante"}
    fertilizantes = {"fertilizante foliar", "fertilizante", "aminoácido", "bioestimulante"}

    if classe in defensivos:
        if posicao not in _POSICOES_DEFENSIVO:
            return False
        if formulacao in _FORMULACAO_PARA_POSICAO and _FORMULACAO_PARA_POSICAO[formulacao] != posicao:
            return False
    elif classe in adjuvantes:
        if posicao not in _POSICOES_ADJUVANTE:
            return False
    elif classe in fertilizantes:
        if posicao != 18:
            return False

    return True


def salvar_produto(nome_original: str, dados_ia: dict) -> dict:
    """
    Salva produto encontrado pela IA em produtos.csv.
    Retorna o dict do produto salvo (com posicao).
    """
    formulacao = (dados_ia.get("formulacao") or "").upper()

    posicao = _FORMULACAO_PARA_POSICAO.get(formulacao) or _FORM_ESPECIAL_POSICAO.get(formulacao) or 999

    _FORM_ESPECIAL = {2: "ADJUVANTE", 12: "OLEO", 17: "ADJUVANTE", 18: "FERTILIZANTE", 19: "ADJUVANTE"}
    if posicao in _FORM_ESPECIAL and formulacao not in _FORMULACAO_PARA_POSICAO:
        formulacao = _FORM_ESPECIAL[posicao]

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
        ja_existe = False
        with open(caminho, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["nome"].lower().strip() == nome_completo.lower().strip():
                    ja_existe = True
                    break
        if ja_existe:
            logger.info("Produto '%s' ja existe em CSV — pulando duplicata", nome_completo)
            return produto
        with open(caminho, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["nome", "nomes_alternativos", "registro_mapa",
                                                    "formulacao", "posicao", "fonte", "data_conferencia",
                                                    "principio_ativo"])
            writer.writerow(produto)
        logger.info("Produto salvo: %s (%s, posicao %d)", nome_completo, formulacao, posicao)
    except OSError:
        logger.warning("Filesystem read-only — produto '%s' nao persistido", nome_completo)
    return produto
