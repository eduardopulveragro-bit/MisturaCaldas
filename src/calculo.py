"""Cálculos de taxa de aplicação e totais por carga — fórmula fixa, sem IA."""


def calcular_taxa_L_ha(vazao_L_min: float, velocidade_km_h: float, faixa_m: float) -> float:
    """L/ha = vazão(L/min) × 600 / (velocidade km/h × faixa m)"""
    if velocidade_km_h <= 0 or faixa_m <= 0:
        raise ValueError("Velocidade e faixa devem ser positivos")
    return round((vazao_L_min * 600) / (velocidade_km_h * faixa_m), 2)


def calcular_totais_por_carga(
    itens: list[dict], taxa_L_ha: float, volume_tanque_L: float
) -> tuple[list[dict], float]:
    """
    Calcula quantidade de cada produto por carga completa do tanque.
    Retorna (itens_com_totais, ha_por_carga).
    """
    if taxa_L_ha <= 0:
        raise ValueError("Taxa de aplicação deve ser positiva")

    ha_por_carga = round(volume_tanque_L / taxa_L_ha, 2)
    resultado = []

    for item in itens:
        dose = item.get("dose") or 0
        base = item.get("base", "ha")

        if base == "ha":
            qtd_por_carga = round(dose * ha_por_carga, 3)
        else:
            # base == "L_calda": dose por litro de calda
            qtd_por_carga = round(dose * volume_tanque_L, 3)

        resultado.append({**item, "qtd_por_carga": qtd_por_carga})

    return resultado, ha_por_carga
