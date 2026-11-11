import time

import pytest

from api import create_app
from scraper.procesador import procesar_consulta
from scraper.sesion import SesionRequerida


@pytest.fixture()
def app():
    application = create_app()
    application.config["TESTING"] = True
    yield application
    application.config["EXECUTOR"].shutdown(wait=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def _esperar(client, job_id, timeout=5.0):
    fin = time.time() + timeout
    while time.time() < fin:
        respuesta = client.get(f"/api/consultas/{job_id}")
        assert respuesta.status_code == 200
        job = respuesta.get_json()
        if job["estado"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("el trabajo no terminó a tiempo")


def test_health(client):
    respuesta = client.get("/api/health")
    assert respuesta.status_code == 200
    assert respuesta.get_json()["status"] == "ok"


def test_filtros_meta(client):
    respuesta = client.get("/api/filtros")
    assert respuesta.status_code == 200
    meta = respuesta.get_json()
    assert meta["tipos"] == ["perfil", "texto", "documentos", "busqueda"]
    assert meta["limite_max"] == 100
    assert any(c["nombre"] == "partida" for c in meta["campos"])


def test_crear_consulta_perfil(client):
    respuesta = client.post("/api/consultas", json={"tipo": "perfil"})
    assert respuesta.status_code == 202
    assert respuesta.headers["Location"].startswith("/api/consultas/")

    job = respuesta.get_json()
    assert job["estado"] == "queued"
    assert job["consulta"]["tipo"] == "perfil"

    terminado = _esperar(client, job["id"])
    assert terminado["estado"] == "done"
    assert terminado["resultado"]["mock"] is True
    assert terminado["resultado"]["consulta"]["tipo"] == "perfil"
    assert terminado["terminada_en"] is not None


def test_crear_consulta_con_filtros(client):
    payload = {
        "tipo": "busqueda",
        "texto": "café",
        "pais": "CO",
        "partida": "0901",
        "fecha_desde": "2024-01-01",
        "fecha_hasta": "2024-12-31",
        "limite": 5,
        "filtros_extra": {"moneda": "USD"},
    }
    respuesta = client.post("/api/consultas", json=payload)
    assert respuesta.status_code == 202

    job = respuesta.get_json()
    consulta = job["consulta"]
    assert consulta["texto"] == "café"
    assert consulta["pais"] == "CO"
    assert consulta["partida"] == "0901"
    assert consulta["fecha_desde"] == "2024-01-01"
    assert consulta["fecha_hasta"] == "2024-12-31"
    assert consulta["limite"] == 5
    assert consulta["filtros_extra"] == {"moneda": "USD"}

    terminado = _esperar(client, job["id"])
    assert terminado["estado"] == "done"
    assert terminado["resultado"]["resumen"]["tipo"] == "busqueda"


@pytest.mark.parametrize(
    ("payload", "campo"),
    [
        ({"tipo": "otro"}, "tipo"),
        ({"tipo": "busqueda"}, "filtros"),
        ({"tipo": "busqueda", "texto": "x", "limite": 0}, "limite"),
        ({"tipo": "busqueda", "texto": "x", "limite": 101}, "limite"),
        ({"tipo": "busqueda", "texto": "x", "limite": "10"}, "limite"),
        (
            {
                "tipo": "busqueda",
                "texto": "x",
                "fecha_desde": "2024-12-31",
                "fecha_hasta": "2024-01-01",
            },
            "fecha_desde",
        ),
        ({"tipo": "busqueda", "texto": "x", "campo_raro": 1}, "campo_raro"),
        ({"tipo": "busqueda", "texto": 123}, "texto"),
        (
            {"tipo": "busqueda", "texto": "x", "filtros_extra": "no"},
            "filtros_extra",
        ),
        ({"tipo": "busqueda", "texto": "x", "fecha_desde": "31-12-2024"}, "fecha_desde"),
    ],
)
def test_validacion_de_filtros(client, payload, campo):
    respuesta = client.post("/api/consultas", json=payload)
    assert respuesta.status_code == 400
    cuerpo = respuesta.get_json()
    assert cuerpo["error"]["code"] == "validation_error"
    assert any(d["campo"] == campo for d in cuerpo["error"]["details"])


def test_cuerpo_no_json(client):
    respuesta = client.post(
        "/api/consultas", data="{no es json", content_type="application/json"
    )
    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["code"] == "validation_error"


def test_trabajo_inexistente(client):
    respuesta = client.get("/api/consultas/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["code"] == "not_found"


def test_ruta_inexistente_devuelve_json(client):
    respuesta = client.get("/api/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["code"] == "not_found"


def test_listar_consultas(client):
    ids = []
    for texto in ("uno", "dos"):
        respuesta = client.post(
            "/api/consultas", json={"tipo": "texto", "texto": texto}
        )
        assert respuesta.status_code == 202
        ids.append(respuesta.get_json()["id"])

    respuesta = client.get("/api/consultas?limite=10")
    assert respuesta.status_code == 200
    items = respuesta.get_json()["items"]
    assert len(items) >= 2
    assert {job["id"] for job in items} >= set(ids)


def test_cors(client):
    respuesta = client.get("/api/health")
    assert "Access-Control-Allow-Origin" in respuesta.headers


def test_procesador_sin_mock(monkeypatch, tmp_path):
    monkeypatch.setenv("PHANTOMPASS_MOCK", "0")
    monkeypatch.setenv("LEGIS_STATE_FILE", str(tmp_path / "no-existe.json"))
    with pytest.raises(SesionRequerida):
        procesar_consulta({"tipo": "perfil"})
