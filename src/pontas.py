"""
Sugestão de ponta e pressão — baseada em pontas.csv e no cadastro da fazenda.
Se não houver linha correspondente, retorna "pendente". Nunca inventa valor.
"""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

RESULTADO_PENDENTE = {
    "sugestao": "pendente",
    "ponta": None,
    "pressao_bar": None,
    "vazao_L_min": None,
    "classe_gota": None,
    "observacao": "Sem dados em pontas.csv para a ponta da fazenda ou taxa calculada",
}


def sugerir_ponta(ponta_em_uso: str, vazao_alvo_L_min: float) -> dict:
    """
    Busca em pontas.csv a linha que mais se aproxima da vazão alvo para a ponta informada.
    Retorna resultado_pendente se não encontrar nada.
    """
    caminho = DATA_DIR / "pontas.csv"
    if not caminho.exists():
        return RESULTADO_PENDENTE

    with open(caminho, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))

    candidatos = [
        l for l in linhas if l["ponta"].strip().upper() == ponta_em_uso.strip().upper()
    ]
    if not candidatos:
        return {**RESULTADO_PENDENTE, "observacao": f"Ponta '{ponta_em_uso}' não encontrada em pontas.csv"}

    # Escolhe a linha com menor diferença de vazão
    melhor = min(candidatos, key=lambda l: abs(float(l["vazao_L_min"]) - vazao_alvo_L_min))
    diferenca = abs(float(melhor["vazao_L_min"]) - vazao_alvo_L_min)

    # Tolerância de 20% da vazão alvo
    if diferenca > vazao_alvo_L_min * 0.20:
        return {**RESULTADO_PENDENTE, "observacao": f"Nenhuma linha dentro da tolerância para ponta {ponta_em_uso}"}

    return {
        "sugestao": "SUGERIDO - AGUARDANDO APROVAÇÃO",
        "ponta": melhor["ponta"],
        "pressao_bar": float(melhor["pressao_bar"]),
        "vazao_L_min": float(melhor["vazao_L_min"]),
        "classe_gota": melhor["classe_gota"],
        "observacao": "",
    }
