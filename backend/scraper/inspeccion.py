"""Inspección de controles y enlaces del blog público de LegisComex."""

from __future__ import annotations

import json
from pathlib import Path

from .extractor import RobotsDisallowedError, Scraper
from .legiscomex import url_consulta
from .sesion import SesionRequerida, pagina_logueada

_JS_CONTROLES = """
() => Array.from(
  document.querySelectorAll('input, select, textarea, button, a[href]')
).map(el => ({
  tag: el.tagName.toLowerCase(),
  id: el.id || null,
  name: el.getAttribute('name'),
  type: el.getAttribute('type'),
  placeholder: el.getAttribute('placeholder'),
  aria: el.getAttribute('aria-label'),
  role: el.getAttribute('role'),
  text: (el.innerText || el.value || '').trim().slice(0, 120),
  href: (() => {
    if (!el.href) return null;
    const url = new URL(el.href);
    if (/\/user\/logout/i.test(url.pathname)) return null;
    for (const key of ['access_token', 'auth', 'session', 'sessionid', 'token']) {
      url.searchParams.delete(key);
    }
    return url.href;
  })(),
  visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
}))
"""


def controles_de_frame(frame) -> list[dict]:
    try:
        return frame.evaluate(_JS_CONTROLES)
    except Exception:
        return []


def inspeccionar(page, destino: Path, navegar: bool = True) -> dict:
    """Navega al blog si hace falta y guarda controles no sensibles."""
    if navegar:
        url = url_consulta()
        if not Scraper().is_allowed(url):
            raise RobotsDisallowedError(f"robots.txt disallows: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

    if not pagina_logueada(page):
        raise SesionRequerida(
            "La sesión no es válida o expiró. Vuelve a ejecutar capturar_sesion.py."
        )

    frames = []
    for frame in page.frames:
        controles = controles_de_frame(frame)
        if controles:
            try:
                url = frame.url
            except Exception:
                url = None
            frames.append({"url": url, "controles": controles})

    datos = {"url": page.url, "titulo": page.title(), "frames": frames}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return datos
