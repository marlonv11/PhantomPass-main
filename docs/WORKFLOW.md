# Guía de trabajo (WORKFLOW)

Reglas de colaboración y control de calidad para PhantomPass.

## 1. Ramas

- `main` — solo código estable, ya revisado y con CI en verde.
- `feature/<nombre>` — nuevas funcionalidades.
- `fix/<nombre>` — correcciones.

```bash
git checkout -b feature/scraper-extractor
git add .
git commit -m "feat(scraper): add extractor with robots.txt check"
git push origin feature/scraper-extractor
```

Abre un **Pull Request** hacia `main` y solicita revisión.

## 2. Definición de "Hecho" (Definition of Done)

Una feature solo se considera terminada cuando:

1. Tiene **tests** (unitarios y, si aplica, de integración) que pasan.
2. `pytest` pasa en local **y** en CI (`.github/workflows/tests.yml`).
3. No expone secretos ni credenciales (usa variables de entorno / `.env`, nunca hardcode).
4. El código sigue **PEP 8** (recomendado: `ruff` / `black`).
5. La documentación relevante está actualizada.
6. Al menos **1 aprobación** de otro miembro (2 para cambios sensibles).

## 3. Proceso de verificación antes de mergear

```bash
pip install -r backend/requirements.txt
pytest -q                      # toda la suite
ruff check .                   # estilo / lint (si está instalado)
```

Checklist del PR:

- [ ] Tests añadidos/actualizados y en verde.
- [ ] Sin secretos en el diff.
- [ ] Sin `print()` de depuración ni código comentado muerto.
- [ ] Cambios acotados al alcance del issue.

## 4. Implementación con verificación

Para cada módulo nuevo:

1. Diseña una interfaz clara (ej: `Scraper.fetch(url) -> str`).
2. Escribe los tests **antes o junto** con la implementación.
3. Documenta el uso (docstring + actualización de README si aplica).
4. Verifica con `pytest` antes de abrir el PR.

## 5. Issues

Formato de título: `[BACK] ...`, `[FRONT] ...`, `[DOCS] ...`, `[FIX] ...`.

Ejemplos:

- `[BACK] Extractor con BeautifulSoup y validación de robots.txt`
- `[BACK] Limpieza/normalización de datos scrapeados`
- `[FRONT] Dashboard Flask que lista los datos extraídos`
- `[DOCS] Guía de setup y testing`

Cada issue debe incluir: contexto, criterios de aceptación y checklist de tests.

## 6. Reglas de scraping (uso ético)

- Respeta `robots.txt` y los Términos de Servicio del sitio.
- Usa APIs oficiales cuando existan.
- Limita la tasa de peticiones (rate limiting) y no sobrecargues servidores.
- No recolectes datos personales sin base legal.
- No se aceptan módulos para eludir CAPTCHAs ni protecciones anti-bot.
