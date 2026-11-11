"""Procesador de consultas: punto de unión entre la API y el scraper real.

Con `PHANTOMPASS_MOCK=1` (por defecto) devuelve un resultado simulado para que el
frontend pueda construirse. Con `PHANTOMPASS_MOCK=0` reutiliza la sesión guardada
(`backend/sesion.json`) y extrae la portada/perfil y el blog público de
LegisComex, siempre que `robots.txt` permita verificar el acceso.

La sesión se captura manualmente con `backend/capturar_sesion.py` para no repetir
el CAPTCHA en cada consulta.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

MOCK_ENV = "PHANTOMPASS_MOCK"


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def procesar_consulta(filtros: dict) -> dict:
    """Ejecuta una consulta ya validada y devuelve un dict serializable."""
    if os.getenv(MOCK_ENV, "1") != "0":
        return _resultado_mock(filtros)
    return _resultado_real(filtros)


def _resultado_real(filtros: dict) -> dict:
    """Reutiliza la sesión guardada y extrae datos reales de LegisComex."""
    from .legiscomex import extraer_pagina
    from .sesion import abrir_pagina

    with abrir_pagina() as page:
        resultado = extraer_pagina(page, filtros)
    resultado["generado_en"] = _ahora()
    return resultado


def _resultado_mock(filtros: dict) -> dict:
    time.sleep(0.2)
    tipo = filtros.get("tipo", "perfil")
    texto = filtros.get("texto") or "(sin texto)"
    return {
        "mock": True,
        "aviso": (
            "Resultado simulado. Para usar contenido gratuito real de "
            "LegisComex, configura una sesión válida y verifica que robots.txt "
            "permita el acceso."
        ),
        "generado_en": _ahora(),
        "consulta": filtros,
        "resumen": {
            "total": 3,
            "tipo": tipo,
            "fuente": "mock",
            "solo_cuenta_gratuita": True,
        },
        "registros": [
            {
                "titulo": "Perfil de la cuenta",
                "detalle": "Datos visibles con cuenta gratuita",
                "url": "https://www.legiscomex.com/",
            },
            {
                "titulo": "Bloque de texto",
                "detalle": f"filtro texto={texto}",
                "url": "https://www.legiscomex.com/",
            },
            {
                "titulo": "Documento",
                "detalle": "Descarga pendiente de conectar (requisito 4)",
                "url": "https://www.legiscomex.com/",
            },
        ],
    }
