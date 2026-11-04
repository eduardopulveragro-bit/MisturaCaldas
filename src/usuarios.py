"""CRUD de usuários via Supabase."""
import os

import requests
from werkzeug.security import check_password_hash, generate_password_hash

_SUPA_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SUPA_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _disponivel() -> bool:
    return bool(_SUPA_URL and _SUPA_KEY)


def _headers() -> dict:
    return {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def buscar_por_email(email: str) -> dict | None:
    if not _disponivel():
        return None
    r = requests.get(
        f"{_SUPA_URL}/rest/v1/usuarios?email=eq.{email.lower().strip()}&select=*",
        headers=_headers(), timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def buscar_por_id(user_id: str) -> dict | None:
    if not _disponivel():
        return None
    r = requests.get(
        f"{_SUPA_URL}/rest/v1/usuarios?id=eq.{user_id}&select=*",
        headers=_headers(), timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def listar() -> list[dict]:
    if not _disponivel():
        return []
    r = requests.get(
        f"{_SUPA_URL}/rest/v1/usuarios?select=*&order=criado_em.asc",
        headers=_headers(), timeout=10,
    )
    r.raise_for_status()
    return r.json()


def contar() -> int:
    if not _disponivel():
        return 0
    r = requests.get(
        f"{_SUPA_URL}/rest/v1/usuarios?select=id",
        headers={**_headers(), "Prefer": "count=exact"}, timeout=10,
    )
    r.raise_for_status()
    content_range = r.headers.get("content-range", "0/0")
    try:
        return int(content_range.split("/")[-1])
    except (ValueError, IndexError):
        return len(r.json())


def criar(email: str, nome: str, senha: str, admin: bool = False) -> dict:
    row = {
        "email": email.lower().strip(),
        "nome": nome.strip(),
        "password_hash": generate_password_hash(senha),
        "ativo": True,
        "admin": admin,
        "plano": "trial",
    }
    r = requests.post(
        f"{_SUPA_URL}/rest/v1/usuarios",
        headers=_headers(), json=row, timeout=10,
    )
    r.raise_for_status()
    return r.json()[0]


def verificar_senha(email: str, senha: str) -> dict | None:
    usuario = buscar_por_email(email)
    if not usuario or not usuario.get("ativo"):
        return None
    if check_password_hash(usuario["password_hash"], senha):
        return usuario
    return None


def atualizar_ativo(user_id: str, ativo: bool) -> None:
    requests.patch(
        f"{_SUPA_URL}/rest/v1/usuarios?id=eq.{user_id}",
        headers={**_headers(), "Prefer": "return=minimal"},
        json={"ativo": ativo}, timeout=10,
    ).raise_for_status()
