# AGENTS.md — Contexto para agentes

Este archivo es la fuente de verdad para futuras sesiones de agentes. Léelo antes
de tocar el proyecto. Los requisitos de la empresa y su estado están en la sección 3.

## 1. Proyecto

PhantomPass: toolkit de scraping/monitoreo. Backend Python + Flask. El objetivo
actual es **automatizar una consulta en LegisComex** (con cuenta gratuita),
tratar el CAPTCHA del inicio de sesión y exponer el resultado por API para un
frontend visual.

## 2. Reglas del proyecto (no romper)

- **No modificar `backend/phatomCatch.py`** salvo autorización explícita del
  usuario: ya funciona y es la base del login.
- **Solo cuenta gratuita.** No usar endpoints, datos ni funciones de suscripción.
- **No traer datos de suscripción.** Basta con datos visibles tras el login
  gratuito (perfil del usuario o un bloque de texto de la página).
- **No hardcodear secretos.** Credenciales y API keys van en `backend/.env`
  (ya está en `.gitignore`). Nunca pegarlas en el chat ni en el repo.
- **No eludir protecciones.** `README.md` y `docs/WORKFLOW.md` prohíben módulos
  para eludir CAPTCHAs/anti-bot. Cualquier tratamiento del CAPTCHA debe ser un
  método **justificado y autorizado** (ver sección 10).
- Respetar `robots.txt` y los Términos de Servicio del sitio.
- Tests y verificación antes de dar algo por terminado (sección 8).

## 3. Requisitos de la empresa (estado)

| # | Requisito | Estado | Evidencia / brecha |
|---|-----------|--------|--------------------|
| 1 | Solicitud al backend con filtros | ✅ **Implementado** | `backend/api.py` (`POST /api/consultas`), validación, jobs, `backend/openapi.yaml`, `backend/tests/test_api.py` |
| 2 | Consultas en LegisComex | 🟡 **Parcial** | `backend/scraper/legiscomex.py` extrae el nombre visible de la cuenta, la portada, `/blog` y artículos enlazados. Excluye estadísticas y rutas de suscripción; falla cerrado si no puede verificar `robots.txt`. La búsqueda editorial por texto funciona localmente; país, partida y fechas no aplican. |
| 3 | Tratamiento automático del CAPTCHA | 🟡 **Parcial** | Método justificado implementado: login **manual asistido** una vez (`capturar_sesion.py`) + reutilización de sesión (`sesion.json`). Detección v3/invisible en `phatomCatch.py`; captcha de imagen hace OCR pero **no rellena**; automatización total del CAPTCHA sigue pendiente |
| 4 | Recuperación de datos o documentos | 🟡 **Parcial** | `legiscomex.py` extrae texto visible, enlaces y enlaces a documentos (PDF/XLS/XLSX/CSV/ZIP…). **Falta descargarlos** y guardarlos en `output/` |
| 5 | Resultado disponible mediante API | 🟡 **Parcial** | `GET /api/consultas/{id}` devuelve **datos reales** con `PHANTOMPASS_MOCK=0` y sesión válida (texto/enlaces/enlaces a documentos); por defecto sigue mock. Falta endpoint de descarga y persistencia |

Leyenda: ✅ hecho · 🟡 parcial · ❌ pendiente.

## 4. Mensajes/restricciones de la empresa

- No deben traer exactamente datos de la suscripción.
- Cualquier dato de la página tras ingresar con la **cuenta gratuita** es suficiente.
- Pueden elegir un **bloque de texto** o mirar su **propio perfil**.
- El **bloqueo por automatización está al inicio de la sesión** (CAPTCHA del login).
- **No requieren hacer ninguna suscripción.**
- El CAPTCHA se debe superar con **IA u otro método que el equipo justifique**.

## 5. Estado actual del código

### Backend

- `backend/phatomCatch.py` — login multi-sitio, detección de formulario/captcha,
  resolución v3/invisible/imagen. **No modificar.**
- `backend/phantompass.py` — menú CLI, selección de navegador (`auto` = Edge del
  sistema), `--close`, `--state` (guardar sesión), deja el navegador abierto.
- `backend/login_sites.yaml` — recetas (LegisComex: selectores + captcha invisible).
- `backend/api.py` — API Flask (requisito 1): salud, filtros, consultas, trabajos,
  estado de IA y preguntas a la IA.
- `backend/capturar_sesion.py` — **login manual asistido**: abre el navegador,
  esperas a iniciar sesión (incluido CAPTCHA) y guarda `storage_state` en
  `backend/sesion.json` (gitignored). Con `--dump` guarda una inspección no
  sensible de páginas gratuitas en `backend/inspeccion_paginas_gratuitas.json`.
- `backend/scraper/sesion.py` — carga la sesión guardada, lanza Edge/Chromium
  (`HEADLESS=0`), detecta sesión inválida y lanza `SesionRequerida`.
- `backend/scraper/legiscomex.py` — navega a la portada/perfil y al blog público
  con límite de artículos; excluye rutas comerciales/suscripción, comprueba
  `robots.txt` antes de navegar y quita tokens de enlaces de salida.
- `backend/scraper/filtros.py` — aplica filtros leyendo
  `backend/legiscomex_filtros.yaml`; si faltan selectores, no falla y reporta
  `aplicados: false`.
- `backend/scraper/inspeccion.py` — vuelca inputs/selects/botones/enlaces
  (incluyendo iframes) a JSON para mapear selectores.
- `backend/legiscomex_filtros.yaml` — plantilla anterior de filtros comerciales;
  no se usa para consultar contenido editorial.
- `backend/scraper/procesador.py` — seam API↔scraper. `PHANTOMPASS_MOCK=1`
  (defecto) → mock; `0` → `_resultado_real` con sesión guardada.
- `backend/scraper/ai.py` — cliente OpenRouter para responder preguntas sobre el
  resultado (no resuelve CAPTCHA).
- `backend/openapi.yaml` — contrato OpenAPI 3.0.3.
- `backend/scraper/` — fetch/parse existente (`extractor.py`, `data_cleaner.py`,
  `sources.py`) con tests.
- `backend/tests/` + `backend/scraper/tests/` — suite verificada en verde.

### Frontend

- `frontend/app.py` + `templates/index.html` — prototipo Flask **no conectado aún**
  a la API. El stack definitivo sigue abierto (`docs/FRONTEND.md`).

## 6. Requerimientos faltantes (trazabilidad)

1. **Requisito 2 (consulta real):**
   - ✅ reutilizar sesión (`storage_state` / `sesion.json`);
   - ✅ extraer perfil visible, portada, blog y artículos enlazados gratuitos;
   - ✅ excluir rutas de estadísticas/suscripción y verificar robots antes de
     navegar; 403/error al comprobar robots detiene la consulta;
   - ✅ filtro local de texto sobre páginas editoriales;
   - ❌ probar con sesión válida cuando el sitio permita verificar `robots.txt`;
     país, partida y fechas no aplican al blog.
2. **Requisito 3 (CAPTCHA):**
   - ✅ método justificado: login manual asistido una vez + reutilización de sesión;
   - ❌ automatización total del CAPTCHA; rellenar captcha de imagen (hoy solo OCR);
     re-login automático si la sesión expira; documentar la justificación.
3. **Requisito 4 (datos/documentos):**
   - ✅ extraer texto visible, enlaces y enlaces a documentos;
   - ❌ **descargar** documentos, guardarlos en `output/` (ignorado por git) y
     devolver rutas/URLs.
4. **Requisito 5 (API real):**
   - ✅ `GET /api/consultas/{id}` devuelve datos reales con `PHANTOMPASS_MOCK=0`;
   - ❌ endpoint de descarga de documentos; persistir trabajos (hoy en memoria).
5. **Frontend:** conectar el prototipo Flask (o Next.js) a `/api/filtros`,
   `/api/consultas`, `/api/consultas/{id}` y `/api/consultas/{id}/preguntar`.

## 7. Arquitectura acordada

```
Frontend ──POST /api/consultas──> API Flask (job "queued")
   │                                  │
   │<── 202 {id} ─────────────────────┘
   │                                  ▼
   │                        worker (ThreadPoolExecutor)
   │                                  │
   │                        procesar_consulta(filtros)
   │                                  ├─ Playwright (Edge/Chromium)
   │                                  ├─ sesión guardada (capturar_sesion.py)
   │                                  ├─ verificar robots.txt y límites de rutas
   │                                  ├─ extraer perfil/portada y blog público
   │                                  ├─ seguir artículos del mismo sitio con límite
   │                                  ▼
   └──GET /api/consultas/{id}──> job "done" + resultado
```

- El contrato de la API **no cambia** al conectar el scraper: solo se reemplaza
  el cuerpo de `procesar_consulta`.
- La IA (OpenRouter) es **post-procesamiento**: responde preguntas sobre el
  `resultado`, no hace scraping ni resuelve reCAPTCHA.

## 8. Cómo ejecutar y verificar

Desde `backend/` (bash):

```bash
# 1) Capturar sesión una vez (inicia sesión a mano en el navegador)
#    --dump guarda backend/inspeccion_paginas_gratuitas.json sin tokens
../.venv/Scripts/python.exe capturar_sesion.py --dump

# 2) API (dejar la terminal abierta)
../.venv/Scripts/python.exe api.py          # http://127.0.0.1:8000

# Tests
../.venv/Scripts/python.exe -m pytest tests scraper/tests -q

# CLI de login alternativo
../.venv/Scripts/python.exe phantompass.py
```

Para datos reales: `PHANTOMPASS_MOCK=0` en `backend/.env` y **reiniciar** la API.
La sesión queda en `backend/sesion.json` (gitignored); si expira, repetir el paso 1.

En PowerShell usar `..\.venv\Scripts\python.exe`.

## 9. Variables de entorno (`backend/.env`)

```env
LEGIS_USERNAME=...
LEGIS_PASSWORD=...
HEADLESS=0                  # LegisComex requiere navegador visible (0)
# LEGIS_STATE_FILE=backend/sesion.json
# LEGIS_BLOG_URL=https://www.legiscomex.com/blog
# LEGIS_BROWSER=auto        # auto | edge | chrome | firefox | chromium
# LEGIS_FILTROS_FILE=backend/legiscomex_filtros.yaml

OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=openai/gpt-4o-mini
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# OPENROUTER_TIMEOUT=60
# OPENROUTER_MAX_CONTEXT=12000

# PHANTOMPASS_MOCK=1        # 1 = mock (defecto); 0 = scraper real (requiere sesión)
# PHANTOMPASS_WORKERS=2
# PORT=8000
# CORS_ORIGIN=*
```

## 10. Riesgos y conflictos

- **CAPTCHA vs. política del repo:** la empresa pide superar el CAPTCHA; el
  README/WORKFLOW prohíben eludir anti-bot. Interpretación acordada: usar la
  cuenta real + un método **justificado y autorizado**. Implementado: login
  **manual asistido** una vez + reutilización de sesión; **no** hay bypass de
  reCAPTCHA. Documentar la justificación antes de producción.
- **reCAPTCHA real** no es automatizable de forma fiable; el login invisible es
  intermitente. Mitigación: reutilizar `sesion.json` y reintentos; si expira,
  repetir `capturar_sesion.py`.
- **Sesión expirada:** el scraper lanza `SesionRequerida` y el job termina en
  `error` con un mensaje claro; no reintenta login automáticamente.
- **Bloqueo de cuenta** por intentos fallidos repetidos: no hacer pruebas masivas
  de login; esperar entre intentos.
- **Almacén de jobs en memoria**: no sirve para producción multi-worker; migrar a
  SQLite/cola.
- **`*.json` está en `.gitignore`**: `sesion.json`, resultados y tokens no se
  commitean (correcto, son sensibles).
- **Documentos:** se listan enlaces, pero **no se descargan** todavía; falta
  endpoint de descarga y guardado en `output/`.

## 11. Próximo paso recomendado

1. **Verificar robots y acceso real** con sesión válida; hoy `robots.txt`
   responde 403 desde el entorno, por lo que la extracción real falla cerrado.
2. **Descargar documentos** encontrados y guardarlos en `output/`; exponer un
   endpoint de descarga.
3. **Probar la API real** con `PHANTOMPASS_MOCK=0` y una sesión válida.
4. **Conectar el frontend** al contrato de la API.

Mantener el contrato de la API intacto y añadir tests con HTML/JSON de ejemplo.
