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


def atualizar_onboarding(user_id: str, tipo: str, config_equipamento=None) -> bool:
    payload: dict = {"tipo": tipo, "onboarding_completo": True}
    try:
        r = requests.patch(
            f"{_SUPA_URL}/rest/v1/usuarios?id=eq.{user_id}",
            headers={**_headers(), "Prefer": "return=minimal"},
            json=payload, timeout=10,
        )
        if not r.ok:
            import logging
            logging.getLogger(__name__).error("atualizar_onboarding falhou: %s %s", r.status_code, r.text)
            return False
        r.raise_for_status()
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("atualizar_onboarding exception: %s", e)
        return False


def migrar_tabela() -> dict:
    """Adiciona colunas tipo e onboarding_completo se ainda não existirem."""
    if not _disponivel():
        return {"status": 503, "body": "Supabase não configurado"}
    sql = """
    ALTER TABLE usuarios
      ADD COLUMN IF NOT EXISTS tipo text NOT NULL DEFAULT 'produtor',
      ADD COLUMN IF NOT EXISTS onboarding_completo boolean NOT NULL DEFAULT false;
    """
    headers_pg = {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
        "Content-Type": "application/json",
    }
    r = requests.post(
        f"{_SUPA_URL}/pg/query",
        headers=headers_pg,
        json={"query": sql},
        timeout=15,
    )
    return {"status": r.status_code, "body": r.text}


def criar_tabela() -> dict:
    """Cria a tabela usuarios via API pg-meta do Supabase (uso único no /init-db)."""
    sql = """
    CREATE TABLE IF NOT EXISTS usuarios (
      id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
      email text UNIQUE NOT NULL,
      nome text NOT NULL,
      password_hash text NOT NULL,
      ativo boolean DEFAULT true,
      admin boolean DEFAULT false,
      tipo text NOT NULL DEFAULT 'produtor',
      onboarding_completo boolean NOT NULL DEFAULT false,
      plano text DEFAULT 'trial',
      criado_em timestamptz DEFAULT now()
    );
    """
    headers_pg = {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
        "Content-Type": "application/json",
    }
    r = requests.post(
        f"{_SUPA_URL}/pg/query",
        headers=headers_pg,
        json={"query": sql},
        timeout=15,
    )
    return {"status": r.status_code, "body": r.text}
