"""Requests per second of each route and Service, from Traefik's metrics in Prometheus.

Traefik's Gateway API provider names each backend
`httproute-{ns}-{route}-gw-{gw ns}-{gw}-ep-{listener}-{rule}-{hash}`
`-svc-{ns}-{service}-{n}@kubernetesgateway`.
Names contain dashes, so labels are never split: they are matched against the routes
and Services the galaxy already knows, with anchored patterns. Labels are never
published; only the numbers, on objects of visible projects.
"""

import re

from ..contract.models import Traffic
from .raw import Snapshot


def rates(snapshot: Snapshot) -> dict[str, float]:
    """Traefik service label -> requests per second."""
    result = {}
    for item in snapshot["traffic"]:
        label = (item.get("metric") or {}).get("service")
        try:
            value = float((item.get("value") or [0, "nan"])[1])
        except (TypeError, ValueError):
            continue
        if label and value == value and value >= 0:  # drops NaN (no samples yet)
            result[label] = value
    return result


def route_traffic(rates: dict[str, float], namespace: str, route: str) -> Traffic:
    prefix = f"httproute-{namespace}-{route}-gw-"
    return _traffic([v for label, v in rates.items() if label.startswith(prefix)])


def service_traffic(rates: dict[str, float], namespace: str, service: str) -> Traffic:
    pattern = re.compile(rf"^httproute-.*-svc-{re.escape(namespace)}-{re.escape(service)}-\d+@")
    return _traffic([v for label, v in rates.items() if pattern.match(label)])


def _traffic(values: list[float]) -> Traffic:
    """No matching series means no data, not zero traffic."""
    return Traffic(requests_per_second=round(sum(values), 3)) if values else Traffic()
