"""CRUD de clientes — armazena em data/clientes.json."""
import json
import os
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
_SOURCE_ARQUIVO = DATA_DIR / "clientes.json"

_ON_VERCEL = bool(os.environ.get("VERCEL"))
if _ON_VERCEL:
    _TMP_DIR = Path("/tmp")
    ARQUIVO = _TMP_DIR / "clientes.json"
    _LOCK = _TMP_DIR / "clientes.lock"
else:
    ARQUIVO = _SOURCE_ARQUIVO
    _LOCK = DATA_DIR / "clientes.lock"


def _seed_tmp():
    """Copy bundled clientes.json to /tmp on Vercel cold start."""
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
    """Lock simples via arquivo para evitar escritas concorrentes."""
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


def listar() -> list[dict]:
    return _carregar()


def buscar(cliente_id: str) -> dict | None:
    for c in _carregar():
        if c["id"] == cliente_id:
            return c
    return None


def criar(dados: dict) -> dict:
    with _lock_clientes():
        clientes = _carregar()
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
        clientes.append(cliente)
        _salvar(clientes)
        return cliente


def atualizar(cliente_id: str, dados: dict) -> dict | None:
    with _lock_clientes():
        clientes = _carregar()
        for c in clientes:
            if c["id"] == cliente_id:
                c["nome"] = (dados.get("nome") or "").strip()
                c["pulverizador"] = {
                    "modelo": (dados.get("pulverizador_modelo") or "").strip(),
                    "volume_tanque_L": _float_ou_none(dados.get("volume_tanque")),
                }
                c["vazao_L_ha"] = _float_ou_none(dados.get("vazao"))
                c["area_tanque_ha"] = _float_ou_none(dados.get("area_tanque"))
                c["pontas"] = _parse_pontas(dados.get("pontas", ""))
                c["calibracao"] = (dados.get("calibracao") or "").strip()
                c["observacao"] = (dados.get("observacao") or "").strip()
                _salvar(clientes)
                return c
        return None


def excluir(cliente_id: str) -> bool:
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
