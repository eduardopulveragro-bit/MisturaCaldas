"""Flask app — interface web na porta 3002."""
import json as _json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user

_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH, override=True)

from src.parser import extrair_itens
from src.ordenacao import ordenar_itens
from src.operacao import extrair_operacao, calcular_totais_tanque
from src.alertas_incompatibilidade import verificar_incompatibilidades
from src import clientes as clientes_mod
from src import usuarios as usuarios_mod

_handlers = [logging.StreamHandler()]
if os.path.isdir("logs"):
    _handlers.append(logging.FileHandler("logs/app.log", encoding="utf-8"))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-troque-em-producao")

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = ""


class User(UserMixin):
    def __init__(self, data: dict):
        self.id = data["id"]
        self.email = data["email"]
        self.nome = data.get("nome", "")
        self.admin = data.get("admin", False)


@login_manager.user_loader
def carregar_usuario(user_id: str):
    data = usuarios_mod.buscar_por_id(user_id)
    return User(data) if data else None


@login_manager.unauthorized_handler
def nao_autorizado():
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"erro": "Sessão expirada. Faça login novamente.", "redirect": "/login"}), 401
    return redirect(url_for("login"))


@app.route("/favicon.ico")
def favicon():
    return Response(status=204)


# ── Auth ─────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if usuarios_mod.contar() == 0:
        return redirect(url_for("setup"))
    erro = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        usuario = usuarios_mod.verificar_senha(email, senha)
        if usuario:
            login_user(User(usuario), remember=True)
            return redirect(url_for("index"))
        erro = "Email ou senha incorretos."
    return render_template("login.html", erro=erro)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if usuarios_mod.contar() > 0:
        return redirect(url_for("login"))
    erro = None
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        if not nome or not email or not senha:
            erro = "Preencha todos os campos."
        elif len(senha) < 6:
            erro = "Senha deve ter no mínimo 6 caracteres."
        else:
            try:
                u = usuarios_mod.criar(email, nome, senha, admin=True)
                login_user(User(u), remember=True)
                return redirect(url_for("index"))
            except Exception as e:
                logger.exception("Erro ao criar primeiro admin: %s", e)
                erro = "Erro ao criar usuário. Verifique as configurações do Supabase."
    return render_template("setup.html", erro=erro)


# ── App principal ─────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template("index.html")


# ── Admin usuários ────────────────────────────────────────────────────────────

@app.route("/admin/usuarios")
@login_required
def admin_usuarios():
    if not current_user.admin:
        return redirect(url_for("index"))
    usuarios = usuarios_mod.listar()
    return render_template("admin_usuarios.html", usuarios=usuarios)


@app.route("/admin/usuarios/criar", methods=["POST"])
@login_required
def admin_criar_usuario():
    if not current_user.admin:
        return jsonify({"erro": "Acesso negado"}), 403
    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip()
    senha = request.form.get("senha", "")
    admin = request.form.get("admin") == "on"
    if nome and email and senha:
        try:
            usuarios_mod.criar(email, nome, senha, admin=admin)
        except Exception as e:
            logger.error("Erro ao criar usuário: %s", e)
    return redirect(url_for("admin_usuarios"))


@app.route("/admin/usuarios/<user_id>/toggle", methods=["POST"])
@login_required
def admin_toggle_usuario(user_id):
    if not current_user.admin:
        return jsonify({"erro": "Acesso negado"}), 403
    if user_id == current_user.id:
        return redirect(url_for("admin_usuarios"))
    usuario = usuarios_mod.buscar_por_id(user_id)
    if usuario:
        usuarios_mod.atualizar_ativo(user_id, not usuario.get("ativo", True))
    return redirect(url_for("admin_usuarios"))


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/processar", methods=["POST"])
@login_required
def processar():
    mensagem = request.form.get("mensagem", "").strip()

    if not mensagem:
        return jsonify({"erro": "Mensagem vazia"}), 400

    try:
        dados_extraidos = extrair_itens(mensagem)
    except EnvironmentError as e:
        return jsonify({"erro": str(e)}), 500
    except ValueError as e:
        return jsonify({"erro": str(e)}), 422

    itens = dados_extraidos["itens"]
    alertas = dados_extraidos["alertas"]

    if not itens:
        return jsonify({"erro": "Nenhum produto encontrado na mensagem"}), 422

    formulacoes_raw = request.form.get("formulacoes", "").strip()
    formulacoes_usuario = {}
    if formulacoes_raw:
        try:
            formulacoes_usuario = _json.loads(formulacoes_raw)
        except _json.JSONDecodeError:
            pass

    itens_ordenados = ordenar_itens(itens, formulacoes_usuario)

    operacao = extrair_operacao(mensagem)

    form_vazao = request.form.get("vazao", "").strip()
    form_area = request.form.get("area", "").strip()
    if form_vazao:
        try:
            operacao["vazao_L_ha"] = float(form_vazao.replace(",", "."))
        except ValueError:
            pass
    if form_area:
        try:
            operacao["area_tanque_ha"] = float(form_area.replace(",", "."))
        except ValueError:
            pass

    doses_por_tanque = request.form.get("doses_por_tanque") == "on"
    for item in itens_ordenados:
        if not item.get("base"):
            item["base"] = "tanque" if doses_por_tanque else "ha"

    area = operacao.get("area_tanque_ha")
    if area:
        calcular_totais_tanque(itens_ordenados, area)

    vazao = operacao.get("vazao_L_ha")
    alertas_incomp = verificar_incompatibilidades(itens_ordenados, vazao)

    return jsonify({
        "ordem": [
            {
                "posicao": it["posicao"],
                "produto": it["produto"],
                "formulacao": it.get("formulacao", "—"),
                "dose": it.get("dose", "—"),
                "unidade": it.get("unidade", "—"),
                "base": it.get("base", "—"),
                "alerta_prediluicao": it.get("alerta_prediluicao", ""),
                "total_tanque": it.get("total_tanque"),
                "total_unidade": it.get("total_unidade", ""),
                "dose_ha_calculada": it.get("dose_ha_calculada"),
                "dose_ha_unidade": it.get("dose_ha_unidade", ""),
            }
            for it in itens_ordenados
        ],
        "alertas": alertas,
        "alertas_incompatibilidade": alertas_incomp,
        "operacao": operacao if operacao else None,
    })


@app.route("/clientes")
@login_required
def pagina_clientes():
    return render_template("clientes.html")


@app.route("/api/clientes", methods=["GET"])
@login_required
def api_listar_clientes():
    return jsonify(clientes_mod.listar())


@app.route("/api/clientes", methods=["POST"])
@login_required
def api_criar_cliente():
    dados = request.get_json(silent=True) or {}
    if not dados.get("nome", "").strip():
        return jsonify({"erro": "Nome é obrigatório"}), 400
    cliente = clientes_mod.criar(dados)
    return jsonify(cliente), 201


@app.route("/api/clientes/<cliente_id>", methods=["GET"])
@login_required
def api_buscar_cliente(cliente_id):
    cliente = clientes_mod.buscar(cliente_id)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado"}), 404
    return jsonify(cliente)


@app.route("/api/clientes/<cliente_id>", methods=["PUT"])
@login_required
def api_atualizar_cliente(cliente_id):
    dados = request.get_json(silent=True) or {}
    if not dados.get("nome", "").strip():
        return jsonify({"erro": "Nome é obrigatório"}), 400
    cliente = clientes_mod.atualizar(cliente_id, dados)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado"}), 404
    return jsonify(cliente)


@app.route("/api/clientes/<cliente_id>", methods=["DELETE"])
@login_required
def api_excluir_cliente(cliente_id):
    if clientes_mod.excluir(cliente_id):
        return jsonify({"ok": True})
    return jsonify({"erro": "Cliente não encontrado"}), 404


@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook Z-API — recebe mensagens do WhatsApp."""
    from src.whatsapp import processar_webhook

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"status": "ok"}), 200

    resultado = processar_webhook(payload)
    logger.info("webhook resultado=%s", resultado)
    return jsonify(resultado), 200


@app.errorhandler(Exception)
def erro_geral(e):
    logger.exception("Erro não tratado: %s", e)
    return jsonify({"erro": str(e)}), 500


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    app.run(port=3002, debug=True)
