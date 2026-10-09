"""
Motor de ordenação — SEM IA. Usa produtos.csv e regras_ordem.csv.
A IA extrai dados (inclusive formulação); o CÓDIGO decide a ordem.
"""
import csv
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Mapa formulação → posição (extraído de regras_ordem.csv)
_FORMULACAO_PARA_POSICAO = {
    "SG": 3, "SP": 4, "WP": 5, "WG": 6,
    "CS": 7, "SC": 8, "OD": 9, "SE": 10,
    "EC": 11, "EO": 13, "EW": 14, "ME": 15, "SL": 16,
}


def _carregar_csv(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))


def buscar_produto(nome: str, produtos: list[dict]) -> dict | None:
    """Busca produto por nome ou nome alternativo (case-insensitive, parcial)."""
    chave = _normalizar(nome)

    # 1. Busca exata
    for p in produtos:
        if _normalizar(p["nome"]) == chave:
            return p
        alternativos = str(p.get("nomes_alternativos", "") or "")
        for alt in alternativos.split("|"):
            if _normalizar(alt) == chave:
                return p

    # 2. Busca parcial: nome digitado contém o alternativo ou vice-versa
    for p in produtos:
        if chave in _normalizar(p["nome"]) or _normalizar(p["nome"]) in chave:
            return p
        alternativos = str(p.get("nomes_alternativos", "") or "")
        for alt in alternativos.split("|"):
            alt_norm = _normalizar(alt)
            if alt_norm and (chave in alt_norm or alt_norm in chave):
                return p

    return None


def _posicao_por_formulacao(formulacao: str | None) -> int | None:
    """Converte sigla de formulação para posição na ordem de adição."""
    if not formulacao:
        return None
    return _FORMULACAO_PARA_POSICAO.get(formulacao.strip().upper())


def ordenar_itens(itens: list[dict]) -> list[dict]:
    """
    Ordena itens pela posição de adição na calda.
    Prioridade:
      1) produtos.csv (cadastro confirmado)
      2) busca automática: consulta IA, salva em produtos.csv, marca pendente
      3) formulação extraída na mensagem
      4) posicao=999 (desconhecido)
    """
    from src.busca_produto import buscar_produto_ia, salvar_produto

    produtos = _carregar_csv(DATA_DIR / "produtos.csv")
    resultado = []

    for item in itens:
        info = buscar_produto(item["produto"], produtos)

        if info is not None:
            resultado.append({
                **item,
                "posicao": int(info["posicao"]),
                "formulacao": info["formulacao"],
                "registro_mapa": info["registro_mapa"],
                "fonte": info.get("fonte", ""),
                "pendente": "pendente" in info.get("data_conferencia", ""),
            })
            continue

        # Produto não cadastrado: busca via IA e salva
        dados_ia = buscar_produto_ia(item["produto"])
        if dados_ia:
            produto_salvo = salvar_produto(item["produto"], dados_ia)
            posicao = int(produto_salvo["posicao"])
            resultado.append({
                **item,
                "posicao": posicao,
                "formulacao": produto_salvo["formulacao"],
                "registro_mapa": produto_salvo.get("registro_mapa", ""),
                "fonte": produto_salvo["fonte"],
                "pendente": True,
                "alerta_pendente": f"produto cadastrado automaticamente ({produto_salvo['formulacao']}) — confirmar com agrônomo",
            })
            continue

        # Fallback: tenta formulação extraída pela IA na mensagem original
        formulacao_ia = item.get("formulacao")
        posicao_ia = _posicao_por_formulacao(formulacao_ia)
        if posicao_ia is not None:
            resultado.append({
                **item,
                "posicao": posicao_ia,
                "formulacao": formulacao_ia.upper(),
                "registro_mapa": "",
                "fonte": "formulação da mensagem (não confirmada)",
                "pendente": True,
                "alerta_pendente": f"produto não cadastrado — formulação {formulacao_ia.upper()} da mensagem",
            })
        else:
            resultado.append({
                **item,
                "posicao": 999,
                "formulacao": "DESCONHECIDA",
                "registro_mapa": "",
                "fonte": "",
                "pendente": True,
                "alerta_pendente": "produto e formulação não identificados",
            })

    resultado.sort(key=lambda x: (x["posicao"], 0 if x["posicao"] in (2, 16) else -_dose_em_ml(x)))
    resultado = _priorizar_heat(resultado)
    resultado = _posicionar_sl(resultado)
    resultado = _posicionar_oleo(resultado)
    resultado = _oleo_laranja_com_mancozeb(resultado)
    resultado = _prediluir_cletodim_oleo(resultado)
    resultado = _prediluir_abamectina_oleo(resultado)
    resultado = _prediluir_haloxifop_oleo(resultado)
    resultado = _separar_glif_24d(resultado)
    return resultado


def _eh_glifosato(item: dict) -> bool:
    nome = _normalizar(item["produto"])
    return any(x in nome for x in ("glifosato", "roundup", "glifos"))


def _eh_24d(item: dict) -> bool:
    nome = _normalizar(item["produto"])
    return any(x in nome for x in ("2,4-d", "2,4 d", "2,4d", "aminol", "dma 806", "u-46"))


def _eh_heat(item: dict) -> bool:
    nome = _normalizar(item["produto"])
    return any(x in nome for x in ("heat", "saflufenacil"))


def _dose_em_ml(item: dict) -> float:
    dose = item.get("dose", 0) or 0
    unidade = (item.get("unidade") or "").lower()
    if unidade in ("l", "lt"):
        return dose * 1000
    if unidade == "kg":
        return dose * 1000
    return dose


def _priorizar_heat(resultado: list[dict]) -> list[dict]:
    """Heat (Saflufenacil WG): pre-diluir em agua, colocar logo apos condicionador."""
    heat = None
    for item in resultado:
        if _eh_heat(item):
            heat = item
            break
    if not heat:
        return resultado

    resultado.remove(heat)
    ponto = 0
    for i, item in enumerate(resultado):
        if item["posicao"] <= 2:
            ponto = i + 1
    heat["alerta_prediluicao"] = "pré-diluir em água antes de adicionar ao tanque"
    resultado.insert(ponto, heat)
    return resultado


def _posicionar_sl(resultado: list[dict]) -> list[dict]:
    sls = [item for item in resultado if item["posicao"] == 16]
    if not sls:
        return resultado

    tem_glif_sl = any(_eh_glifosato(s) for s in sls)
    tem_24d_sl = any(_eh_24d(s) for s in sls)
    tem_glif_wg = any(_eh_glifosato(item) and item["posicao"] == 6 for item in resultado)

    if tem_glif_sl and tem_24d_sl:
        primeiro_sl = next(s for s in sls if _eh_24d(s))
    elif tem_24d_sl and tem_glif_wg and len(sls) >= 2:
        outros = [s for s in sls if not _eh_24d(s)]
        primeiro_sl = outros[0] if outros else sls[0]
    else:
        primeiro_sl = sls[0]

    dose_ml = _dose_em_ml(primeiro_sl)
    tem_po_suspensao = any(item["posicao"] in (5, 6) for item in resultado)
    deve_mover = len(sls) >= 2 or dose_ml >= 2500 or (dose_ml >= 2000 and tem_po_suspensao)
    if not deve_mover:
        return resultado

    resultado.remove(primeiro_sl)

    ponto = 0
    for i, item in enumerate(resultado):
        if item["posicao"] <= 6:
            ponto = i + 1

    if ponto == 0:
        for i, item in enumerate(resultado):
            if item["posicao"] <= 2:
                ponto = i + 1

    resultado.insert(ponto, primeiro_sl)
    return resultado


def _posicionar_oleo(resultado: list[dict]) -> list[dict]:
    oleos = [item for item in resultado if item["posicao"] == 12]
    if not oleos:
        return resultado
    for oleo in oleos:
        resultado.remove(oleo)
    ponto = len(resultado)
    for i, item in enumerate(resultado):
        if item["posicao"] > 16:
            ponto = i
            break
    for oleo in oleos:
        resultado.insert(ponto, oleo)
        ponto += 1
    return resultado


def _oleo_laranja_com_mancozeb(resultado: list[dict]) -> list[dict]:
    mancozeb = None
    oleo_laranja = None
    for item in resultado:
        nome = _normalizar(item["produto"])
        if any(x in nome for x in ("mancozeb", "mancozebe", "unizeb")):
            mancozeb = item
        elif any(x in nome for x in ("oleo de laranja", "oleo da laranja", "terpen")):
            oleo_laranja = item
    if not mancozeb or not oleo_laranja:
        return resultado
    resultado.remove(oleo_laranja)
    ponto = 0
    for i, item in enumerate(resultado):
        if item["posicao"] <= 2:
            ponto = i + 1
    resultado.insert(ponto, oleo_laranja)
    return resultado


def _prediluir_cletodim_oleo(resultado: list[dict]) -> list[dict]:
    """
    Cletodim + óleo mineral devem ser pré-diluídos juntos e adicionados
    por último entre os produtos regulares (antes de adjuvantes pos 17+).
    """
    cletodim = None
    oleo = None

    for item in resultado:
        nome = _normalizar(item["produto"])
        if any(x in nome for x in ("cletodim", "cletodin", "clethodim", "select", "cartago")):
            cletodim = item
        elif item["posicao"] == 12 and not any(x in nome for x in ("laranja", "terpen")):
            oleo = item

    if not cletodim or not oleo:
        return resultado

    resultado.remove(cletodim)
    resultado.remove(oleo)

    ponto = len(resultado)
    for i, item in enumerate(resultado):
        if item["posicao"] > 16:
            ponto = i
            break

    cletodim["alerta_prediluicao"] = "pré-diluir com óleo mineral antes de adicionar"
    oleo["alerta_prediluicao"] = "pré-diluir com cletodim antes de adicionar"
    resultado.insert(ponto, oleo)
    resultado.insert(ponto, cletodim)
    return resultado


def _prediluir_abamectina_oleo(resultado: list[dict]) -> list[dict]:
    abamectina = None
    oleo = None
    for item in resultado:
        nome = _normalizar(item["produto"])
        if any(x in nome for x in ("abamectina", "abamectin", "vertimec", "kraft")):
            abamectina = item
        elif item["posicao"] == 12 and not item.get("alerta_prediluicao"):
            oleo = item
    if not abamectina or not oleo:
        return resultado
    resultado.remove(abamectina)
    resultado.remove(oleo)
    ponto = len(resultado)
    for i, item in enumerate(resultado):
        if item["posicao"] > 16:
            ponto = i
            break
    abamectina["alerta_prediluicao"] = f"pré-diluir com {oleo['produto']} antes de adicionar"
    oleo["alerta_prediluicao"] = f"pré-diluir com {abamectina['produto']} antes de adicionar"
    resultado.insert(ponto, oleo)
    resultado.insert(ponto, abamectina)
    return resultado


def _prediluir_haloxifop_oleo(resultado: list[dict]) -> list[dict]:
    halox = None
    oleo = None
    for item in resultado:
        nome = _normalizar(item["produto"])
        if any(x in nome for x in ("haloxifop", "haloxifope", "haloxyfop", "verdict", "gallant", "missil ultra", "viggie")):
            halox = item
        elif item["posicao"] == 12 and not item.get("alerta_prediluicao"):
            oleo = item
    if not halox or not oleo:
        return resultado
    resultado.remove(halox)
    resultado.remove(oleo)
    ponto = len(resultado)
    for i, item in enumerate(resultado):
        if item["posicao"] > 16:
            ponto = i
            break
    halox["alerta_prediluicao"] = f"pré-diluir com {oleo['produto']} antes de adicionar"
    oleo["alerta_prediluicao"] = f"pré-diluir com {halox['produto']} antes de adicionar"
    resultado.insert(ponto, oleo)
    resultado.insert(ponto, halox)
    return resultado


def _separar_glif_24d(resultado: list[dict]) -> list[dict]:
    """Glifosato e 2,4-D juntos: separar ao maximo.
    Glifosato WG + 2,4-D: glif cedo (solido), 2,4-D por ultimo.
    Ambos SL: 2,4-D cedo (ja movido), glifosato por ultimo."""
    item_24d = None
    item_glif = None
    for item in resultado:
        if _eh_24d(item) and not item_24d:
            item_24d = item
        if _eh_glifosato(item) and not item_glif:
            item_glif = item

    if not item_24d or not item_glif:
        return resultado

    if item_glif["posicao"] == 6:
        para_final = item_24d
    else:
        para_final = item_glif

    idx = resultado.index(para_final)
    ponto_final = len(resultado)
    for i, item in enumerate(resultado):
        if item["posicao"] >= 17:
            ponto_final = i
            break

    if idx >= ponto_final - 1:
        return resultado

    resultado.remove(para_final)
    ponto_final = len(resultado)
    for i, item in enumerate(resultado):
        if item["posicao"] >= 17:
            ponto_final = i
            break
    resultado.insert(ponto_final, para_final)
    return resultado


def descricao_posicao(posicao: int) -> str:
    """Retorna a descrição da regra para aquela posição."""
    regras = _carregar_csv(DATA_DIR / "regras_ordem.csv")
    for r in regras:
        if int(r["posicao"]) == posicao:
            return r["descricao"]
    return f"Posição {posicao}"
