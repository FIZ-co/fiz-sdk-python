from collections.abc import Mapping

from ._compat import NotRequired, TypedDict


class RequestOptions(TypedDict, total=False):
    """Options of a single call, as keyword arguments; each overrides the client's default."""

    idempotency_key: str
    """Idempotency-Key for a write. Generated (a UUID) when omitted, and reused by every
    automatic retry of this call. Pass your own (an order id, say, at most 128 printable
    ASCII characters) to make retries across process restarts safe too."""
    max_retries: int
    """Automatic retries for this call (default: the client's `max_retries`)."""
    timeout: float
    """Timeout of each attempt, in seconds (default: the client's `timeout`)."""
    headers: Mapping[str, str]
    """Extra request headers."""


class AppInfo(TypedDict):
    """Your integration's name and version, added to the User-Agent."""

    name: str
    version: NotRequired[str]
