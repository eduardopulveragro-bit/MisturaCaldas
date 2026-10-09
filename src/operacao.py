"""
Extração de parâmetros operacionais da mensagem — SEM IA.
Detecta área por tanque, vazão, ponta, pressão e tipo de gota via regex.
Calcula totais por tanque.
"""
import re


def extrair_operacao(texto: str) -> dict:
    """Extrai parametros operacionais do texto livre (regex)."""
    resultado = {}

    # "tanque para 50 ha" / "tanque 50ha" / "tq 27 ha"
    m = re.search(
        r"(?:tanque|tq|tk)\s*(?:para|p/)?\s*(\d+(?:[,\.]\d+)?)\s*h[aá]",
        texto, re.IGNORECASE,
    )
    if m:
        resultado["area_tanque_ha"] = float(m.group(1).replace(",", "."))

    # "vazão 80 l/ha" / "vazão - 60l" / "vazao 75l"
    m = re.search(
        r"vaz[aã]o\s*[-:]?\s*(\d+(?:[,\.]\d+)?)\s*l(?:/h[aá])?",
        texto, re.IGNORECASE,
    )
    if m:
        resultado["vazao_L_ha"] = float(m.group(1).replace(",", "."))

    # "ponta - Leque HI 35" / "ponta TT110015"
    m = re.search(
        r"ponta\s*[-:]?\s*(.+?)(?:\n|pressão|press|vazão|vaz|$)",
        texto, re.IGNORECASE,
    )
    if m:
        resultado["ponta"] = m.group(1).strip().rstrip("-: ")

    # "pressão max 2,5 bar" / "pressao - 3 bar"
    m = re.search(
        r"press[aã]o\s*(?:max|m[aá]x\.?)?\s*[-:]?\s*(\d+(?:[,\.]\d+)?)\s*bar",
        texto, re.IGNORECASE,
    )
    if m:
        resultado["pressao_bar"] = float(m.group(1).replace(",", "."))

    # "gota fina" / "gota média" / "gota grossa"
    m = re.search(r"gota\s+(fina|m[eé]dia|grossa|ultra\s*fina)", texto, re.IGNORECASE)
    if m:
        resultado["tipo_gota"] = m.group(1).lower()

    # Área total (ex: "dessecação 54 ha" / "receita 40ha")
    if "area_tanque_ha" not in resultado:
        m = re.search(r"(\d+(?:[,\.]\d+)?)\s*h[aá]\b", texto, re.IGNORECASE)
        if m:
            resultado["area_tanque_ha"] = float(m.group(1).replace(",", "."))

    return resultado


def calcular_totais_tanque(itens: list[dict], area_ha: float) -> list[dict]:
    """Adiciona 'total_tanque' e 'total_formatado' a cada item."""
    for item in itens:
        dose = item.get("dose") or 0
        unidade = (item.get("unidade") or "").lower()

        total = dose * area_ha
        if unidade in ("l", "lt"):
            item["total_tanque"] = round(total, 1)
            item["total_unidade"] = "L"
        elif unidade == "ml":
            if total >= 1000:
                item["total_tanque"] = round(total / 1000, 1)
                item["total_unidade"] = "L"
            else:
                item["total_tanque"] = round(total, 0)
                item["total_unidade"] = "mL"
        elif unidade in ("kg",):
            item["total_tanque"] = round(total, 1)
            item["total_unidade"] = "kg"
        elif unidade in ("g", "gr"):
            if total >= 1000:
                item["total_tanque"] = round(total / 1000, 1)
                item["total_unidade"] = "kg"
            else:
                item["total_tanque"] = round(total, 0)
                item["total_unidade"] = "g"
        else:
            item["total_tanque"] = round(total, 1)
            item["total_unidade"] = unidade

    return itens
