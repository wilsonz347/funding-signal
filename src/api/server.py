# src/api/server.py
"""Flask server for the SQL agent"""

from __future__ import annotations

from flask import Flask, jsonify, request

from src.agent.agent import SQLAgent
from src.agent.answer import Answerer
from src.agent.catalog import load_catalog
from src.agent.llm import OllamaClient
from src.agent.settings import Settings
from src.agent.warehouse import DatabricksWarehouse


def create_app(
    agent: SQLAgent | None = None,
    answerer: Answerer | None = None,
) -> Flask:
    app = Flask(__name__)

    # Load the catalog and initialize the agent and answerer if not provided
    if agent is None or answerer is None:
        catalog = load_catalog("config/agent_catalog.yaml")
        llm = OllamaClient()

        # Initialize the agent and answerer if not provided
        if agent is None:
            settings = Settings.from_env()
            warehouse = DatabricksWarehouse(settings)
            agent = SQLAgent(
                llm=llm,
                warehouse=warehouse,
                catalog=catalog,
            )

        if answerer is None:
            answerer = Answerer(llm=llm, catalog=catalog)

    # Store the agent and answerer in the app config for use in request handlers
    app.config["agent"] = agent
    app.config["answerer"] = answerer

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    # Endpoint to handle the /ask POST request
    @app.post("/ask")
    def ask():
        body = request.get_json(silent=True)

        if not isinstance(body, dict):
            return jsonify({"error": "Request body must be a JSON object."}), 400

        question = body.get("question")

        if not isinstance(question, str) or not question.strip():
            return jsonify({"error": "'question' must be a non-empty string."}), 400

        if len(question) > 2000:
            return jsonify({"error": "Question must be 2000 characters or fewer."}), 400

        try:
            agent_result = app.config["agent"].run(question.strip())
            answer = app.config["answerer"].answer(agent_result)
        except Exception:
            app.logger.exception("Unexpected error while processing question.")
            return jsonify({"error": "An internal error occurred."}), 500

        payload = {
            "ok": answer.ok,
            "answer": answer.text,
            "sql": answer.sql,
            "rows_shown": answer.rows_shown,
            "rows_total": answer.rows_total,
            "notes": answer.notes or [],
        }

        status_code = 200 if answer.ok else 502
        return jsonify(payload), status_code

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)
