# astrolabio-api

Reads the Kubernetes cluster live and serves it, sanitized, as a galaxy.

## Commands

```
uv sync                                   # install deps from uv.lock
uv run pytest                             # tests
uv run ruff check . && uv run ruff format --check .
uv run export-contract                    # regenerate ../contract/ after changing the contract
ASTROLABIO_ENV=development uv run uvicorn astrolabio_api.main:app --reload
```

## How the code is organized

Data flows in one direction, and each layer only talks to the next one:

```
Kubernetes API ──► kube/ ──► assembly/ ──► contract/ ──► routes/ ──► browser
                  (watch)   (build the     (public       (HTTP)
                             galaxy)        shape)
```

| Module | Responsibility | Status |
| --- | --- | --- |
| `main.py` | Builds the FastAPI app and plugs the routers in. No logic. | done |
| `config.py` | Every environment variable the API reads (`ASTROLABIO_ENV`). | done |
| `contract/` | The public shape of the data. **Nothing leaves the API without passing through these models.** | done |
| `contract/models.py` | Pydantic models of `GET /api/galaxy`, `extra="forbid"`, public-repo validators. | done |
| `contract/example.py` | Example galaxy covering every state; web fixture and temporary data source. | done |
| `contract/export.py` | `export-contract` CLI: writes JSON Schema + example to `../contract/`. | done |
| `routes/` | Thin HTTP layer, one module per endpoint group. GET only. | done |
| `routes/galaxy.py` | `GET /api/galaxy`. Serves the example until `assembly/` exists. | done |
| `kube/` | Informers: one `list` + `watch` per resource, in-memory cache, re-list on `410 Gone`. | E1.3–E1.4 |
| `assembly/` | Turns the cache into a `Galaxy`: annotations, commit from the image tag, Argo status, visible namespaces, infra catalog. | E1.5–E1.6 |
| `routes/ws.py` | `/ws`: pushes deltas from the informers. | phase 3 |

Rules that keep the layers honest:

- `kube/` knows Kubernetes and nothing about the contract.
- `assembly/` is the only place that reads raw k8s objects and builds contract models. It is pure (cache in, `Galaxy` out), so it is tested without a cluster.
- `routes/` never touches k8s objects; it only returns contract models.

Tests mirror this layout: `tests/contract/`, `tests/routes/`, and later `tests/kube/` and `tests/assembly/`.
