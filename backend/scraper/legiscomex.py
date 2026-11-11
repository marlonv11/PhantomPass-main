"""Extracción de contenido visible y gratuito de LegisComex.

Se limita a la portada autenticada y al blog público con sus artículos enlazados.
Las rutas de consulta comercial y de suscripción no se visitan.
"""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from .extractor import RobotsDisallowedError, Scraper
from .sesion import SesionRequerida, nombre_usuario, pagina_logueada

URL_INICIO = "https://www.legiscomex.com/"
URL_BLOG = "https://www.legiscomex.com/blog"
EXTENSIONES_DOC = (
    ".pdf",
    ".xls",
    ".xlsx",
    ".csv",
    ".zip",
    ".rar",
    ".7z",
    ".doc",
    ".docx",
    ".txt",
    ".xml",
)
MAX_TEXTO = 20000
MAX_ARTICULOS = 20
MIN_TEXTO_ENLACE_ARTICULO = 20
ESPERA_ENTRE_PAGINAS_MS = 1000
HOSTS_LEGISCOMEX = {"legiscomex.com", "www.legiscomex.com"}
RUTAS_EXCLUIDAS = (
    "/ir/",
    "/planes",
    "/suscripcion",
    "/legis_sso",
    "/user/logout",
)
PARAMETROS_SENSIBLES = {
    "access_token",
    "auth",
    "session",
    "sessionid",
    "token",
}


def url_consulta() -> str:
    return os.getenv("LEGIS_BLOG_URL", URL_BLOG)


def texto_limpio(texto: str, max_chars: int = MAX_TEXTO) -> str:
    limpio = re.sub(r"\s+", " ", texto or "").strip()
    return limpio[:max_chars]


def clasificar_enlaces(
    enlaces: list[dict], base_url: str
) -> tuple[list[dict], list[dict]]:
    """Normaliza enlaces, omite rutas excluidas y separa documentos."""
    vistos: set[str] = set()
    normalizados: list[dict] = []
    documentos: list[dict] = []
    for enlace in enlaces:
        href = (enlace.get("url") or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        url = _sanear_url(urljoin(base_url, href))
        if not url or _ruta_excluida(url):
            continue
        if url in vistos:
            continue
        vistos.add(url)
        item = {"texto": (enlace.get("texto") or "").strip(), "url": url}
        normalizados.append(item)
        if url.lower().endswith(EXTENSIONES_DOC):
            documentos.append(item)
    return normalizados, documentos


def _sanear_url(url: str) -> str:
    partes = urlsplit(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        return ""
    query = urlencode(
        [
            (clave, valor)
            for clave, valor in parse_qsl(partes.query, keep_blank_values=True)
            if clave.casefold() not in PARAMETROS_SENSIBLES
        ]
    )
    return urlunsplit((partes.scheme, partes.netloc, partes.path, query, ""))


def _ruta_excluida(url: str) -> bool:
    partes = urlsplit(url)
    ruta = partes.path.casefold()
    return any(segmento in ruta for segmento in RUTAS_EXCLUIDAS)


def _es_url_interna_gratuita(url: str) -> bool:
    partes = urlsplit(url)
    return (
        partes.scheme == "https"
        and (partes.hostname or "").casefold() in HOSTS_LEGISCOMEX
        and not _ruta_excluida(url)
    )


def _parece_barrera_de_suscripcion(titulo: str, texto: str) -> bool:
    contenido = f"{titulo} {texto}".casefold()
    patrones = (
        r"contenido exclusivo para suscriptores",
        r"suscr[ií]bete para continuar",
        r"suscripci[oó]n requerida",
        r"inicia sesi[oó]n para continuar",
        r"adquiere tu suscripci[oó]n",
    )
    return any(re.search(patron, contenido) for patron in patrones)


def _enlaces_de_pagina(page) -> list[dict]:
    return page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => ({texto: (e.innerText || '').trim(), url: e.href}))",
    )


def _leer_pagina(page, url: str, robots: Scraper) -> tuple[dict | None, str | None]:
    if not _es_url_interna_gratuita(url):
        return None, "URL fuera del alcance gratuito"
    if not robots.is_allowed(url):
        raise RobotsDisallowedError(f"robots.txt disallows: {url}")

    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if response is not None and response.status >= 400:
        if response.status in (401, 403):
            return None, f"el sitio respondió HTTP {response.status}"
        raise RuntimeError(f"LegisComex respondió HTTP {response.status} para {url}")

    actual_url = _sanear_url(page.url)
    if not _es_url_interna_gratuita(actual_url):
        return None, "redirección fuera del alcance gratuito"

    titulo = page.title()
    texto = texto_limpio(page.locator("body").inner_text(timeout=15000))
    if _parece_barrera_de_suscripcion(titulo, texto):
        return None, "la página solicita suscripción o acceso"

    enlaces_raw = _enlaces_de_pagina(page)
    enlaces, documentos = clasificar_enlaces(enlaces_raw, actual_url)
    return {
        "titulo": titulo,
        "url": actual_url,
        "texto": texto,
        "enlaces": enlaces,
        "documentos": documentos,
    }, None


def _candidatos_articulos(enlaces: list[dict]) -> list[str]:
    urls: list[str] = []
    vistos: set[str] = set()
    for enlace in enlaces:
        url = _sanear_url(enlace.get("url") or "")
        ruta = urlsplit(url).path.rstrip("/").casefold()
        if (
            _es_url_interna_gratuita(url)
            and ruta not in ("", "/blog")
            and len((enlace.get("texto") or "").strip()) >= MIN_TEXTO_ENLACE_ARTICULO
            and len(ruta.strip("/").split("/")) <= 2
            and url not in vistos
        ):
            vistos.add(url)
            urls.append(url)
    return urls


def extraer_pagina(page, filtros: dict) -> dict:
    robots = Scraper()
    inicio, motivo = _leer_pagina(page, URL_INICIO, robots)
    if inicio is None:
        raise RuntimeError(f"No se pudo leer el perfil gratuito: {motivo}")

    if not pagina_logueada(page):
        raise SesionRequerida(
            "La sesión no es válida o expiró (la portada redirigió al login). "
            "Vuelve a ejecutar `python capturar_sesion.py`."
        )

    nombre = nombre_usuario(page)
    page.wait_for_timeout(ESPERA_ENTRE_PAGINAS_MS)
    blog, motivo = _leer_pagina(page, url_consulta(), robots)
    if blog is None:
        raise RuntimeError(f"No se pudo leer el blog público: {motivo}")

    try:
        limite = max(1, min(int(filtros.get("limite", MAX_ARTICULOS)), 100))
    except (TypeError, ValueError):
        limite = MAX_ARTICULOS

    paginas = [inicio, blog]
    omitidos: list[dict] = []
    urls_articulos = _candidatos_articulos(blog["enlaces"])
    for url in urls_articulos[:limite]:
        page.wait_for_timeout(ESPERA_ENTRE_PAGINAS_MS)
        articulo, motivo = _leer_pagina(page, url, robots)
        if articulo is None:
            omitidos.append({"url": url, "motivo": motivo})
        else:
            paginas.append(articulo)

    filtros_aplicados: list[str] = []
    termino = filtros.get("texto")
    if filtros.get("tipo") in {"texto", "busqueda"} and termino:
        termino_normalizado = str(termino).casefold()
        paginas = [
            pagina
            for pagina in paginas
            if termino_normalizado in pagina["titulo"].casefold()
            or termino_normalizado in pagina["texto"].casefold()
        ]
        filtros_aplicados.append(f"texto={termino}")

    filtros_omitidos = [
        clave
        for clave in ("pais", "partida", "fecha_desde", "fecha_hasta", "filtros_extra")
        if filtros.get(clave) not in (None, "", {})
    ]
    if termino and filtros.get("tipo") not in {"texto", "busqueda"}:
        filtros_omitidos.append("texto")
    enlaces_raw = [
        enlace for pagina in paginas for enlace in pagina["enlaces"]
    ]
    enlaces, documentos = clasificar_enlaces(enlaces_raw, URL_INICIO)
    texto = texto_limpio(
        "\n\n".join(
            f"{pagina['titulo']}\n{pagina['texto']}" for pagina in paginas
        ),
        MAX_TEXTO,
    )
    registros = [
        {
            "titulo": pagina["titulo"],
            "detalle": f"{len(pagina['texto'])} caracteres de texto visible",
            "url": pagina["url"],
        }
        for pagina in paginas
    ]
    nota = (
        "Se consultaron únicamente la portada/perfil y el blog público con "
        "artículos enlazados. No se consultaron estadísticas ni rutas de "
        "suscripción. La búsqueda de texto es local; país, partida y fechas "
        "no se aplican a contenido editorial."
    )

    return {
        "mock": False,
        "consulta": filtros,
        "resumen": {
            "total": len(registros) + len(documentos),
            "tipo": filtros.get("tipo", "perfil"),
            "fuente": "legiscomex",
            "solo_cuenta_gratuita": True,
            "filtros_aplicados": bool(filtros_aplicados),
            "filtros": {
                "aplicados": bool(filtros_aplicados),
                "detalle": filtros_aplicados,
                "omitidos": filtros_omitidos,
            },
            "paginas_omitidas": omitidos,
            "nota": nota,
        },
        "perfil": {"nombre_usuario": nombre, "url": URL_INICIO},
        "titulo": blog["titulo"],
        "url": blog["url"],
        "texto": texto,
        "registros": registros,
        "paginas": paginas,
        "enlaces": enlaces[:200],
        "documentos": documentos[:100],
    }
