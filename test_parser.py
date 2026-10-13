"""
Teste da ordenação com dados simulados (formato do parser enxuto).
Verifica que o motor de ordenação funciona corretamente quando a IA
retorna só nome+dose+unidade (sem formulação), confiando no CSV.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.ordenacao import ordenar_itens

CALDAS = [
    {
        "nome": "Calda dessecação soja (sem formulação da IA)",
        "itens": [
            {"produto": "Roundup Original Mais", "dose": 2, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "LI 700", "dose": 50, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Cofenrin", "dose": 100, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Verdict Ultra", "dose": 400, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Prisma Plus", "dose": 300, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Vessarya", "dose": 400, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Nitro Dry", "dose": 1, "unidade": "kg", "base": "ha", "formulacao": None},
        ],
        "ordem_esperada_parcial": {
            "Cofenrin": 11, "Prisma Plus": 11, "Vessarya": 11, "Verdict Ultra": 11,
            "Roundup Original Mais": 16, "LI 700": 2, "Nitro Dry": 18,
        },
    },
    {
        "nome": "Calda fungicida milho",
        "itens": [
            {"produto": "Score", "dose": 0.5, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Nimbus", "dose": 0.5, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Engeo Pleno S", "dose": 200, "unidade": "mL", "base": "ha", "formulacao": None},
        ],
        "ordem_esperada_parcial": {
            "Engeo Pleno S": 8,
            "Nimbus": 12,
        },
    },
    {
        "nome": "Calda com formulação no nome (IA extrai sigla)",
        "itens": [
            {"produto": "Score 250 EC", "dose": 0.5, "unidade": "L", "base": "ha", "formulacao": "EC"},
            {"produto": "Elatus Easy", "dose": 300, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Nimbus", "dose": 0.6, "unidade": "L", "base": "ha", "formulacao": None},
        ],
        "ordem_esperada_parcial": {
            "Elatus Easy": 6,
            "Nimbus": 12,
        },
    },
]


def testar():
    total_ok = 0
    total_falha = 0

    for calda in CALDAS:
        print(f"\n{'='*60}")
        print(f"TESTE: {calda['nome']}")
        print(f"{'='*60}")

        ordenados = ordenar_itens(calda["itens"])
        print(f"Ordem de adição:")
        erros = []
        for i, it in enumerate(ordenados, 1):
            form = it.get("formulacao", "?")
            pos = it.get("posicao", "?")
            dose_txt = f"{it.get('dose', '?')} {it.get('unidade', '?')}/{it.get('base', 'ha')}"
            alert = ""
            if it.get("alerta_prediluicao"):
                alert = f"\n      >> {it['alerta_prediluicao']}"
            pendente = " [pendente]" if it.get("pendente") else ""
            print(f"  {i}. [pos {pos}] {it['produto']} ({form}) — {dose_txt}{pendente}{alert}")

            esperada = calda["ordem_esperada_parcial"].get(it["produto"])
            if esperada is not None and pos != esperada:
                erros.append(f"  {it['produto']}: esperava pos {esperada}, recebeu {pos}")

        if erros:
            print(f"\nERROS DE POSIÇÃO:")
            for e in erros:
                print(e)
            total_falha += 1
        else:
            print(f"\nPosições conferem OK")
            total_ok += 1

    print(f"\n{'='*60}")
    print(f"RESULTADO: {total_ok} OK, {total_falha} falhas de {len(CALDAS)} testes")
    print(f"{'='*60}")
    return total_falha == 0


if __name__ == "__main__":
    ok = testar()
    sys.exit(0 if ok else 1)
