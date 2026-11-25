from __future__ import annotations

from typing import TYPE_CHECKING

from ..errors import FizError

if TYPE_CHECKING:
    from ..client import FizClient


class Resource:
    def __init__(self, client: FizClient) -> None:
        self._client = client


def require_url(url: str | None, id: str) -> str:
    """The link a `pdf` call returned, or an error when the API sent none."""
    if not url:
        raise FizError(f"The API returned no PDF link for {id}")
    return url
