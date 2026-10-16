"""CRUD de clientes — persiste no Supabase (produção) ou JSON local (dev)."""
import json
import os
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
_SOURCE_ARQUIVO = DATA_DIR / "clientes.json"

_ON_VERCEL = bool(os.environ.get("VERCEL"))
_SUPA_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_SUPA_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
_USA_SUPABASE = bool(_SUPA_URL and _SUPA_KEY)

# Fallback local (dev sem Supabase)
if _ON_VERCEL:
    _TMP_DIR = Path("/tmp")
    ARQUIVO = _TMP_DIR / "clientes.json"
    _LOCK = _TMP_DIR / "clientes.lock"
else:
    ARQUIVO = _SOURCE_ARQUIVO
    _LOCK = DATA_DIR / "clientes.lock"


# ── Supabase REST helpers ────────────────────────────────────────────────────

def _headers():
    return {
        "apikey": _SUPA_KEY,
        "Authorization": f"Bearer {_SUPA_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _supa_listar() -> list[dict]:
    r = requests.get(
        f"{_SUPA_URL}/rest/v1/clientes?select=*&order=criado_em.asc",
        headers=_headers(), timeout=10
    )
    r.raise_for_status()
    return [_row_para_cliente(row) for row in r.json()]


def _supa_buscar(cliente_id: str) -> dict | None:
    r = requests.get(
        f"{_SUPA_URL}/rest/v1/clientes?id=eq.{cliente_id}&select=*",
        headers=_headers(), timeout=10
    )
    r.raise_for_status()
    rows = r.json()
    return _row_para_cliente(rows[0]) if rows else None


def _supa_criar(cliente: dict) -> dict:
    row = _cliente_para_row(cliente)
    r = requests.post(
        f"{_SUPA_URL}/rest/v1/clientes",
        headers=_headers(), json=row, timeout=10
    )
    r.raise_for_status()
    return _row_para_cliente(r.json()[0])


def _supa_atualizar(cliente_id: str, cliente: dict) -> dict | None:
    row = _cliente_para_row(cliente)
    row.pop("id", None)
    row.pop("criado_em", None)
    r = requests.patch(
        f"{_SUPA_URL}/rest/v1/clientes?id=eq.{cliente_id}",
        headers=_headers(), json=row, timeout=10
    )
    r.raise_for_status()
    rows = r.json()
    return _row_para_cliente(rows[0]) if rows else None


def _supa_excluir(cliente_id: str) -> bool:
    r = requests.delete(
        f"{_SUPA_URL}/rest/v1/clientes?id=eq.{cliente_id}",
        headers={**_headers(), "Prefer": "return=minimal"}, timeout=10
    )
    r.raise_for_status()
    return True


def _row_para_cliente(row: dict) -> dict:
    dados = row.get("dados") or {}
    if isinstance(dados, str):
        dados = json.loads(dados)
    return {"id": row["id"], "nome": row["nome"], "criado_em": row.get("criado_em", ""), **dados}


def _cliente_para_row(cliente: dict) -> dict:
    dados = {k: v for k, v in cliente.items() if k not in ("id", "nome", "criado_em")}
    return {"id": cliente["id"], "nome": cliente["nome"], "dados": dados, "criado_em": cliente.get("criado_em", "")}


# ── Fallback JSON local ──────────────────────────────────────────────────────

def _seed_tmp():
    if _ON_VERCEL and not ARQUIVO.exists() and _SOURCE_ARQUIVO.exists():
        shutil.copy2(_SOURCE_ARQUIVO, ARQUIVO)


def _carregar() -> list[dict]:
    _seed_tmp()
    if not ARQUIVO.exists():
        return []
    with open(ARQUIVO, encoding="utf-8") as f:
        return json.load(f)


def _salvar(clientes: list[dict]):
    _seed_tmp()
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(clientes, f, ensure_ascii=False, indent=2)


@contextmanager
def _lock_clientes():
    fd = os.open(str(_LOCK), os.O_CREAT | os.O_WRONLY)
    try:
        try:
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except (ImportError, OSError):
            try:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            except ImportError:
                pass
        yield
    finally:
        os.close(fd)


# ── API pública ──────────────────────────────────────────────────────────────

def listar() -> list[dict]:
    if _USA_SUPABASE:
        return _supa_listar()
    return _carregar()


def buscar(cliente_id: str) -> dict | None:
    if _USA_SUPABASE:
        return _supa_buscar(cliente_id)
    for c in _carregar():
        if c["id"] == cliente_id:
            return c
    return None


def criar(dados: dict) -> dict:
    cliente = {
        "id": uuid.uuid4().hex[:12],
        "nome": (dados.get("nome") or "").strip(),
        "pulverizador": {
            "modelo": (dados.get("pulverizador_modelo") or "").strip(),
            "volume_tanque_L": _float_ou_none(dados.get("volume_tanque")),
        },
        "vazao_L_ha": _float_ou_none(dados.get("vazao")),
        "area_tanque_ha": _float_ou_none(dados.get("area_tanque")),
        "pontas": _parse_pontas(dados.get("pontas", "")),
        "calibracao": (dados.get("calibracao") or "").strip(),
        "observacao": (dados.get("observacao") or "").strip(),
        "criado_em": datetime.now().strftime("%Y-%m-%d"),
    }
    if _USA_SUPABASE:
        return _supa_criar(cliente)
    with _lock_clientes():
        clientes = _carregar()
        clientes.append(cliente)
        _salvar(clientes)
    return cliente


def atualizar(cliente_id: str, dados: dict) -> dict | None:
    campos = {
        "nome": (dados.get("nome") or "").strip(),
        "pulverizador": {
            "modelo": (dados.get("pulverizador_modelo") or "").strip(),
            "volume_tanque_L": _float_ou_none(dados.get("volume_tanque")),
        },
        "vazao_L_ha": _float_ou_none(dados.get("vazao")),
        "area_tanque_ha": _float_ou_none(dados.get("area_tanque")),
        "pontas": _parse_pontas(dados.get("pontas", "")),
        "calibracao": (dados.get("calibracao") or "").strip(),
        "observacao": (dados.get("observacao") or "").strip(),
    }
    if _USA_SUPABASE:
        existente = _supa_buscar(cliente_id)
        if not existente:
            return None
        return _supa_atualizar(cliente_id, {"id": cliente_id, "criado_em": existente.get("criado_em", ""), **campos})
    with _lock_clientes():
        clientes = _carregar()
        for c in clientes:
            if c["id"] == cliente_id:
                c.update(campos)
                _salvar(clientes)
                return c
    return None


def excluir(cliente_id: str) -> bool:
    if _USA_SUPABASE:
        return _supa_excluir(cliente_id)
    with _lock_clientes():
        clientes = _carregar()
        antes = len(clientes)
        clientes = [c for c in clientes if c["id"] != cliente_id]
        if len(clientes) == antes:
            return False
        _salvar(clientes)
        return True


def _float_ou_none(valor) -> float | None:
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_pontas(texto: str) -> list[str]:
    if not texto:
        return []
    return [p.strip() for p in texto.split(",") if p.strip()]
