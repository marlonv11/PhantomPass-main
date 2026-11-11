"""Manejo de sesión de Playwright para LegisComex.

La sesión se captura manualmente una vez con `backend/capturar_sesion.py` y se
guarda como `storage_state` (por defecto `backend/sesion.json`). El scraper real
reutiliza esa sesión para no repetir el CAPTCHA en cada consulta.

No modifica `phatomCatch.py`.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from playwright.sync_api import Browser, Page, Playwright, sync_playwright


class SesionRequerida(RuntimeError):
    """No hay una sesión válida; hay que capturarla manualmente."""


def ruta_estado() -> Path:
    """Ruta del storage_state. Configurable con LEGIS_STATE_FILE."""
    valor = os.getenv("LEGIS_STATE_FILE")
    if valor:
        return Path(valor).expanduser()
    return Path(__file__).resolve().parents[1] / "sesion.json"


def _canal_por_defecto() -> Optional[str]:
    """Lee el navegador predeterminado de Windows y lo mapea a Playwright."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
        ) as key:
            progid = winreg.QueryValueEx(key, "ProgId")[0]
    except Exception:
        return None
    return {
        "MSEdgeHTM": "msedge",
        "ChromeHTML": "chrome",
        "FirefoxURL": "firefox",
    }.get(progid)


def elegir_canal(nombre: Optional[str]) -> Optional[str]:
    nombre = (nombre or "auto").lower()
    if nombre == "auto":
        return _canal_por_defecto()
    return {
        "edge": "msedge",
        "msedge": "msedge",
        "chrome": "chrome",
        "firefox": "firefox",
        "chromium": None,
    }.get(nombre)


def lanzar(p: Playwright, canal: Optional[str], headless: bool) -> Browser:
    if canal == "firefox":
        return p.firefox.launch(headless=headless)
    kwargs = {"headless": headless, "args": ["--no-proxy-server"]}
    if canal:
        kwargs["channel"] = canal
    return p.chromium.launch(**kwargs)


def nombre_usuario(page: Page) -> Optional[str]:
    """Devuelve el nombre del menú de usuario (indica sesión iniciada)."""
    try:
        texto = page.locator("#dropdownMenuButton").first.inner_text(timeout=2000)
    except Exception:
        return None
    texto = (texto or "").strip()
    return texto or None


def pagina_logueada(page: Page) -> bool:
    """Heurística: no estamos en el login y existe el menú de usuario."""
    url = (page.url or "").lower()
    if "new_login" in url or "sso.legis.com.co" in url:
        return False
    if nombre_usuario(page):
        return True
    try:
        if page.locator("input[type='password']").first.is_visible(timeout=1000):
            return False
    except Exception:
        pass
    return False


@contextmanager
def abrir_pagina() -> Iterator[Page]:
    """Abre el navegador con la sesión guardada y entrega una página."""
    estado = ruta_estado()
    if not estado.exists():
        raise SesionRequerida(
            f"No hay sesión guardada en {estado}. Ejecuta "
            "`python capturar_sesion.py` desde backend/ e inicia sesión manualmente."
        )

    headless = os.getenv("HEADLESS", "0") == "1"
    canal = elegir_canal(os.getenv("LEGIS_BROWSER", "auto"))

    with sync_playwright() as p:
        browser = lanzar(p, canal, headless)
        try:
            try:
                context = browser.new_context(
                    storage_state=str(estado), locale="es-CO"
                )
            except Exception as exc:
                raise SesionRequerida(
                    f"No se pudo cargar la sesión {estado}: {exc}. "
                    "Vuelve a ejecutar `python capturar_sesion.py`."
                ) from exc
            page = context.new_page()
            yield page
        finally:
            browser.close()
