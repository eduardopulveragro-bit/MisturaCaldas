"""CRUD de histórico de caldas — Supabase."""
import os
import uuid
from datetime import datetime

import requests

_SUPA_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SUPA_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
_USA_SUPABASE = bool(_SUPA_URL and _SUPA_KEY)


def _headers():
    return {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def listar(usuario_id: str) -> list[dict]:
    if not _USA_SUPABASE:
        return []
    r = requests.get(
        f"{_SUPA_URL}/rest/v1/historico_caldas"
        f"?usuario_id=eq.{usuario_id}"
        f"&order=data_aplicacao.desc,criado_em.desc"
        f"&select=*",
        headers=_headers(), timeout=10,
    )
    r.raise_for_status()
    return r.json()


def criar(dados: dict) -> dict:
    if not _USA_SUPABASE:
        return {}
    row = {
        "id": str(uuid.uuid4()),
        "usuario_id": dados["usuario_id"],
        "data_aplicacao": dados.get("data_aplicacao") or datetime.now().strftime("%Y-%m-%d"),
        "cultura": (dados.get("cultura") or "").strip(),
        "talhao": (dados.get("talhao") or "").strip(),
        "area_ha": _float_ou_none(dados.get("area_ha")),
        "vazao_L_ha": _float_ou_none(dados.get("vazao_L_ha")),
        "produtos": dados.get("produtos"),
        "operacao": dados.get("operacao"),
        "temp_amb": _float_ou_none(dados.get("temp_amb")),
        "rh_amb": _float_ou_none(dados.get("rh_amb")),
        "delta_t": _float_ou_none(dados.get("delta_t")),
        "notas": (dados.get("notas") or "").strip(),
        "criado_em": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    r = requests.post(
        f"{_SUPA_URL}/rest/v1/historico_caldas",
        headers=_headers(), json=row, timeout=10,
    )
    r.raise_for_status()
    return r.json()[0]


def excluir(historico_id: str, usuario_id: str) -> bool:
    if not _USA_SUPABASE:
        return False
    r = requests.delete(
        f"{_SUPA_URL}/rest/v1/historico_caldas"
        f"?id=eq.{historico_id}&usuario_id=eq.{usuario_id}",
        headers={**_headers(), "Prefer": "return=minimal"}, timeout=10,
    )
    r.raise_for_status()
    return True


def _float_ou_none(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except (ValueError, TypeError):
        return None
