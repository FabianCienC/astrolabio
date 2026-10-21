"""Our `fabiancienfuegos.com/*` annotations, in Spanish in `homelab-gitops`, to contract values.

Only these keys are read. An unknown value becomes None, never passes through raw.
"""

from ..contract.models import Criticality, Role, is_public_repo

PREFIX = "fabiancienfuegos.com/"
VISIBLE_LABEL = PREFIX + "astrolabio"  # label, value "visible"
PROJECT = PREFIX + "proyecto"
DESCRIPTION = PREFIX + "descripcion"
REPO = PREFIX + "repo"
ROLE = PREFIX + "rol"
CRITICALITY = PREFIX + "criticidad"

_ROLES: dict[str, Role] = {
    "frontend": "frontend",
    "api": "api",
    "worker": "worker",
    "datos": "data",
}
_CRITICALITIES: dict[str, Criticality] = {"alta": "high", "media": "medium", "baja": "low"}
_TEXT_LIMIT = 200  # `Text` in the contract


def text(value: str | None) -> str | None:
    """Free text: trimmed and cut to the contract's limit; empty reads as None."""
    value = (value or "").strip()
    if len(value) > _TEXT_LIMIT:
        value = value[: _TEXT_LIMIT - 1].rstrip() + "…"
    return value or None


def role(value: str | None) -> Role | None:
    return _ROLES.get((value or "").strip().lower())


def criticality(value: str | None) -> Criticality | None:
    return _CRITICALITIES.get((value or "").strip().lower())


def repo(value: str | None) -> str | None:
    value = (value or "").strip().removesuffix("/")
    return value if is_public_repo(value) else None
