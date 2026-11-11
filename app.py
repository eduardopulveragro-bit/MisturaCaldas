"""Flask app — interface web na porta 3002."""
import json as _json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, session
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user

_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH, override=True)

from src.parser import extrair_itens
from src.ordenacao import ordenar_itens
from src.operacao import extrair_operacao, calcular_totais_tanque
from src.alertas_incompatibilidade import verificar_incompatibilidades
from src import clientes as clientes_mod
from src import usuarios as usuarios_mod
from src import historico as historico_mod

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
        self.tipo = data.get("tipo", "produtor")
        self.onboarding_completo = data.get("onboarding_completo", False)


@login_manager.user_loader
def carregar_usuario(user_id: str):
    data = usuarios_mod.buscar_por_id(user_id)
    return User(data) if data else None


@login_manager.unauthorized_handler
def nao_autorizado():
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"erro": "Sessão expirada. Faça login novamente.", "redirect": "/login"}), 401
    return redirect(url_for("login"))


_SKIP_ONBOARDING = {
    "login", "logout", "cadastro", "setup",
    "onboarding", "onboarding_equipamentos",
    "static", "favicon", "webhook", "init_db", "init_db_historico", "migrate_db", "migrate_db_historico",
    "historico", "api_historico_listar", "api_historico_criar", "api_historico_excluir",
}


@app.before_request
def verificar_onboarding():
    if not request.endpoint:
        return None
    ep = request.endpoint
    if ep in _SKIP_ONBOARDING or ep.startswith("static"):
        return None
    if (current_user.is_authenticated
            and not current_user.onboarding_completo
            and not session.get("onboarding_done")):
        return redirect(url_for("onboarding"))


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


@app.route("/init-db")
def init_db():
    """Cria a tabela usuarios no Supabase. Visitar uma vez após o deploy."""
    resultado = usuarios_mod.criar_tabela()
    if resultado["status"] == 200:
        return jsonify({"ok": True, "msg": "Tabela usuarios criada com sucesso."})
    return jsonify({"ok": False, "status": resultado["status"], "detalhe": resultado["body"]}), 500


@app.route("/migrate-db")
def migrate_db():
    """Adiciona colunas tipo/onboarding_completo se não existirem. Idempotente."""
    resultado = usuarios_mod.migrar_tabela()
    if resultado["status"] in (200, 201, 204):
        return jsonify({"ok": True, "msg": "Migração aplicada (ou já estava atualizada)."})
    return jsonify({"ok": False, "status": resultado["status"], "detalhe": resultado["body"]}), 500


@app.route("/migrate-db-historico")
def migrate_db_historico():
    """Adiciona colunas ausentes em historico_caldas. Idempotente."""
    resultado = historico_mod.migrar_tabela()
    if resultado["status"] in (200, 201, 204):
        return jsonify({"ok": True, "msg": "Migração historico_caldas aplicada."})
    return jsonify({"ok": False, "status": resultado["status"], "detalhe": resultado["body"]}), 500


@app.route("/init-db-historico")
def init_db_historico():
    """Cria a tabela historico_caldas no Supabase. Visitar uma vez após o deploy."""
    resultado = historico_mod.criar_tabela()
    if resultado["status"] in (200, 201, 204):
        return jsonify({"ok": True, "msg": "Tabela historico_caldas criada com sucesso."})
    return jsonify({"ok": False, "status": resultado["status"], "detalhe": resultado["body"]}), 500


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if usuarios_mod.contar() == 0:
        return redirect(url_for("setup"))
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
                u = usuarios_mod.criar(email, nome, senha, admin=False)
                login_user(User(u), remember=True)
                return redirect(url_for("onboarding"))
            except Exception as e:
                logger.exception("Erro ao criar usuário: %s", e)
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    erro = "Este email já está cadastrado."
                else:
                    erro = "Erro ao criar conta. Tente novamente."
    return render_template("cadastro.html", erro=erro)


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
                return redirect(url_for("onboarding"))
            except Exception as e:
                logger.exception("Erro ao criar primeiro admin: %s", e)
                erro = "Erro ao criar usuário. Verifique as configurações do Supabase."
    return render_template("setup.html", erro=erro)


# ── Onboarding ───────────────────────────────────────────────────────────────

@app.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    if current_user.onboarding_completo and not session.get("onboarding_tipo"):
        return redirect(url_for("index"))
    if request.method == "POST":
        tipo = request.form.get("tipo")
        if tipo not in ("produtor", "consultor"):
            return render_template("onboarding_tipo.html", erro="Escolha um tipo.")
        session["onboarding_tipo"] = tipo
        return redirect(url_for("onboarding_equipamentos"))
    return render_template("onboarding_tipo.html")


@app.route("/onboarding/equipamentos", methods=["GET", "POST"])
@login_required
def onboarding_equipamentos():
    if current_user.onboarding_completo and not session.get("onboarding_tipo"):
        return redirect(url_for("index"))
    if request.method == "POST":
        tipo = session.pop("onboarding_tipo", "produtor")

        fazendas_raw = request.form.get("fazendas_json")
        if fazendas_raw:
            # Fluxo consultor: múltiplas fazendas
            try:
                fazendas = _json.loads(fazendas_raw)
            except _json.JSONDecodeError:
                fazendas = []
            usuarios_mod.atualizar_onboarding(current_user.id, tipo, {"fazendas": fazendas})
            for fazenda in fazendas:
                nome_fazenda = (fazenda.get("nome") or "").strip()
                pulverizadores = fazenda.get("pulverizadores") or []
                for i, pulv in enumerate(pulverizadores):
                    modelo = (pulv.get("nome") or pulv.get("modelo") or "").strip()
                    if not modelo and not nome_fazenda:
                        continue
                    if nome_fazenda and len(pulverizadores) == 1:
                        nome_cliente = nome_fazenda
                    elif nome_fazenda:
                        nome_cliente = f"{nome_fazenda} — {modelo}" if modelo else f"{nome_fazenda} {i+1}"
                    else:
                        nome_cliente = modelo
                    try:
                        clientes_mod.criar({
                            "nome": nome_cliente,
                            "usuario_id": current_user.id,
                            "pulverizador_modelo": modelo,
                            "volume_tanque": pulv.get("volume_tanque_L"),
                            "pontas": ",".join(pulv.get("pontas") or []),
                            "configs": [{"descricao": "Padrão", "vazao_L_ha": pulv.get("vazao_L_ha"), "area_tanque_ha": pulv.get("area_tanque_ha")}]
                                     if pulv.get("vazao_L_ha") else [],
                        })
                    except Exception as e:
                        logger.warning("Onboarding: erro ao criar cliente '%s': %s", nome_cliente, e)
        else:
            # Fluxo produtor: fazenda única + pulverizadores
            try:
                pulverizadores = _json.loads(request.form.get("pulverizadores_json", "[]"))
            except _json.JSONDecodeError:
                pulverizadores = []
            try:
                talhoes = _json.loads(request.form.get("talhoes_json", "[]"))
            except _json.JSONDecodeError:
                talhoes = []
            usuarios_mod.atualizar_onboarding(current_user.id, tipo, {"pulverizadores": pulverizadores, "talhoes": talhoes})
            nome_fazenda = request.form.get("nome_fazenda", "").strip()
            for i, pulv in enumerate(pulverizadores):
                modelo = (pulv.get("nome") or pulv.get("modelo") or "").strip()
                if not modelo and not nome_fazenda:
                    continue
                if nome_fazenda and len(pulverizadores) == 1:
                    nome_cliente = nome_fazenda
                elif nome_fazenda:
                    nome_cliente = f"{nome_fazenda} — {modelo}" if modelo else f"{nome_fazenda} {i+1}"
                else:
                    nome_cliente = modelo
                try:
                    clientes_mod.criar({
                        "nome": nome_cliente,
                        "usuario_id": current_user.id,
                        "pulverizador_modelo": modelo,
                        "volume_tanque": pulv.get("volume_tanque_L"),
                        "pontas": ",".join(pulv.get("pontas") or []),
                        "configs": [{"descricao": "Padrão", "vazao_L_ha": pulv.get("vazao_L_ha"), "area_tanque_ha": pulv.get("area_tanque_ha")}]
                                 if pulv.get("vazao_L_ha") else [],
                    })
                except Exception as e:
                    logger.warning("Onboarding: erro ao criar cliente '%s': %s", nome_cliente, e)
        session["onboarding_done"] = True
        return redirect(url_for("index"))
    tipo_onboarding = session.get("onboarding_tipo", current_user.tipo)
    return render_template("onboarding_equipamentos.html", tipo_onboarding=tipo_onboarding)


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
    contagem_caldas = historico_mod.contar_todos()
    for u in usuarios:
        u["num_caldas"] = contagem_caldas.get(u["id"], 0)
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


@app.route("/delta-t")
@login_required
def delta_t():
    return render_template("delta_t.html")


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
    dados["usuario_id"] = current_user.id
    try:
        cliente = clientes_mod.criar(dados)
    except Exception as e:
        logger.exception("Erro ao criar cliente: %s", e)
        return jsonify({"erro": str(e)}), 500
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
    dados["usuario_id"] = current_user.id
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


@app.route("/historico")
@login_required
def historico():
    return render_template("historico.html")


@app.route("/api/historico", methods=["GET"])
@login_required
def api_historico_listar():
    cliente_id = request.args.get("cliente_id") or None
    registros = historico_mod.listar(current_user.id, cliente_id=cliente_id)
    return jsonify(registros)


@app.route("/api/historico", methods=["POST"])
@login_required
def api_historico_criar():
    dados = request.get_json(silent=True) or {}
    dados["usuario_id"] = current_user.id
    try:
        registro = historico_mod.criar(dados)
        return jsonify(registro), 201
    except Exception as e:
        logger.exception("Erro ao salvar histórico: %s", e)
        return jsonify({"erro": str(e)}), 500


@app.route("/api/historico/<historico_id>", methods=["DELETE"])
@login_required
def api_historico_excluir(historico_id):
    try:
        historico_mod.excluir(historico_id, current_user.id)
        return jsonify({"ok": True})
    except Exception as e:
        logger.exception("Erro ao excluir histórico: %s", e)
        return jsonify({"erro": str(e)}), 500


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
