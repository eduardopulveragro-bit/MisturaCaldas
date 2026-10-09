"""Flask app — interface web na porta 3002."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH, override=True)

from src.parser import extrair_itens
from src.ordenacao import ordenar_itens
from src.operacao import extrair_operacao, calcular_totais_tanque

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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/processar", methods=["POST"])
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

    itens_ordenados = ordenar_itens(itens)

    operacao = extrair_operacao(mensagem)
    area = operacao.get("area_tanque_ha")
    if area:
        calcular_totais_tanque(itens_ordenados, area)

    return jsonify({
        "ordem": [
            {
                "posicao": it["posicao"],
                "produto": it["produto"],
                "formulacao": it.get("formulacao", "—"),
                "dose": it.get("dose", "—"),
                "unidade": it.get("unidade", "—"),
                "base": it.get("base", "—"),
                "pendente": it.get("pendente", False),
                "alerta": it.get("alerta_pendente", ""),
                "alerta_prediluicao": it.get("alerta_prediluicao", ""),
                "total_tanque": it.get("total_tanque"),
                "total_unidade": it.get("total_unidade", ""),
            }
            for it in itens_ordenados
        ],
        "alertas": alertas,
        "operacao": operacao if operacao else None,
    })


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
