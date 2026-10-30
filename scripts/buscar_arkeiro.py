"""Script pontual: busca Arkeiro via IA e salva em produtos.csv se encontrado."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from src.busca_produto import buscar_produto_ia, salvar_produto

nome = "Arkeiro"
print(f"Buscando '{nome}'...")
dados = buscar_produto_ia(nome)

if not dados:
    print("IA não encontrou o produto ou confiança baixa.")
    sys.exit(1)

print(f"\nEncontrado:")
print(f"  Nome completo : {dados.get('nome_completo')}")
print(f"  Classe        : {dados.get('classe')}")
print(f"  Formulação    : {dados.get('formulacao')}")
print(f"  Posição       : {dados.get('posicao')}")
print(f"  Ingrediente   : {dados.get('ingrediente_ativo')}")
print(f"  Registro MAPA : {dados.get('registro_mapa')}")
print(f"  Confiança     : {dados.get('confianca')}")

produto = salvar_produto(nome, dados)
print(f"\nSalvo em produtos.csv: posicao={produto['posicao']}, formulacao={produto['formulacao']}")
