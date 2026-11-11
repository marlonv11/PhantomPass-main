# Setup

## Requisitos

- Python 3.10+
- Git

## Instalación

```bash
git clone https://github.com/JoseMorales44/PhantomPass.git
cd PhantomPass

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

pip install -r backend/requirements.txt
```

## Variables de entorno

Crea un archivo `.env` (ignorado por git) si necesitas configuración local:

```dotenv
# Ejemplo
LOG_LEVEL=INFO
```

Nunca subas `.env` ni claves al repositorio.

## Ejecutar

```bash
# Backend
python backend/main.py --url https://example.com

# Dashboard (desarrollo local)
python frontend/app.py
```

Por defecto escucha en `http://127.0.0.1:5000`. El **host de despliegue del
frontend aún no está definido**; host/puerto son configurables:

```bash
# Windows
$env:FLASK_HOST="0.0.0.0"; $env:FLASK_PORT="8080"; python frontend/app.py
# Linux/macOS
FLASK_HOST=0.0.0.0 FLASK_PORT=8080 python frontend/app.py
```

Variables soportadas: `FLASK_HOST` (default `127.0.0.1`), `FLASK_PORT`
(default `5000`), `FLASK_DEBUG` (`1`/`0`, default `1`).

> La **tecnología del frontend** aún no está decidida (Flask es solo el prototipo
> actual; podría ser Next.js u otra). Ver [FRONTEND.md](FRONTEND.md).
