# Frontend — decisión de stack (pendiente)

**Estado: sin definir.** `frontend/` contiene un prototipo mínimo en **Flask**
para validar los datos. Es reemplazable: la elección final de tecnología (Next.js,
Flask, Streamlit u otra) está abierta.

## Opciones evaluadas

| Opción    | Pros | Contras | Cuándo conviene |
|-----------|------|---------|-----------------|
| **Flask** (prototipo actual) | Mismo lenguaje que el backend; SSR con Jinja; simple de desplegar | UI menos interactiva; requiere escribir HTML/JS a mano | Dashboard interno rápido |
| **Next.js** (React) | SPA moderna, ecosistema, deploy en Vercel, buena DX | Otro stack (Node); consume el backend vía API JSON | Producto público / UI rica |
| **Streamlit** | Prototipo de datos en minutos | Poco control de UI y de despliegue | Exploración interna temporal |

## Preguntas para decidir

1. ¿Es un **dashboard interno** o un **producto público**?
2. ¿Ya hay **hosting** definido (Vercel, VM, contenedor, PaaS)?
3. ¿Se necesita **interactividad** / actualización en tiempo real?

## Contrato con el backend (independiente del stack)

Cualquier frontend debe consumir los datos por una **API JSON** del backend, no
acoplarse a `sources.yaml`. Contrato sugerido:

```
GET /api/records        -> [{ "title": "...", "url": "..." }, ...]
GET /health             -> { "status": "ok" }
```

Así se puede cambiar Flask por Next.js (o cualquier otro) sin tocar el scraper.
