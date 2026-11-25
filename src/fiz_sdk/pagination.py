from collections.abc import Callable, Iterator, Mapping
from typing import Any, TypeVar, cast

DEFAULT_PAGE_SIZE = 100
"""Records per request while `list_all` walks the pages."""

Q = TypeVar("Q", bound=Mapping[str, Any])
T = TypeVar("T")


def paginate_by_offset(
    list_page: Callable[[Q], list[T]], query: Q | None, page_size: int
) -> Iterator[T]:
    """List endpoints answer one page as a plain list. This walks the pages until an empty
    one: stopping at a short page would be one request cheaper, but a server-side cap below
    the requested size would then end the walk early and silently drop records. Paging
    parameters in `query` are replaced."""
    filters = dict(query or {})
    offset = 0
    while True:
        page = list_page(cast(Q, {**filters, "offset": offset, "limit": page_size}))
        if not page:
            return
        yield from page
        offset += len(page)


def paginate_by_page(
    list_page: Callable[[Q], list[T]], query: Q | None, page_size: int
) -> Iterator[T]:
    """Same as `paginate_by_offset`, for endpoints that number pages from 1."""
    filters = dict(query or {})
    page = 1
    while True:
        items = list_page(cast(Q, {**filters, "page": page, "pageSize": page_size}))
        if not items:
            return
        yield from items
        page += 1
