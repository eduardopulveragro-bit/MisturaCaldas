"""CRUD de histórico de caldas — Supabase."""
import os
import uuid
from datetime import datetime

import requests


def _disponivel() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def _headers():
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _url(path: str = "") -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/") + path


def listar(usuario_id: str, cliente_id: str | None = None) -> list[dict]:
    if not _disponivel():
        return []
    filtro = f"usuario_id=eq.{usuario_id}"
    if cliente_id:
        filtro += f"&cliente_id=eq.{cliente_id}"
    r = requests.get(
        _url("/rest/v1/historico_caldas")
        + f"?{filtro}"
        + "&order=data_aplicacao.desc,criado_em.desc"
        + "&select=*",
        headers=_headers(), timeout=10,
    )
    r.raise_for_status()
    return r.json()


def criar(dados: dict) -> dict:
    if not _disponivel():
        raise RuntimeError("Supabase não configurado — histórico não disponível")
    row = {
        "id": str(uuid.uuid4()),
        "usuario_id": dados["usuario_id"],
        "data_aplicacao": dados.get("data_aplicacao") or datetime.now().strftime("%Y-%m-%d"),
        "cultura": (dados.get("cultura") or "").strip(),
        "talhao": (dados.get("talhao") or "").strip(),
        "area_ha": _float_ou_none(dados.get("area_ha")),
        "vazao_l_ha": _float_ou_none(dados.get("vazao_L_ha") or dados.get("vazao_l_ha")),
        "produtos": dados.get("produtos"),
        "operacao": dados.get("operacao"),
        "temp_amb": _float_ou_none(dados.get("temp_amb")),
        "rh_amb": _float_ou_none(dados.get("rh_amb")),
        "delta_t": _float_ou_none(dados.get("delta_t")),
        "notas": (dados.get("notas") or "").strip(),
    }
    if dados.get("cliente_id"):
        row["cliente_id"] = dados["cliente_id"]
    if dados.get("criado_em"):
        row["criado_em"] = dados["criado_em"]
    r = requests.post(
        _url("/rest/v1/historico_caldas"),
        headers=_headers(), json=row, timeout=10,
    )
    if not r.ok:
        import logging as _log
        _log.getLogger(__name__).error("historico criar %s: %s", r.status_code, r.text)
        raise RuntimeError(f"Supabase {r.status_code}: {r.text}")
    return r.json()[0]


def excluir(historico_id: str, usuario_id: str) -> bool:
    if not _disponivel():
        return False
    r = requests.delete(
        _url("/rest/v1/historico_caldas")
        + f"?id=eq.{historico_id}&usuario_id=eq.{usuario_id}",
        headers={**_headers(), "Prefer": "return=minimal"}, timeout=10,
    )
    r.raise_for_status()
    return True


def listar_todos(limit: int = 200) -> list[dict]:
    """Retorna todas as caldas de todos os usuários (uso admin)."""
    if not _disponivel():
        return []
    r = requests.get(
        _url("/rest/v1/historico_caldas")
        + f"?order=criado_em.desc&limit={limit}"
        + "&select=*",
        headers=_headers(), timeout=15,
    )
    r.raise_for_status()
    return r.json()


def contar_todos() -> dict:
    """Retorna {usuario_id: count} para todos os usuários."""
    if not _disponivel():
        return {}
    r = requests.get(
        _url("/rest/v1/historico_caldas?select=usuario_id"),
        headers=_headers(), timeout=15,
    )
    r.raise_for_status()
    contagem: dict = {}
    for row in r.json():
        uid = row.get("usuario_id")
        if uid:
            contagem[uid] = contagem.get(uid, 0) + 1
    return contagem


def migrar_tabela() -> dict:
    """Adiciona colunas que podem estar ausentes em tabelas criadas antes dessas features."""
    if not _disponivel():
        return {"status": 503, "body": "Supabase não configurado"}
    sql = """
    ALTER TABLE historico_caldas
      ADD COLUMN IF NOT EXISTS operacao jsonb,
      ADD COLUMN IF NOT EXISTS temp_amb float,
      ADD COLUMN IF NOT EXISTS rh_amb float,
      ADD COLUMN IF NOT EXISTS delta_t float,
      ADD COLUMN IF NOT EXISTS notas text NOT NULL DEFAULT '',
      ADD COLUMN IF NOT EXISTS talhao text NOT NULL DEFAULT '';
    """
    r = requests.post(
        _url("/rest/v1/rpc/exec_sql"),
        headers={**_headers(), "Prefer": ""},
        json={"query": sql},
        timeout=15,
    )
    return {"status": r.status_code, "body": r.text}


def criar_tabela() -> dict:
    """Cria a tabela historico_caldas no Supabase via SQL (uso único no /init-db-historico)."""
    if not _disponivel():
        return {"status": 503, "body": "Supabase não configurado"}
    sql = """
    CREATE TABLE IF NOT EXISTS historico_caldas (
      id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
      usuario_id uuid NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
      cliente_id uuid REFERENCES clientes(id) ON DELETE SET NULL,
      data_aplicacao date NOT NULL DEFAULT CURRENT_DATE,
      cultura text NOT NULL DEFAULT '',
      talhao text NOT NULL DEFAULT '',
      area_ha float,
      vazao_l_ha float,
      produtos jsonb,
      operacao jsonb,
      temp_amb float,
      rh_amb float,
      delta_t float,
      notas text NOT NULL DEFAULT '',
      criado_em timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS historico_caldas_usuario_idx ON historico_caldas(usuario_id);
    CREATE INDEX IF NOT EXISTS historico_caldas_data_idx ON historico_caldas(data_aplicacao DESC);
    """
    r = requests.post(
        _url("/rest/v1/rpc/exec_sql"),
        headers={**_headers(), "Prefer": ""},
        json={"query": sql},
        timeout=15,
    )
    return {"status": r.status_code, "body": r.text}


def _float_ou_none(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except (ValueError, TypeError):
        return None
