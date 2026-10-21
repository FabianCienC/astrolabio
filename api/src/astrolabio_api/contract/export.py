"""Exports the contract to `contract/` at the repo root, for the web.

uv run export-contract           # writes the files
uv run export-contract --check   # fails if they are out of date (CI)
"""

import argparse
import json
import sys
from pathlib import Path

from .example import example_galaxy
from .models import Galaxy

OUTPUT_DIR = Path(__file__).resolve().parents[4] / "contract"


def render() -> dict[str, str]:
    """File name -> content of every exported file."""
    schema = Galaxy.model_json_schema(mode="serialization")
    return {
        "galaxy.schema.json": json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        "galaxy.example.json": example_galaxy().model_dump_json(indent=2) + "\n",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    outdated = []
    for name, content in render().items():
        path = OUTPUT_DIR / name
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        if args.check:
            outdated.append(name)
        else:
            OUTPUT_DIR.mkdir(exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"wrote {path}")

    if outdated:
        print(
            f"contract out of date: {', '.join(outdated)}; run `uv run export-contract`",
            file=sys.stderr,
        )
        sys.exit(1)
