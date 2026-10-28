"""
Alertas de risco de incompatibilidade na calda.
Regras puras de código — sem IA. O assistente SUGERE; o agrônomo APROVA.
"""
import unicodedata


def _norm(texto: str) -> str:
    texto = texto.lower().strip()
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M"))


def _eh_mancozeb(item: dict) -> bool:
    n = _norm(item["produto"])
    return any(x in n for x in ("mancozeb", "mancozebe", "unizeb", "dithane", "manzate", "pencozeb", "bravonil"))


def _eh_glifosato(item: dict) -> bool:
    n = _norm(item["produto"])
    return any(x in n for x in ("glifosato", "roundup", "glifos", "touchdown", "zapp"))


def verificar_incompatibilidades(itens: list[dict], vazao_L_ha: float | None) -> list[dict]:
    """
    Retorna lista de alertas de incompatibilidade.
    Cada alerta: {"nivel": "alto"|"medio", "mensagem": str}
    """
    alertas = []

    mancozeb_items = [it for it in itens if _eh_mancozeb(it)]
    glif_items = [it for it in itens if _eh_glifosato(it)]

    if not mancozeb_items or not glif_items:
        # Sem par de risco — verifica só vazão com glifosato SL
        if glif_items and vazao_L_ha and vazao_L_ha <= 50:
            glif = glif_items[0]
            form = (glif.get("formulacao") or "").upper()
            if form == "SL":
                alertas.append({
                    "nivel": "medio",
                    "mensagem": (
                        f"VAZÃO BAIXA ({vazao_L_ha:.0f} L/ha): com Glifosato líquido (SL) "
                        "em baixo volume aumenta o risco de precipitação. "
                        "Confirme com o agrônomo."
                    ),
                })
        return alertas

    for mc in mancozeb_items:
        for glif in glif_items:
            form_mc = (mc.get("formulacao") or "").upper()
            form_glif = (glif.get("formulacao") or "").upper()

            # Pó (WG/WP) + qualquer glifosato → risco alto
            if form_mc in ("WG", "WP", "SP"):
                alertas.append({
                    "nivel": "alto",
                    "mensagem": (
                        f"RISCO DE INCOMPATIBILIDADE: {mc['produto']} ({form_mc}) em pó "
                        f"com {glif['produto']} pode precipitar na calda. "
                        "Confirme compatibilidade com o agrônomo antes de misturar."
                    ),
                })
            # Mancozeb SC + Glifosato SL → risco médio
            elif form_glif == "SL":
                alertas.append({
                    "nivel": "medio",
                    "mensagem": (
                        f"ATENÇÃO: {mc['produto']} + {glif['produto']} (SL líquido) — "
                        "risco de incompatibilidade. Confirme com o agrônomo."
                    ),
                })

            # Agrava com baixa vazão
            if vazao_L_ha and vazao_L_ha <= 50 and form_glif == "SL":
                alertas.append({
                    "nivel": "alto",
                    "mensagem": (
                        f"VAZÃO BAIXA ({vazao_L_ha:.0f} L/ha): aumenta o risco de "
                        f"precipitação de {mc['produto']} com Glifosato líquido. "
                        "Considere aumentar o volume de calda. Confirme com o agrônomo."
                    ),
                })

    return alertas
