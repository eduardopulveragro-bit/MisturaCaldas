"""CRUD de clientes — armazena em data/clientes.json."""
import json
import uuid
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
ARQUIVO = DATA_DIR / "clientes.json"


def _carregar() -> list[dict]:
    if not ARQUIVO.exists():
        return []
    with open(ARQUIVO, encoding="utf-8") as f:
        return json.load(f)


def _salvar(clientes: list[dict]):
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(clientes, f, ensure_ascii=False, indent=2)


def listar() -> list[dict]:
    return _carregar()


def buscar(cliente_id: str) -> dict | None:
    for c in _carregar():
        if c["id"] == cliente_id:
            return c
    return None


def criar(dados: dict) -> dict:
    clientes = _carregar()
    cliente = {
        "id": uuid.uuid4().hex[:12],
        "nome": dados["nome"].strip(),
        "pulverizador": {
            "modelo": (dados.get("pulverizador_modelo") or "").strip(),
            "volume_tanque_L": _float_ou_none(dados.get("volume_tanque")),
            "faixa_m": _float_ou_none(dados.get("faixa")),
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
    clientes = _carregar()
    for c in clientes:
        if c["id"] == cliente_id:
            c["nome"] = dados["nome"].strip()
            c["pulverizador"] = {
                "modelo": (dados.get("pulverizador_modelo") or "").strip(),
                "volume_tanque_L": _float_ou_none(dados.get("volume_tanque")),
                "faixa_m": _float_ou_none(dados.get("faixa")),
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
