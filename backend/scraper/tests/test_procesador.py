from types import SimpleNamespace

import pytest

from scraper import procesador
from scraper.extractor import RobotsDisallowedError, Scraper
from scraper.legiscomex import clasificar_enlaces, extraer_pagina, texto_limpio
from scraper.sesion import SesionRequerida


def test_mock_por_defecto(monkeypatch):
    monkeypatch.setenv("PHANTOMPASS_MOCK", "1")
    resultado = procesador.procesar_consulta({"tipo": "perfil"})
    assert resultado["mock"] is True


def test_real_sin_sesion(monkeypatch, tmp_path):
    monkeypatch.setenv("PHANTOMPASS_MOCK", "0")
    monkeypatch.setenv("LEGIS_STATE_FILE", str(tmp_path / "no-existe.json"))
    with pytest.raises(SesionRequerida):
        procesador.procesar_consulta({"tipo": "perfil"})


def test_texto_limpio():
    assert texto_limpio("  hola \n\n mundo  ") == "hola mundo"
    assert texto_limpio("abcdef", max_chars=3) == "abc"


def test_clasificar_enlaces_resuelve_y_separa_documentos():
    enlaces, documentos = clasificar_enlaces(
        [
            {"texto": "Doc", "url": "/files/a.pdf"},
            {"texto": "Página", "url": "/ir/49"},
            {"texto": "Excel", "url": "https://x/b.xlsx"},
            {"texto": "Duplicado", "url": "/files/a.pdf"},
            {"texto": "Cerrar sesión", "url": "/user/logout?token=secret"},
            {"texto": "Planes", "url": "/planes"},
        ],
        "https://www.legiscomex.com",
    )
    assert [e["url"] for e in enlaces] == [
        "https://www.legiscomex.com/files/a.pdf",
        "https://x/b.xlsx",
    ]
    assert all("token=" not in e["url"] for e in enlaces)
    assert {d["url"] for d in documentos} == {
        "https://www.legiscomex.com/files/a.pdf",
        "https://x/b.xlsx",
    }


class _FakeLocator:
    def __init__(self, texto):
        self._texto = texto

    def inner_text(self, timeout=None):
        return self._texto


class _FakePage:
    def __init__(self):
        self.url = ""
        self.visitas = []
        self.esperas = []

    def goto(self, url, **kwargs):
        self.url = url
        self.visitas.append(url)
        return SimpleNamespace(status=200)

    def wait_for_timeout(self, ms):
        self.esperas.append(ms)

    def title(self):
        return {
            "https://www.legiscomex.com/": "LegisComex",
            "https://www.legiscomex.com/blog": "Blog LegisComex",
            "https://www.legiscomex.com/articulo-gratuito": "Artículo gratuito",
        }[self.url]

    def locator(self, selector):
        if selector == "#dropdownMenuButton":
            return _FakeLocator("Cuenta de prueba")
        return _FakeLocator(f"Contenido visible en {self.url}")

    def eval_on_selector_all(self, selector, expression):
        if self.url == "https://www.legiscomex.com/":
            return [
                {"texto": "Blog", "url": "https://www.legiscomex.com/blog"},
                {"texto": "Ingresar", "url": "https://www.legiscomex.com/ir/49"},
            ]
        if self.url == "https://www.legiscomex.com/blog":
            return [
                {
                    "texto": (
                        "Artículo gratuito con información de comercio exterior"
                    ),
                    "url": "https://www.legiscomex.com/articulo-gratuito",
                },
                {
                    "texto": "Suscripción",
                    "url": "https://www.legiscomex.com/planes",
                },
                {"texto": "Documento", "url": "https://x/a.pdf"},
            ]
        return [{"texto": "Documento", "url": "https://x/a.pdf"}]


def test_extraer_pagina_usa_perfil_blog_y_articulos_gratuitos(monkeypatch):
    monkeypatch.setattr(Scraper, "is_allowed", lambda self, url: True)
    monkeypatch.setattr("scraper.legiscomex.pagina_logueada", lambda page: True)
    monkeypatch.setattr(
        "scraper.legiscomex.nombre_usuario", lambda page: "Cuenta de prueba"
    )
    page = _FakePage()

    resultado = extraer_pagina(page, {"tipo": "perfil", "limite": 5})

    assert resultado["mock"] is False
    assert resultado["perfil"]["nombre_usuario"] == "Cuenta de prueba"
    assert [pagina["titulo"] for pagina in resultado["paginas"]] == [
        "LegisComex",
        "Blog LegisComex",
        "Artículo gratuito",
    ]
    assert resultado["documentos"] == [
        {"texto": "Documento", "url": "https://x/a.pdf"}
    ]
    assert "https://www.legiscomex.com/ir/49" not in page.visitas
    assert "https://www.legiscomex.com/planes" not in page.visitas
    assert page.visitas == [
        "https://www.legiscomex.com/",
        "https://www.legiscomex.com/blog",
        "https://www.legiscomex.com/articulo-gratuito",
    ]
    assert resultado["resumen"]["filtros_aplicados"] is False


def test_extraer_pagina_no_navega_si_robots_deniega(monkeypatch):
    monkeypatch.setattr(Scraper, "is_allowed", lambda self, url: False)
    page = _FakePage()

    with pytest.raises(RobotsDisallowedError):
        extraer_pagina(page, {"tipo": "perfil"})

    assert page.visitas == []


def test_extraer_pagina_filtra_texto_en_contenido_publico(monkeypatch):
    monkeypatch.setattr(Scraper, "is_allowed", lambda self, url: True)
    monkeypatch.setattr("scraper.legiscomex.pagina_logueada", lambda page: True)
    monkeypatch.setattr(
        "scraper.legiscomex.nombre_usuario", lambda page: "Cuenta de prueba"
    )

    resultado = extraer_pagina(_FakePage(), {"tipo": "texto", "texto": "artículo"})

    assert [registro["titulo"] for registro in resultado["registros"]] == [
        "Artículo gratuito"
    ]
    assert resultado["resumen"]["filtros_aplicados"] is True
    assert resultado["resumen"]["filtros"]["detalle"] == ["texto=artículo"]
