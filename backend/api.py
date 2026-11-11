"""API HTTP de PhantomPass (requisito 1: solicitud con filtros).

Reutiliza el stack Flask del proyecto. Expone:

    GET  /api/health
    GET  /api/filtros            -> metadatos para el frontend
    POST /api/consultas          -> crea un trabajo (202 + id)
    GET  /api/consultas          -> lista trabajos recientes
    GET  /api/consultas/<id>     -> estado/resultado del trabajo

El procesamiento real (scraper LegisComex) vive en `scraper.procesador`.
Por defecto devuelve un mock (`PHANTOMPASS_MOCK=1`) para poder construir el front.

Ejecutar en desarrollo:
    flask --app api run --port 8000
"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from flask import Flask, jsonify, request, url_for

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

from scraper.ai import IAError, ia_configurada, responder as responder_ia
from scraper.procesador import procesar_consulta

TIPOS = ("perfil", "texto", "documentos", "busqueda")
CAMPOS = {
    "tipo",
    "texto",
    "pais",
    "partida",
    "fecha_desde",
    "fecha_hasta",
    "limite",
    "filtros_extra",
}
LIMITE_DEFAULT = 20
LIMITE_MAX = 100
ESTADOS_FINALES = ("done", "error")

FILTROS_META = {
    "tipos": list(TIPOS),
    "limite_default": LIMITE_DEFAULT,
    "limite_max": LIMITE_MAX,
    "campos": [
        {
            "nombre": "tipo",
            "tipo": "string",
            "requerido": False,
            "default": "perfil",
            "enum": list(TIPOS),
            "descripcion": (
                "perfil = portada y nombre visible de la cuenta; texto = "
                "filtrar contenido público por texto; documentos = archivos "
                "en portada/blog; busqueda = búsqueda local en el blog"
            ),
        },
        {"nombre": "texto", "tipo": "string", "requerido": False},
        {"nombre": "pais", "tipo": "string", "requerido": False},
        {
            "nombre": "partida",
            "tipo": "string",
            "requerido": False,
            "descripcion": "código de partida arancelaria",
        },
        {"nombre": "fecha_desde", "tipo": "date", "requerido": False},
        {"nombre": "fecha_hasta", "tipo": "date", "requerido": False},
        {
            "nombre": "limite",
            "tipo": "integer",
            "requerido": False,
            "default": LIMITE_DEFAULT,
            "min": 1,
            "max": LIMITE_MAX,
        },
        {"nombre": "filtros_extra", "tipo": "object", "requerido": False},
    ],
    "nota": (
        "Solo se consulta la portada/perfil y el blog público; no se visitan "
        "estadísticas comerciales ni se solicitan datos de suscripción. Los "
        "filtros país, partida y fechas no aplican al contenido editorial."
    ),
}


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Almacén de trabajos en memoria, seguro para hilos.

    Suficiente para desarrollo y para un único proceso. Para producción con
    varios workers habría que sustituirlo por una cola/DB.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict] = {}

    def crear(self, consulta: dict) -> dict:
        job = {
            "id": uuid.uuid4().hex,
            "estado": "queued",
            "creada_en": _ahora(),
            "iniciada_en": None,
            "terminada_en": None,
            "consulta": consulta,
            "resultado": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job["id"]] = job
        return dict(job)

    def obtener(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def listar(self, limite: int) -> list[dict]:
        with self._lock:
            jobs = list(self._jobs.values())
        return [dict(job) for job in reversed(jobs[-limite:])]

    def actualizar(self, job_id: str, **campos: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.update(campos)


def _serializar_consulta(consulta: dict) -> dict:
    salida = dict(consulta)
    for campo in ("fecha_desde", "fecha_hasta"):
        valor = salida.get(campo)
        if isinstance(valor, date):
            salida[campo] = valor.isoformat()
    return salida


def _validar_consulta(payload: Any) -> tuple[Optional[dict], list[dict]]:
    """Valida el cuerpo JSON y devuelve (consulta, errores)."""
    if not isinstance(payload, dict):
        return None, [
            {"campo": "body", "mensaje": "el cuerpo debe ser un objeto JSON"}
        ]

    errores: list[dict] = []

    for campo in sorted(set(payload) - CAMPOS):
        errores.append({"campo": campo, "mensaje": "campo no soportado"})

    tipo = payload.get("tipo", "perfil")
    if tipo not in TIPOS:
        errores.append(
            {"campo": "tipo", "mensaje": f"debe ser uno de {list(TIPOS)}"}
        )
        tipo = "perfil"

    consulta: dict[str, Any] = {"tipo": tipo}

    for campo in ("texto", "pais", "partida"):
        valor = payload.get(campo)
        if valor is None:
            consulta[campo] = None
        elif not isinstance(valor, str):
            errores.append({"campo": campo, "mensaje": "debe ser texto"})
        else:
            consulta[campo] = valor.strip() or None

    for campo in ("fecha_desde", "fecha_hasta"):
        valor = payload.get(campo)
        if valor is None:
            consulta[campo] = None
            continue
        if not isinstance(valor, str):
            errores.append(
                {"campo": campo, "mensaje": "debe ser fecha ISO (YYYY-MM-DD)"}
            )
            continue
        try:
            consulta[campo] = date.fromisoformat(valor)
        except ValueError:
            errores.append(
                {"campo": campo, "mensaje": "fecha inválida (usar YYYY-MM-DD)"}
            )

    desde = consulta.get("fecha_desde")
    hasta = consulta.get("fecha_hasta")
    if isinstance(desde, date) and isinstance(hasta, date) and desde > hasta:
        errores.append(
            {
                "campo": "fecha_desde",
                "mensaje": "no puede ser posterior a fecha_hasta",
            }
        )

    limite = payload.get("limite", LIMITE_DEFAULT)
    if isinstance(limite, bool) or not isinstance(limite, int):
        errores.append({"campo": "limite", "mensaje": "debe ser un entero"})
    elif not 1 <= limite <= LIMITE_MAX:
        errores.append(
            {
                "campo": "limite",
                "mensaje": f"debe estar entre 1 y {LIMITE_MAX}",
            }
        )
    else:
        consulta["limite"] = limite

    extra = payload.get("filtros_extra") or {}
    if not isinstance(extra, dict) or not all(
        isinstance(k, str) and isinstance(v, (str, int, float, bool))
        for k, v in extra.items()
    ):
        errores.append(
            {
                "campo": "filtros_extra",
                "mensaje": "debe ser un objeto de valores simples",
            }
        )
    else:
        consulta["filtros_extra"] = dict(extra)

    if tipo != "perfil" and not any(
        consulta.get(campo)
        for campo in ("texto", "pais", "partida", "fecha_desde", "fecha_hasta")
    ):
        errores.append(
            {
                "campo": "filtros",
                "mensaje": "se requiere al menos un filtro para este tipo",
            }
        )

    if errores:
        return None, errores
    return _serializar_consulta(consulta), []


def _ejecutar(store: JobStore, job_id: str) -> None:
    store.actualizar(job_id, estado="running", iniciada_en=_ahora())
    job = store.obtener(job_id)
    if job is None:
        return
    try:
        resultado = procesar_consulta(job["consulta"])
    except Exception as exc:  # noqa: BLE001 - se reporta al cliente
        store.actualizar(
            job_id,
            estado="error",
            error=str(exc),
            terminada_en=_ahora(),
        )
    else:
        store.actualizar(
            job_id,
            estado="done",
            resultado=resultado,
            terminada_en=_ahora(),
        )


def create_app() -> Flask:
    app = Flask(__name__)
    store = JobStore()
    workers = int(os.getenv("PHANTOMPASS_WORKERS", "2"))
    executor = ThreadPoolExecutor(max_workers=max(1, workers))
    app.config["JOB_STORE"] = store
    app.config["EXECUTOR"] = executor

    @app.after_request
    def _cors(resp):
        resp.headers["Access-Control-Allow-Origin"] = os.getenv(
            "CORS_ORIGIN", "*"
        )
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    @app.get("/")
    def index():
        return jsonify(
            {
                "servicio": "PhantomPass API",
                "health": "/api/health",
                "filtros": "/api/filtros",
                "consultas": "/api/consultas",
            }
        )

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "mock": os.getenv("PHANTOMPASS_MOCK", "1") != "0",
            }
        )

    @app.get("/api/filtros")
    def filtros():
        return jsonify(FILTROS_META)

    @app.post("/api/consultas")
    def crear_consulta():
        payload = request.get_json(silent=True)
        consulta, errores = _validar_consulta(payload)
        if errores:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "validation_error",
                            "message": "filtros inválidos",
                            "details": errores,
                        }
                    }
                ),
                400,
            )

        job = store.crear(consulta)
        executor.submit(_ejecutar, store, job["id"])

        resp = jsonify(job)
        resp.status_code = 202
        resp.headers["Location"] = url_for(
            "obtener_consulta", job_id=job["id"]
        )
        return resp

    @app.get("/api/consultas")
    def listar_consultas():
        limite = request.args.get("limite", default=50, type=int)
        if limite is None:
            limite = 50
        limite = max(1, min(limite, 200))
        return jsonify({"items": store.listar(limite)})

    @app.get("/api/consultas/<job_id>")
    def obtener_consulta(job_id: str):
        job = store.obtener(job_id)
        if job is None:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "not_found",
                            "message": f"la consulta '{job_id}' no existe",
                        }
                    }
                ),
                404,
            )
        return jsonify(job)

    @app.get("/api/ia/estado")
    def ia_estado():
        return jsonify(
            {
                "configurada": ia_configurada(),
                "modelo": os.getenv(
                    "OPENROUTER_MODEL", "openai/gpt-4o-mini"
                ),
            }
        )

    @app.post("/api/consultas/<job_id>/preguntar")
    def preguntar_consulta(job_id: str):
        job = store.obtener(job_id)
        if job is None:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "not_found",
                            "message": f"la consulta '{job_id}' no existe",
                        }
                    }
                ),
                404,
            )

        if job["estado"] != "done" or not job["resultado"]:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "consulta_no_lista",
                            "message": (
                                "la consulta aún no terminó; espera a que "
                                "estado sea 'done'"
                            ),
                            "estado": job["estado"],
                        }
                    }
                ),
                409,
            )

        payload = request.get_json(silent=True) or {}
        pregunta = payload.get("pregunta")
        if not isinstance(pregunta, str) or not pregunta.strip():
            return (
                jsonify(
                    {
                        "error": {
                            "code": "validation_error",
                            "message": "el campo 'pregunta' es obligatorio",
                        }
                    }
                ),
                400,
            )
        pregunta = pregunta.strip()
        if len(pregunta) > 2000:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "validation_error",
                            "message": "la pregunta supera 2000 caracteres",
                        }
                    }
                ),
                400,
            )

        if not ia_configurada():
            return (
                jsonify(
                    {
                        "error": {
                            "code": "ia_no_configurada",
                            "message": (
                                "falta OPENROUTER_API_KEY en el entorno (.env)"
                            ),
                        }
                    }
                ),
                503,
            )

        try:
            respuesta = responder_ia(pregunta, job["resultado"])
        except IAError as exc:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "ia_error",
                            "message": str(exc),
                        }
                    }
                ),
                502,
            )

        return jsonify(
            {
                "job_id": job_id,
                "pregunta": pregunta,
                "mock": bool(job["resultado"].get("mock", False)),
                **respuesta,
            }
        )

    @app.errorhandler(404)
    def _no_encontrado(_exc):
        return (
            jsonify(
                {
                    "error": {
                        "code": "not_found",
                        "message": "recurso no encontrado",
                    }
                }
            ),
            404,
        )

    @app.errorhandler(405)
    def _metodo_no_permitido(_exc):
        return (
            jsonify(
                {
                    "error": {
                        "code": "method_not_allowed",
                        "message": "método no permitido",
                    }
                }
            ),
            405,
        )

    return app


if __name__ == "__main__":
    create_app().run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
