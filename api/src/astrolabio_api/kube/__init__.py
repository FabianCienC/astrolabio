"""Kubernetes layer: informers that keep raw cluster objects cached in memory.

- `informer.py`: generic list + watch with an in-memory cache and re-list on `410 Gone`.
- `source.py`: the informer's `Source` over kubernetes_asyncio, reading raw JSON.
- `cluster.py`: one informer per watched resource; `snapshot()` is what `assembly/` reads.

It knows Kubernetes and nothing about the contract: it caches raw API JSON as
dicts, and only `assembly/` reads them.
"""
