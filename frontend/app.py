"""Flask dashboard for viewing scraped data.

El destino de despliegue del frontend aún NO está definido. Por ahora corre en
local para desarrollo; host/puerto se configuran por variables de entorno
(FLASK_HOST / FLASK_PORT) para desplegarlo donde se decida más adelante.
"""

from __future__ import annotations

import os

from flask import Flask, render_template


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        records = [
            {"title": "Example Domain", "url": "https://example.com"},
        ]
        return render_template("index.html", records=records)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)
