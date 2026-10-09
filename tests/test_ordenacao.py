"""
Testes de ordenação baseados em pares.csv.
Cada linha do arquivo é um caso: ordem original → ordem corrigida esperada.
NÃO ajustar as regras para passar nos testes; listar divergências para revisão.
"""
import csv
from pathlib import Path
import pytest

from src.ordenacao import ordenar_itens

DATA_DIR = Path(__file__).parent.parent / "data"


def _carregar_pares() -> list[tuple[list[str], list[str]]]:
    """Lê pares.csv e retorna lista de (original, corrigido)."""
    pares = []
    caminho = DATA_DIR / "pares.csv"
    with open(caminho, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            original = [p.strip() for p in row["ordem_original"].split("|")]
            corrigido = [p.strip() for p in row["ordem_corrigida"].split("|")]
            pares.append((original, corrigido))
    return pares


def _nomes_ordenados(nomes: list[str]) -> list[str]:
    """Converte lista de nomes em itens mínimos, ordena e retorna nomes."""
    itens = [{"produto": n, "dose": 1, "unidade": "L", "base": "ha"} for n in nomes]
    return [it["produto"] for it in ordenar_itens(itens)]


def test_todos_os_pares():
    """
    Roda todos os pares de pares.csv.
    Imprime taxa de acerto e cada divergência para revisão do especialista.
    NÃO falha o suite só por divergências — elas são listadas para revisão.
    """
    pares = _carregar_pares()
    acertos = 0
    divergencias = []

    for i, (original, esperado) in enumerate(pares):
        obtido = _nomes_ordenados(original)
        if obtido == esperado:
            acertos += 1
        else:
            divergencias.append({
                "par": i + 1,
                "original": original,
                "esperado": esperado,
                "obtido": obtido,
            })

    total = len(pares)
    taxa = acertos / total * 100 if total > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"RESULTADO: {acertos}/{total} acertos ({taxa:.1f}%)")
    if divergencias:
        print(f"\nDIVERGÊNCIAS ({len(divergencias)}) — revisar com especialista:")
        for d in divergencias:
            print(f"\n  Par {d['par']}:")
            print(f"    Original : {' → '.join(d['original'])}")
            print(f"    Esperado : {' → '.join(d['esperado'])}")
            print(f"    Obtido   : {' → '.join(d['obtido'])}")
    else:
        print("Nenhuma divergência.")
    print("=" * 60)

    # O teste só falha se NENHUM par passou (indica problema estrutural)
    assert total > 0, "pares.csv está vazio"
    assert acertos > 0, f"Zero acertos em {total} pares — verifique produtos.csv e regras"


# Testes unitários individuais para regressão
@pytest.mark.parametrize("entrada,esperado", [
    (["Score", "Engeo Pleno S"], ["Engeo Pleno S", "Score"]),  # EC(11) antes de SC(8) → errado
    (["Roundup Original DI", "Lannate BR"], ["Lannate BR", "Roundup Original DI"]),  # SL(16) antes de SP(4)
    (["Opera Ultra", "Engeo Pleno S", "Ally"], ["Ally", "Engeo Pleno S", "Opera Ultra"]),
])
def test_ordem_parametrizado(entrada, esperado):
    obtido = _nomes_ordenados(entrada)
    assert obtido == esperado, (
        f"\nEntrada : {entrada}"
        f"\nEsperado: {esperado}"
        f"\nObtido  : {obtido}"
    )


def test_produto_nao_cadastrado():
    """Produto desconhecido deve ficar no final (posicao=999) e pendente=True."""
    itens = [{"produto": "ProdutoXXX_Inexistente", "dose": 1, "unidade": "L", "base": "ha"}]
    resultado = ordenar_itens(itens)
    assert resultado[0]["pendente"] is True
    assert resultado[0]["posicao"] == 999


def test_ordenacao_sem_ia():
    """Garante que ordenar_itens não importa nem chama anthropic."""
    import sys
    # anthropic NÃO deve ser importado pelo módulo de ordenação
    from src import ordenacao
    codigo = Path(ordenacao.__file__).read_text(encoding="utf-8")
    assert "anthropic" not in codigo, "Módulo de ordenação não deve chamar IA"


def test_calculos_taxa():
    """Taxa L/ha = vazão × 600 / (velocidade × faixa)"""
    from src.calculo import calcular_taxa_L_ha
    # 0.8 * 600 / (18 * 17) = 480 / 306 ≈ 1.57
    resultado = calcular_taxa_L_ha(0.8, 18, 17)
    assert abs(resultado - 1.57) < 0.01


def test_calculos_totais():
    """Verifica cálculo de totais por carga."""
    from src.calculo import calcular_totais_por_carga
    itens = [{"produto": "A", "dose": 2.0, "unidade": "L", "base": "ha", "posicao": 8}]
    resultado, ha_por_carga = calcular_totais_por_carga(itens, taxa_L_ha=2.0, volume_tanque_L=2000)
    assert ha_por_carga == 1000.0
    assert resultado[0]["qtd_por_carga"] == 2000.0
