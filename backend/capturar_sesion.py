"""Captura manual de la sesión de LegisComex.

Abre un navegador visible en el login, espera a que inicies sesión a mano y
guarda `storage_state` en `backend/sesion.json` (o `LEGIS_STATE_FILE`). El
scraper real reutiliza esa sesión para no repetir el CAPTCHA en cada consulta.

Uso (desde `backend/`):
    python capturar_sesion.py
    python capturar_sesion.py --browser chrome --out otra_sesion.json
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from scraper.inspeccion import inspeccionar
from scraper.legiscomex import URL_INICIO
from scraper.sesion import elegir_canal, lanzar, pagina_logueada, ruta_estado

LOGIN_URL = "https://www.legiscomex.com/legis_sso/new_login"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Captura manual de la sesión de LegisComex."
    )
    parser.add_argument("--url", default=LOGIN_URL, help="URL de login")
    parser.add_argument(
        "--out",
        default=None,
        help="Archivo storage_state (por defecto backend/sesion.json)",
    )
    parser.add_argument(
        "--browser",
        default="auto",
        choices=["auto", "edge", "chrome", "firefox", "chromium"],
        help="Navegador a usar; auto = el predeterminado del sistema",
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Guardar una inspección no sensible de la portada/blog gratuitos",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Segundos a esperar el login manual (por defecto 300)",
    )
    return parser


def _esperar_login_manual(page, timeout_s: int) -> bool:
    """Espera sin bloquear a que el usuario inicie sesión en el navegador."""
    page.bring_to_front()
    print("[info] Inicia sesión manualmente en el navegador (incluido el CAPTCHA).")
    print(f"[info] Esperando hasta {timeout_s}s a detectar la sesión...")
    fin = time.time() + timeout_s
    ultimo_url = None
    while time.time() < fin:
        if page.is_closed():
            return False
        try:
            if pagina_logueada(page):
                return True
            url = page.url
            if url != ultimo_url:
                print(f"[info] URL actual: {url}")
                ultimo_url = url
        except Exception:
            pass
        page.wait_for_timeout(1000)
    return False


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    destino = Path(args.out).expanduser() if args.out else ruta_estado()
    canal = elegir_canal(args.browser)

    with sync_playwright() as p:
        browser = lanzar(p, canal, headless=False)
        try:
            context = browser.new_context(locale="es-CO")
            page = context.new_page()
            page.goto(args.url, wait_until="domcontentloaded")
            print(f"[info] navegador: {canal or 'chromium'}")

            if not _esperar_login_manual(page, args.timeout):
                print("[error] No se detectó una sesión iniciada; no se guardó nada.")
                return 1

            print(f"[info] Verificando sesión en {URL_INICIO} ...")
            page.goto(URL_INICIO, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            if not pagina_logueada(page):
                print("[warn] La portada redirigió al login; la sesión podría no ser válida.")

            destino.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(destino))
            print(f"[ok] Sesión guardada en {destino}")

            if args.dump:
                destino_dump = destino.parent / "inspeccion_paginas_gratuitas.json"
                try:
                    inspeccionar(page, destino_dump, navegar=False)
                    print(f"[ok] Inspección guardada en {destino_dump}")
                except Exception as exc:
                    print(f"[warn] No se pudo inspeccionar la página: {exc}")

            print(
                "[info] Para usar datos reales: PHANTOMPASS_MOCK=0 en backend/.env "
                "y reinicia la API."
            )
            return 0
        finally:
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
