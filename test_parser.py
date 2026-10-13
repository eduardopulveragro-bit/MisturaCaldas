"""
Teste da ordenação com dados simulados (formato do parser enxuto).
Verifica que o motor de ordenação funciona corretamente quando a IA
retorna só nome+dose+unidade (sem formulação), confiando no CSV.
Inclui caldas complexas com regras especiais.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.ordenacao import ordenar_itens

CALDAS = [
    # 1. Calda básica — 7 produtos, sem formulação da IA
    {
        "nome": "Dessecação soja básica",
        "itens": [
            {"produto": "Roundup Original Mais", "dose": 2, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "LI 700", "dose": 50, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Cofenrin", "dose": 100, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Verdict Ultra", "dose": 400, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Prisma Plus", "dose": 300, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Vessarya", "dose": 400, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Nitro Dry", "dose": 1, "unidade": "kg", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "posicoes": {"Cofenrin": 11, "Roundup Original Mais": 16, "LI 700": 2, "Nitro Dry": 18},
        },
    },
    # 2. Glifosato SL + 2,4-D SL — devem ser separados ao máximo
    {
        "nome": "Glifosato + 2,4-D (separação)",
        "itens": [
            {"produto": "Roundup Original Mais", "dose": 3, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "2,4-D", "dose": 1.5, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Nimbus", "dose": 0.5, "unidade": "L", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "separados": ["Roundup Original Mais", "2,4-D"],
        },
    },
    # 3. Glifosato WG + 2,4-D SL — WG cedo, 2,4-D pro final
    {
        "nome": "Glifosato WG + 2,4-D SL (separação invertida)",
        "itens": [
            {"produto": "Roundup WG", "dose": 2.5, "unidade": "kg", "base": "ha", "formulacao": None},
            {"produto": "2,4-D", "dose": 1, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Nimbus", "dose": 0.5, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Score", "dose": 0.3, "unidade": "L", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "posicoes": {"Roundup WG": 6},
            "separados": ["Roundup WG", "2,4-D"],
        },
    },
    # 4. Heat WG — pré-diluir em água, vai logo após condicionador
    {
        "nome": "Heat (pré-diluição em água)",
        "itens": [
            {"produto": "Heat", "dose": 140, "unidade": "g", "base": "ha", "formulacao": None},
            {"produto": "Roundup Original Mais", "dose": 2, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "LI 700", "dose": 50, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Score", "dose": 0.3, "unidade": "L", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "prediluicao": ["Heat"],
            "primeiro_apos_condicionador": "Heat",
        },
    },
    # 5. Cletodim + óleo — devem pré-diluir juntos
    {
        "nome": "Cletodim + óleo (pré-diluição conjunta)",
        "itens": [
            {"produto": "Select", "dose": 400, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Nimbus", "dose": 0.5, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Roundup Original Mais", "dose": 2, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "LI 700", "dose": 50, "unidade": "mL", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "prediluicao": ["Select", "Nimbus"],
            "adjacentes": ["Select", "Nimbus"],
        },
    },
    # 6. Abamectina + óleo — devem pré-diluir juntos
    {
        "nome": "Abamectina + óleo (pré-diluição conjunta)",
        "itens": [
            {"produto": "Abamectina", "dose": 1, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Nimbus", "dose": 0.8, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Score", "dose": 0.3, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "LI 700", "dose": 50, "unidade": "mL", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "prediluicao": ["Abamectina", "Nimbus"],
            "adjacentes": ["Abamectina", "Nimbus"],
        },
    },
    # 7. Mancozeb WP + óleo de laranja — óleo de laranja vai pro começo
    {
        "nome": "Mancozeb + óleo de laranja (regra especial)",
        "itens": [
            {"produto": "Mancozeb", "dose": 2, "unidade": "kg", "base": "ha", "formulacao": None},
            {"produto": "Terpen", "dose": 30, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Score", "dose": 0.3, "unidade": "L", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "posicoes": {"Mancozeb": 5},
            "terpen_antes_mancozeb": True,
        },
    },
    # 8. Calda grande — muitas formulações misturadas
    {
        "nome": "Calda complexa 10 produtos",
        "itens": [
            {"produto": "LI 700", "dose": 50, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Elatus Easy", "dose": 300, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Engeo Pleno S", "dose": 200, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Fuse", "dose": 1, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Score", "dose": 0.3, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Nimbus", "dose": 0.5, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Roundup Original Mais", "dose": 2, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "2,4-D", "dose": 1.5, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Nitro Dry", "dose": 1, "unidade": "kg", "base": "ha", "formulacao": None},
            {"produto": "Cofenrin", "dose": 100, "unidade": "mL", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "posicoes": {
                "LI 700": 2, "Elatus Easy": 6, "Engeo Pleno S": 8,
                "Fuse": 9, "Cofenrin": 11, "Nimbus": 12,
                "Nitro Dry": 18,
            },
            "separados": ["Roundup Original Mais", "2,4-D"],
        },
    },
    # 9. Haloxifop (Verdict) + óleo — pré-diluição
    {
        "nome": "Verdict + óleo (pré-diluição haloxifop)",
        "itens": [
            {"produto": "Verdict Ultra", "dose": 400, "unidade": "mL", "base": "ha", "formulacao": None},
            {"produto": "Nimbus", "dose": 0.5, "unidade": "L", "base": "ha", "formulacao": None},
            {"produto": "Roundup Original Mais", "dose": 2, "unidade": "L", "base": "ha", "formulacao": None},
        ],
        "checks": {
            "prediluicao": ["Verdict Ultra", "Nimbus"],
            "adjacentes": ["Verdict Ultra", "Nimbus"],
        },
    },
]


def _nome_match(nome_busca, nome_item):
    return nome_busca.lower() in nome_item.lower() or nome_item.lower() in nome_busca.lower()


def _find_idx(ordenados, nome):
    for i, it in enumerate(ordenados):
        if _nome_match(nome, it["produto"]):
            return i
    return -1


def verificar_checks(ordenados, checks):
    erros = []

    if "posicoes" in checks:
        for nome, pos_esperada in checks["posicoes"].items():
            idx = _find_idx(ordenados, nome)
            if idx == -1:
                erros.append(f"  {nome}: não encontrado na saída")
            elif ordenados[idx]["posicao"] != pos_esperada:
                erros.append(f"  {nome}: esperava pos {pos_esperada}, recebeu {ordenados[idx]['posicao']}")

    if "prediluicao" in checks:
        for nome in checks["prediluicao"]:
            idx = _find_idx(ordenados, nome)
            if idx == -1:
                erros.append(f"  {nome}: não encontrado")
            elif not ordenados[idx].get("alerta_prediluicao"):
                erros.append(f"  {nome}: deveria ter alerta de pré-diluição")

    if "adjacentes" in checks:
        nomes = checks["adjacentes"]
        indices = [_find_idx(ordenados, n) for n in nomes]
        if -1 not in indices and abs(indices[0] - indices[1]) != 1:
            erros.append(f"  {nomes[0]} e {nomes[1]}: deveriam estar adjacentes (posições {indices[0]} e {indices[1]})")

    if "separados" in checks:
        nomes = checks["separados"]
        indices = [_find_idx(ordenados, n) for n in nomes]
        if -1 not in indices and abs(indices[0] - indices[1]) <= 1:
            erros.append(f"  {nomes[0]} e {nomes[1]}: deveriam estar SEPARADOS (posições {indices[0]} e {indices[1]})")

    if checks.get("primeiro_apos_condicionador"):
        nome = checks["primeiro_apos_condicionador"]
        idx_heat = _find_idx(ordenados, nome)
        if idx_heat == -1:
            erros.append(f"  {nome}: não encontrado")
        else:
            ultimo_cond = -1
            for i, it in enumerate(ordenados):
                if it["posicao"] <= 2:
                    ultimo_cond = i
            if idx_heat != ultimo_cond + 1:
                erros.append(f"  {nome}: deveria estar logo após condicionador (pos {ultimo_cond+1}), está em {idx_heat}")

    if checks.get("terpen_antes_mancozeb"):
        idx_terpen = _find_idx(ordenados, "Terpen")
        idx_mancozeb = _find_idx(ordenados, "Mancozeb")
        if idx_terpen != -1 and idx_mancozeb != -1 and idx_terpen >= idx_mancozeb:
            erros.append(f"  Terpen (idx {idx_terpen}) deveria vir ANTES do Mancozeb (idx {idx_mancozeb})")

    if checks.get("ordem_crescente_geral"):
        posicoes = [it["posicao"] for it in ordenados]
        for i in range(len(posicoes) - 1):
            if posicoes[i] > posicoes[i + 1]:
                n1 = ordenados[i]["produto"]
                n2 = ordenados[i + 1]["produto"]
                erros.append(f"  Ordem quebrada: {n1} (pos {posicoes[i]}) antes de {n2} (pos {posicoes[i+1]})")
                break

    return erros


def testar():
    total_ok = 0
    total_falha = 0

    for calda in CALDAS:
        print(f"\n{'='*60}")
        print(f"TESTE: {calda['nome']}")
        print(f"{'='*60}")

        ordenados = ordenar_itens(calda["itens"])
        print(f"Ordem de adição:")
        for i, it in enumerate(ordenados, 1):
            form = it.get("formulacao", "?")
            pos = it.get("posicao", "?")
            dose_txt = f"{it.get('dose', '?')} {it.get('unidade', '?')}/{it.get('base', 'ha')}"
            alert = ""
            if it.get("alerta_prediluicao"):
                alert = f"\n      >> {it['alerta_prediluicao']}"
            pendente = " [pendente]" if it.get("pendente") else ""
            print(f"  {i}. [pos {pos}] {it['produto']} ({form}) — {dose_txt}{pendente}{alert}")

        erros = verificar_checks(ordenados, calda["checks"])
        if erros:
            print(f"\nFALHAS:")
            for e in erros:
                print(e)
            total_falha += 1
        else:
            print(f"\nOK")
            total_ok += 1

    print(f"\n{'='*60}")
    print(f"RESULTADO: {total_ok} OK, {total_falha} falhas de {len(CALDAS)} testes")
    print(f"{'='*60}")
    return total_falha == 0


if __name__ == "__main__":
    ok = testar()
    sys.exit(0 if ok else 1)
