# Testing

Usamos **pytest**.

## Ejecutar la suite

```bash
pip install -r backend/requirements.txt
pytest -q
```

## Ejecutar un módulo específico

```bash
pytest backend/scraper/tests/ -q
pytest frontend/tests/ -q
```

## Convenciones

- Archivos: `test_*.py`.
- Nombres de test: `test_<comportamiento>()`.
- Tests unitarios sin red: usa `unittest.mock` para aislar `requests`/I/O.
- Los tests de integración (con red) deben estar marcados y ser opcionales en CI.

## CI

`.github/workflows/tests.yml` ejecuta `pytest` en cada push y PR. Un PR no se
mergea si el CI está en rojo.
