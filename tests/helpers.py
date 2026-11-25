from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from fiz_sdk import Fiz


@dataclass
class Recorded:
    method: str
    url: httpx.URL
    headers: dict[str, str]
    body: Any


@dataclass
class Reply:
    status: int
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)


Answer = Reply | Exception | Callable[[httpx.Request], httpx.Response]


class CutOff(httpx.SyncByteStream):
    """A response body the connection drops before it ends."""

    def __iter__(self) -> Iterator[bytes]:
        raise httpx.ReadError("terminated")


def cut_off(status: int, headers: dict[str, str] | None = None) -> Answer:
    return lambda request: httpx.Response(
        status, headers={"content-type": "application/json", **(headers or {})}, stream=CutOff()
    )


def raw(status: int, text: str, content_type: str = "application/json") -> Answer:
    return lambda request: httpx.Response(
        status, headers={"content-type": content_type}, content=text.encode()
    )


@dataclass
class Mock:
    fiz: Fiz
    requests: list[Recorded]


def mock_fiz(replies: list[Answer], **options: Any) -> Mock:
    """A Fiz client whose transport answers from `replies` in order and records every
    request. The httpx client follows redirects on its own, to prove the SDK stops it."""
    requests: list[Recorded] = []
    queue = list(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        content = request.read()
        requests.append(
            Recorded(
                method=request.method,
                url=request.url,
                headers=dict(request.headers),
                body=json.loads(content) if content else None,
            )
        )
        if not queue:
            raise AssertionError("No reply queued for this request")
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            return reply(request)
        content = b"" if reply.body is None else json.dumps(reply.body).encode()
        return httpx.Response(
            reply.status,
            headers={"content-type": "application/json", **reply.headers},
            content=content,
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    options.setdefault("api_key", "fiz_live_key")
    fiz = Fiz(http_client=http_client, **options)
    return Mock(fiz, requests)
