"""Safe readers for raw API JSON: missing fields read as empty, never as errors."""

from collections.abc import Mapping
from typing import Any

RawObject = dict[str, Any]
Snapshot = Mapping[str, list[RawObject]]  # raw objects by resource key (`kube/cluster.py`)


def name(obj: RawObject) -> str:
    return obj["metadata"]["name"]


def namespace(obj: RawObject) -> str | None:
    return obj["metadata"].get("namespace")


def labels(obj: RawObject) -> dict[str, str]:
    return obj["metadata"].get("labels") or {}


def annotations(obj: RawObject) -> dict[str, str]:
    return obj["metadata"].get("annotations") or {}


def spec(obj: RawObject) -> dict[str, Any]:
    return obj.get("spec") or {}


def status(obj: RawObject) -> dict[str, Any]:
    return obj.get("status") or {}


def controller(obj: RawObject) -> tuple[str, str] | None:
    """(kind, name) of the object's controlling owner."""
    for ref in obj["metadata"].get("ownerReferences") or []:
        if ref.get("controller"):
            return ref["kind"], ref["name"]
    return None


def in_namespace(objects: list[RawObject], ns: str) -> list[RawObject]:
    return sorted((o for o in objects if namespace(o) == ns), key=name)


def image_tag(image: str) -> str | None:
    """`registry/repo:tag` -> `tag`; None for untagged or digest-only images."""
    image = image.split("@", 1)[0]
    last = image.rsplit("/", 1)[-1]
    return last.split(":", 1)[1] if ":" in last else None
