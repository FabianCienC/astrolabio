"""Takes the example galaxy from the live site: a faithful snapshot of the cluster.

uv run snapshot-example                 # from https://astrolabio.fabiancienfuegos.com
uv run snapshot-example --url URL       # from another API (a local uvicorn, say)

What `GET /api/galaxy` serves has already passed through the contract, so it is
safe to commit. Run `uv run export-contract` afterwards to refresh `contract/`.
"""

import argparse
import json
import urllib.request
from pathlib import Path

from .models import Galaxy

SNAPSHOT = Path(__file__).with_name("snapshot.json")
PUBLIC_API = "https://astrolabio.fabiancienfuegos.com/api/galaxy"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=PUBLIC_API)
    args = parser.parse_args()

    # Cloudflare turns away urllib's default User-Agent as a bot.
    request = urllib.request.Request(args.url, headers={"User-Agent": "astrolabio-snapshot"})
    with urllib.request.urlopen(request, timeout=15) as response:
        galaxy = Galaxy.model_validate(json.load(response))
    SNAPSHOT.write_text(galaxy.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    projects = ", ".join(c.id for c in galaxy.constellations)
    print(
        f"wrote {SNAPSHOT.name}: {projects}; {len(galaxy.core.components)} components; "
        "now run `uv run export-contract`"
    )
