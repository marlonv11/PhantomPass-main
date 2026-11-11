import time

import pytest

import scraper.ai as ai
from api import create_app


class _FakeResp:
    status_code = 200
    text = ""

    def json(self):
        return {
            "model": "fake/model",
            "choices": [{"message": {"content": "  La respuesta IA.  "}}],
            "usage": {"total_tokens": 12},
        }


@pytest.fixture()
def app():
    application = create_app()
    application.config["TESTING"] = True
    yield application
    application.config["EXECUTOR"].shutdown(wait=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def _job_done(client, payload=None):
    respuesta = client.post("/api/consultas", json=payload or {"tipo": "perfil"})
    assert respuesta.status_code == 202
    job = respuesta.get_json()
    fin = time.time() + 5
    while time.time() < fin:
        actual = client.get(f"/api/consultas/{job['id']}").get_json()
        if actual["estado"] == "done":
            return actual
        time.sleep(0.05)
    raise AssertionError("el trabajo no terminó a tiempo")


def test_ia_estado_sin_clave(client, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    respuesta = client.get("/api/ia/estado")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["configurada"] is False


def test_preguntar_sin_clave(client, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    job = _job_done(client)
    respuesta = client.post(
        f"/api/consultas/{job['id']}/preguntar",
        json={"pregunta": "¿Qué información hay?"},
    )
    assert respuesta.status_code == 503
    assert respuesta.get_json()["error"]["code"] == "ia_no_configurada"


def test_preguntar_ok(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    job = _job_done(client, {"tipo": "busqueda", "texto": "café"})
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _FakeResp())

    respuesta = client.post(
        f"/api/consultas/{job['id']}/preguntar",
        json={"pregunta": "¿De qué trata el resultado?"},
    )
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["respuesta"] == "La respuesta IA."
    assert cuerpo["modelo"] == "fake/model"
    assert cuerpo["mock"] is True
    assert cuerpo["job_id"] == job["id"]
    assert cuerpo["pregunta"] == "¿De qué trata el resultado?"


def test_preguntar_job_inexistente(client):
    respuesta = client.post(
        "/api/consultas/no-existe/preguntar", json={"pregunta": "x"}
    )
    assert respuesta.status_code == 404


def test_preguntar_job_no_listo(app, client):
    job = app.config["JOB_STORE"].crear({"tipo": "perfil"})
    respuesta = client.post(
        f"/api/consultas/{job['id']}/preguntar", json={"pregunta": "x"}
    )
    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["code"] == "consulta_no_lista"


def test_preguntar_sin_pregunta(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    job = _job_done(client)
    respuesta = client.post(
        f"/api/consultas/{job['id']}/preguntar", json={}
    )
    assert respuesta.status_code == 400


def test_preguntar_error_openrouter(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    job = _job_done(client)

    class _Err:
        status_code = 500
        text = "boom"

        def json(self):
            return {}

    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: _Err())
    respuesta = client.post(
        f"/api/consultas/{job['id']}/preguntar", json={"pregunta": "x"}
    )
    assert respuesta.status_code == 502
    assert respuesta.get_json()["error"]["code"] == "ia_error"


def test_responder_usa_contexto_y_pregunta(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    capturado = {}

    def _post(url, json=None, headers=None, timeout=None):
        capturado["url"] = url
        capturado["json"] = json
        capturado["headers"] = headers
        return _FakeResp()

    monkeypatch.setattr(ai.requests, "post", _post)
    resultado = ai.responder("¿Cuántos registros?", {"resumen": {"total": 3}})

    assert resultado["respuesta"] == "La respuesta IA."
    assert capturado["url"].endswith("/chat/completions")
    assert capturado["headers"]["Authorization"] == "Bearer test-key"
    assert "¿Cuántos registros?" in capturado["json"]["messages"][-1]["content"]
    assert '"total": 3' in capturado["json"]["messages"][-1]["content"]
