"""Teste direto da chave API — roda fora do Flask para isolar o problema."""
from pathlib import Path
from dotenv import load_dotenv
import os

env_path = Path(__file__).parent / ".env"
print(f"Arquivo .env: {env_path}")
print(f"Existe: {env_path.exists()}")

load_dotenv(env_path)

chave = os.environ.get("ANTHROPIC_API_KEY", "")
print(f"Chave carregada: {chave[:15]}...{chave[-5:]} ({len(chave)} chars)")

if not chave or chave == "sk-ant-sua-chave-aqui":
    print("ERRO: chave não configurada")
    exit(1)

import anthropic
cliente = anthropic.Anthropic(api_key=chave)

try:
    resp = cliente.messages.create(
        model="claude-haiku-5-5",
        max_tokens=10,
        messages=[{"role": "user", "content": "Diga apenas: OK"}],
    )
    print(f"SUCESSO: {resp.content[0].text}")
except anthropic.AuthenticationError as e:
    print(f"ERRO DE AUTENTICAÇÃO: {e}")
    print("Verifique se a chave é válida em console.anthropic.com")
    print("Verifique se a conta tem crédito/billing ativo")
except Exception as e:
    print(f"OUTRO ERRO: {type(e).__name__}: {e}")
