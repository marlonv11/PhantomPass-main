# PhantomPass

Toolkit de **scraping ético** y **monitoreo de datos** con backend en Python y dashboard en Flask.

> Este proyecto scrapea únicamente fuentes que lo permiten (APIs oficiales, datos públicos, o sitios cuyo `robots.txt` y Términos de Servicio lo autorizan). No incluye mecanismos para eludir CAPTCHAs ni otras protecciones anti-bot.

## Estructura

```
PhantomPass/
├── backend/
│   ├── scraper/
│   │   ├── extractor.py      # Fetch + parseo (requests + BeautifulSoup), respeta robots.txt
│   │   ├── data_cleaner.py   # Limpieza / normalización de datos
│   │   └── tests/
│   ├── main.py               # Orquestador (CLI)
│   └── requirements.txt
├── frontend/
│   ├── app.py                # Prototipo Flask (stack del front: TBD)
│   ├── templates/
│   ├── static/
│   └── tests/
├── docs/
│   ├── WORKFLOW.md           # Guía de trabajo y estándares
│   ├── SETUP.md              # Instalación
│   ├── TESTING.md            # Cómo ejecutar pruebas
│   └── FRONTEND.md           # Decisión de stack del front (pendiente)
├── .github/workflows/tests.yml
├── .gitignore
├── README.md
└── LICENSE
```

## Inicio rápido

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r backend/requirements.txt

# Backend: fuentes configuradas en backend/sources.yaml
python backend/main.py --list-sources
python backend/main.py --source example

# Fetch ad-hoc (respeta robots.txt)
python backend/main.py --url https://example.com --selector h1

# Dashboard (solo desarrollo local; el host de despliegue aún está por definir)
python frontend/app.py
# -> http://127.0.0.1:5000  (configurable con FLASK_HOST / FLASK_PORT)
```

> El destino de despliegue del frontend todavía no está decidido. `app.py` expone
> host y puerto por variables de entorno para poder moverlo a cualquier hosting
> (VM, contenedor, PaaS) cuando se defina.

> La **tecnología del frontend tampoco está definida**: `frontend/` es un
> prototipo Flask para validar los datos, pero puede reemplazarse por Next.js u
> otra opción. Ver [docs/FRONTEND.md](docs/FRONTEND.md).

## LegisComex: contenido gratuito

El modo real (`PHANTOMPASS_MOCK=0`) reutiliza una sesión capturada manualmente y
se limita a leer el nombre visible de la cuenta en la portada, `/blog` y sus
artículos enlazados. No visita estadísticas comerciales, rutas `/ir/`, páginas
de planes ni enlaces de suscripción. La búsqueda de texto se hace sobre el
contenido editorial ya leído; país, partida y fechas no aplican al blog.

Antes de cada navegación del extractor se verifica `robots.txt`. Si no se puede
consultar (por ejemplo, si responde 403), el trabajo falla sin abrir la página. Captura
la sesión con `python backend/capturar_sesion.py`; para usar datos reales,
configura `PHANTOMPASS_MOCK=0` en `backend/.env` y reinicia la API. El mock
permanece activo por defecto.

## Licencia

MIT — ver [LICENSE](LICENSE).
