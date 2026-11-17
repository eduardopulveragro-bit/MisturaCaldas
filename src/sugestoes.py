"""Sugestões de produtos feitas pelos usuários via seleção manual de formulação."""
import os
import requests
from datetime import datetime, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def _url(path: str) -> str:
    return SUPABASE_URL + path


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _disponivel() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def registrar(nome: str, formulacao: str, usuario_id: str) -> None:
    """Registra sugestão. Incrementa contador se mesmo produto+formulação já existe pendente."""
    if not _disponivel():
        return
    try:
        import urllib.parse
        q = f"?nome=eq.{urllib.parse.quote(nome)}&formulacao=eq.{formulacao}&status=eq.pendente&select=id,vezes_sugerido,usuario_ids"
        r = requests.get(_url("/rest/v1/produtos_sugeridos") + q, headers=_headers(), timeout=10)
        rows = r.json() if r.ok else []
        if rows:
            row = rows[0]
            ids = row.get("usuario_ids") or []
            if usuario_id not in ids:
                ids.append(usuario_id)
            requests.patch(
                _url(f"/rest/v1/produtos_sugeridos?id=eq.{row['id']}"),
                json={"vezes_sugerido": row["vezes_sugerido"] + 1, "usuario_ids": ids},
                headers={**_headers(), "Prefer": "return=minimal"},
                timeout=10,
            )
        else:
            requests.post(
                _url("/rest/v1/produtos_sugeridos"),
                json={
                    "nome": nome,
                    "formulacao": formulacao.upper(),
                    "vezes_sugerido": 1,
                    "usuario_ids": [usuario_id],
                    "status": "pendente",
                },
                headers=_headers(),
                timeout=10,
            )
    except Exception:
        pass


def listar_pendentes() -> list[dict]:
    if not _disponivel():
        return []
    try:
        r = requests.get(
            _url("/rest/v1/produtos_sugeridos?status=eq.pendente&order=vezes_sugerido.desc,criado_em.desc"),
            headers=_headers(),
            timeout=10,
        )
        return r.json() if r.ok else []
    except Exception:
        return []


def atualizar_status(sugestao_id: str, status: str) -> None:
    if not _disponivel():
        return
    try:
        requests.patch(
            _url(f"/rest/v1/produtos_sugeridos?id=eq.{sugestao_id}"),
            json={"status": status},
            headers={**_headers(), "Prefer": "return=minimal"},
            timeout=10,
        )
    except Exception:
        pass


def criar_tabela() -> dict:
    """Testa a tabela inserindo e deletando um registro de teste."""
    if not _disponivel():
        return {"status": 503, "body": "Supabase não configurado"}
    # Tenta um GET simples para verificar se a tabela existe
    r = requests.get(
        _url("/rest/v1/produtos_sugeridos?limit=1"),
        headers=_headers(),
        timeout=10,
    )
    if r.status_code == 200:
        return {"status": 200, "body": "Tabela produtos_sugeridos já existe e está acessível."}
    return {
        "status": r.status_code,
        "body": f"Tabela não acessível: {r.text}\n\nCrie manualmente no Supabase SQL Editor:\n\nCREATE TABLE produtos_sugeridos (\n  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,\n  nome text NOT NULL,\n  formulacao text NOT NULL,\n  vezes_sugerido int NOT NULL DEFAULT 1,\n  usuario_ids jsonb NOT NULL DEFAULT '[]',\n  status text NOT NULL DEFAULT 'pendente',\n  criado_em timestamptz NOT NULL DEFAULT now()\n);"
    }
