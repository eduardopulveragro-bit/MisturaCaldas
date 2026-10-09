"""Script para salvar a chave API sem risco de truncamento."""
import getpass
from pathlib import Path

env = Path(__file__).parent / ".env"
print("Cole sua chave da Anthropic (console.anthropic.com → API Keys)")
print("A chave NÃO aparecerá na tela enquanto você digita/cola.")
print()
chave = getpass.getpass("Chave: ").strip()

if not chave.startswith("sk-ant-"):
    print("AVISO: a chave não começa com 'sk-ant-' — verifique se copiou corretamente.")
else:
    env.write_text(f"ANTHROPIC_API_KEY={chave}\n", encoding="utf-8")
    print(f"Salvo em {env}  ({len(chave)} caracteres)")
