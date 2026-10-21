"""The kubernetes_asyncio source parses raw JSON, splits the stream and maps 410 to Gone."""

import json

import pytest

from astrolabio_api.kube.informer import Gone
from astrolabio_api.kube.source import WATCH_TIMEOUT_SECONDS, ApiError, ApiSource

pytestmark = pytest.mark.anyio


class FakeContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    async def iter_any(self):
        for chunk in self.chunks:
            yield chunk


class FakeResponse:
    """The part of aiohttp's ClientResponse the source uses."""

    def __init__(self, status: int = 200, body: bytes = b"", chunks: list[bytes] = ()) -> None:
        self.status = status
        self.reason = "Forbidden" if status == 403 else "OK"
        self.body = body
        self.content = FakeContent(list(chunks))
        self.released = False

    async def read(self) -> bytes:
        return self.body

    def release(self) -> None:
        self.released = True


class FakeListFunction:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.kwargs: dict = {}

    async def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _obj(name: str, rv: str) -> dict:
    return {
        "metadata": {
            "name": name,
            "resourceVersion": rv,
            "managedFields": [{"manager": "kubectl"}],
            "annotations": {
                "kubectl.kubernetes.io/last-applied-configuration": "{}",
                "fabiancienfuegos.com/rol": "frontend",
            },
        }
    }


def _line(type_: str, obj: dict) -> bytes:
    return json.dumps({"type": type_, "object": obj}).encode() + b"\n"


async def _events(source: ApiSource, rv: str = "10") -> list:
    return [event async for event in source.watch(rv)]


async def test_list_returns_trimmed_items_and_version():
    body = json.dumps({"metadata": {"resourceVersion": "10"}, "items": [_obj("a", "1")]})
    response = FakeResponse(body=body.encode())
    items, rv = await ApiSource(FakeListFunction(response)).list()

    assert rv == "10"
    assert items == [
        {
            "metadata": {
                "name": "a",
                "resourceVersion": "1",
                "annotations": {"fabiancienfuegos.com/rol": "frontend"},
            }
        }
    ]
    assert response.released


async def test_watch_asks_for_bookmarks_from_the_version():
    list_function = FakeListFunction(FakeResponse())
    await _events(ApiSource(list_function), "42")

    assert list_function.kwargs == {
        "watch": True,
        "resource_version": "42",
        "allow_watch_bookmarks": True,
        "timeout_seconds": WATCH_TIMEOUT_SECONDS,
        "_request_timeout": WATCH_TIMEOUT_SECONDS + 30,
        "_preload_content": False,
    }


async def test_watch_rebuilds_lines_split_across_chunks():
    stream = _line("ADDED", _obj("a", "11")) + b"\n" + _line("BOOKMARK", _obj("", "12"))
    chunks = [stream[:7], stream[7:30], stream[30:]]
    response = FakeResponse(chunks=chunks)
    events = await _events(ApiSource(FakeListFunction(response)))

    assert [(e.type, e.object["metadata"]["resourceVersion"]) for e in events] == [
        ("ADDED", "11"),
        ("BOOKMARK", "12"),
    ]
    assert "managedFields" not in events[0].object["metadata"]
    assert response.released


async def test_expired_version_is_gone_either_way():
    # As an HTTP status...
    with pytest.raises(Gone):
        await ApiSource(FakeListFunction(FakeResponse(status=410))).list()
    # ...or as an ERROR event inside a 200 watch.
    error = _line("ERROR", {"code": 410, "reason": "Expired"})
    response = FakeResponse(chunks=[error])
    with pytest.raises(Gone):
        await _events(ApiSource(FakeListFunction(response)))
    assert response.released


async def test_other_errors_raise_api_error():
    with pytest.raises(ApiError, match="403"):
        await _events(ApiSource(FakeListFunction(FakeResponse(status=403))))
    error = _line("ERROR", {"code": 500, "reason": "InternalError"})
    with pytest.raises(ApiError, match="500"):
        await _events(ApiSource(FakeListFunction(FakeResponse(chunks=[error]))))
