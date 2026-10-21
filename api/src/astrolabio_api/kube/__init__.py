"""Kubernetes layer: informers that keep raw cluster objects cached in memory.

- `informer.py`: generic list + watch with an in-memory cache and re-list on `410 Gone`.

It knows Kubernetes and nothing about the contract: it caches raw API JSON as
dicts, and only `assembly/` reads them.
"""
