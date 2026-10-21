"""Public contract: the only shape in which cluster data leaves the API.

- `models.py`: Pydantic models of `GET /api/galaxy` (allowlist of fields).
- `example.py`: an example galaxy covering every state, used as the web fixture.
- `export.py`: writes the JSON Schema and the example to `contract/` at the repo root.
"""
