# astrolabio-api

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run exportar-contrato            # regenera ../contrato/
ASTROLABIO_ENTORNO=desarrollo uv run uvicorn astrolabio_api.main:app --reload
```
