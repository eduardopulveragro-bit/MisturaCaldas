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

# Cache em memória: evita re-chamar a API para o mesmo produto na mesma instância.
_CACHE_PRODUTOS: dict[str, dict | None] = {}

_PROMPT_BUSCA = """Você é um especialista em defensivos agrícolas no Brasil. Dado um nome de produto, retorne APENAS JSON.

CLASSES e POSIÇÕES:
- Defensivos (herbicida/fungicida/inseticida/acaricida): posição pela formulação: SG=3, SP=4, WP=5, WG=6, CS=7, SC=8, OD=9, SE=10, EC=11, EO=13, EW=14, ME=15, SL=16
- Adjuvante óleo (mineral/vegetal/OLEO DE LARANJA): formulacao="OLEO", posicao=12
- Adjuvante condicionador/pH/quelante: formulacao="ADJUVANTE", posicao=2
- Adjuvante espalhante/surfactante: formulacao="ADJUVANTE", posicao=17
- Fertilizante foliar/bioestimulante: formulacao="FERTILIZANTE", posicao=18
- Biológico bacteriano (Bacillus): formulacao="BIO_BACTERIANO", posicao=20
- Biológico fúngico (Trichoderma/Beauveria): formulacao="BIO_FUNGICO", posicao=21
- Biológico viral (Baculovírus): formulacao="BIO_VIRAL", posicao=22

REGRAS:
- Defensivos NUNCA vão em posições de adjuvante/fertilizante/biológico.
- Se não souber com confiança média ou alta: {"encontrado": false, "motivo": "..."}
- confianca "baixa" = retorne encontrado:false.

FORMATO (JSON puro):
{"encontrado":true,"nome_completo":"Nome","classe":"herbicida","formulacao":"EC","posicao":11,"registro_mapa":"12345","ingrediente_ativo":"glifosato","tipo_adjuvante":null,"confianca":"alta"}"""


def buscar_produto_ia(nome: str) -> dict | None:
    """
    Consulta a IA sobre um produto não cadastrado.
    Retorna dict com dados do produto ou None se não encontrado.
    Usa cache em memória para evitar chamadas repetidas.
    """
    chave = nome.lower().strip()
    if chave in _CACHE_PRODUTOS:
        logger.info("busca_produto CACHE_HIT nome='%s'", nome)
        return _CACHE_PRODUTOS[chave]

    from src.parser import _criar_cliente
    try:
        cliente = _criar_cliente()
    except EnvironmentError:
        return None

    try:
        resposta = cliente.messages.create(
            model="claude-haiku-5-5",
            max_tokens=300,
            system=[{
                "type": "text",
                "text": _PROMPT_BUSCA,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": f"Produto: {nome}",
            }],
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

    # Pega o ÚLTIMO bloco de texto — com web_search pode haver blocos intermediários
    # (web_search_tool_result) antes da resposta final em JSON.
    texto = ""
    for bloco in resposta.content:
        if bloco.type == "text":
            texto = bloco.text.strip()

    texto = _limpar_markdown(texto)

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return None

    if not dados.get("encontrado"):
        logger.info("busca_produto nome='%s' nao_encontrado motivo='%s'", nome, dados.get("motivo", ""))
        _CACHE_PRODUTOS[chave] = None
        return None

    if dados.get("confianca") == "baixa":
        logger.warning("busca_produto nome='%s' confianca=baixa — descartado", nome)
        _CACHE_PRODUTOS[chave] = None
        return None

    formulacao = (dados.get("formulacao") or "").upper()
    posicao = dados.get("posicao")
    classe = (dados.get("classe") or "").lower()

    if not _validar_resposta(classe, formulacao, posicao):
        logger.warning(
            "busca_produto nome='%s' VALIDACAO_FALHOU classe=%s form=%s pos=%s — descartado",
            nome, classe, formulacao, posicao,
        )
        _CACHE_PRODUTOS[chave] = None
        return None

    _CACHE_PRODUTOS[chave] = dados
    return dados


_POSICOES_DEFENSIVO = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16}
_POSICOES_ADJUVANTE = {2, 12, 17, 19}
_POSICOES_BIOLOGICO = {20, 21, 22}


def _validar_resposta(classe: str, formulacao: str, posicao) -> bool:
    """Valida que classe, formulação e posição são compatíveis."""
    if not isinstance(posicao, int) or not (1 <= posicao <= 23):
        return False

    defensivos = {"herbicida", "fungicida", "inseticida", "acaricida", "nematicida", "regulador"}
    adjuvantes = {"adjuvante", "óleo mineral", "óleo vegetal", "condicionador", "espalhante", "surfactante"}
    fertilizantes = {"fertilizante foliar", "fertilizante", "aminoácido", "bioestimulante"}
    biologicos = {"biologico", "biológico", "inseticida biológico", "fungicida biológico",
                  "biocontrole", "biopesticida", "microrganismo"}

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
    elif classe in biologicos:
        if posicao not in _POSICOES_BIOLOGICO:
            return False

    return True


def salvar_produto(nome_original: str, dados_ia: dict) -> dict:
    """
    Salva produto encontrado pela IA em produtos.csv.
    Retorna o dict do produto salvo (com posicao).
    """
    formulacao = (dados_ia.get("formulacao") or "").upper()

    posicao = _FORMULACAO_PARA_POSICAO.get(formulacao) or _FORM_ESPECIAL_POSICAO.get(formulacao) or 999

    _FORM_ESPECIAL = {
        2: "ADJUVANTE", 12: "OLEO", 17: "ADJUVANTE", 18: "FERTILIZANTE", 19: "ADJUVANTE",
        20: "BIO_BACTERIANO", 21: "BIO_FUNGICO", 22: "BIO_VIRAL",
    }
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
