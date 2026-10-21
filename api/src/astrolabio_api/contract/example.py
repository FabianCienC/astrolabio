"""Example galaxy: a snapshot of the real cluster, already sanitized by the contract.

`snapshot.json` is what the live site served (`uv run snapshot-example` refreshes
it). It feeds the web fixture (through `contract/galaxy.example.json`), the API
without a cluster (`ASTROLABIO_SOURCE=example`) and the tests.
"""

from functools import cache
from pathlib import Path

from .models import Galaxy

SNAPSHOT = Path(__file__).with_name("snapshot.json")


@cache
def example_galaxy() -> Galaxy:
    # Models are frozen, so every caller can share the one parsed galaxy.
    return Galaxy.model_validate_json(SNAPSHOT.read_text(encoding="utf-8"))
