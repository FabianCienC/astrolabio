"""Kubernetes quantities from metrics-server become millicores and MiB."""

import pytest

from astrolabio_api.assembly.metrics import cpu_millicores, memory_mib, total
from astrolabio_api.contract.models import Metrics


@pytest.mark.parametrize(
    ("quantity", "millicores"),
    [("3141592n", 3.141592), ("2500u", 2.5), ("5m", 5), ("1", 1000), ("0.5", 500), ("x", None)],
)
def test_cpu(quantity, millicores):
    expected = None if millicores is None else pytest.approx(millicores)
    assert cpu_millicores(quantity) == expected


@pytest.mark.parametrize(
    ("quantity", "mib"),
    [("12288Ki", 12), ("20Mi", 20), ("1Gi", 1024), ("1048576", 1), ("3Pi", None), ("", None)],
)
def test_memory(quantity, mib):
    expected = None if mib is None else pytest.approx(mib)
    assert memory_mib(quantity) == expected


def test_total_ignores_objects_without_metrics():
    assert total([Metrics(), Metrics()]) == Metrics()
    assert total([Metrics(cpu_millicores=3, memory_mib=10), Metrics()]) == Metrics(
        cpu_millicores=3, memory_mib=10
    )
