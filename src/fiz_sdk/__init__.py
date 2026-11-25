"""Official Python client for the FIZ API: certified invoicing in Portugal.

```python
from fiz_sdk import Fiz

fiz = Fiz()  # reads FIZ_API_KEY
draft = fiz.invoices.create({"type": "INVOICE", "customerId": customer_id, "items": items})
```
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Any

import httpx

from ._compat import Self
from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    Environment,
    FizClient,
    FizResponseInfo,
)
from .errors import (
    FizApiError,
    FizAuthenticationError,
    FizBadRequestError,
    FizConflictError,
    FizConnectionError,
    FizError,
    FizNotFoundError,
    FizPermissionError,
    FizRateLimitError,
    FizServerError,
    FizTimeoutError,
    FizUnprocessableEntityError,
)
from .generated.calls import TypedCalls
from .generated.operations import API_VERSION, OPERATIONS, Operation, OperationId
from .generated.schemas import (
    CompanyResponseDto,
    CreateCustomerDto,
    CreateCustomerResponseDto,
    CreateInvoiceDto,
    CreateItemDto,
    CreateItemResponseDto,
    ErrorResponseDto,
    InvoiceListItemResponseDto,
    InvoiceResponseDto,
)
from .options import AppInfo, RequestOptions
from .resources import (
    Bank,
    CreditNotes,
    Customers,
    Expenses,
    Exports,
    Invoices,
    Items,
    Proposals,
    RecurringInvoices,
    Series,
    Templates,
    TransportDocuments,
    Vat,
)
from .resources import (
    Company as CompanyResource,
)
from .version import VERSION

__version__ = VERSION


class Fiz(TypedCalls):
    """Client for the FIZ API: certified invoicing in Portugal.

    Takes the options of `FizClient`: `api_key` (default: the `FIZ_API_KEY` environment
    variable) or `access_token`, `base_url`, `max_retries`, `timeout`, `http_client`,
    `app_info` and `on_response`.
    """

    invoices: Invoices
    credit_notes: CreditNotes
    recurring_invoices: RecurringInvoices
    proposals: Proposals
    transport_documents: TransportDocuments
    customers: Customers
    items: Items
    series: Series
    templates: Templates
    company: CompanyResource
    vat: Vat
    expenses: Expenses
    bank: Bank
    exports: Exports

    def __init__(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        base_url: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
        app_info: AppInfo | None = None,
        on_response: Callable[[FizResponseInfo], object] | None = None,
    ) -> None:
        self._client = FizClient(
            api_key=api_key,
            access_token=access_token,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
            http_client=http_client,
            app_info=app_info,
            on_response=on_response,
        )
        self.invoices = Invoices(self._client)
        self.credit_notes = CreditNotes(self._client)
        self.recurring_invoices = RecurringInvoices(self._client)
        self.proposals = Proposals(self._client)
        self.transport_documents = TransportDocuments(self._client)
        self.customers = Customers(self._client)
        self.items = Items(self._client)
        self.series = Series(self._client)
        self.templates = Templates(self._client)
        self.company = CompanyResource(self._client)
        self.vat = Vat(self._client)
        self.expenses = Expenses(self._client)
        self.bank = Bank(self._client)
        self.exports = Exports(self._client)

    @property
    def environment(self) -> Environment:
        """`sandbox` when the key starts with `fiz_test_` (no fiscal effect)."""
        return self._client.environment

    def close(self) -> None:
        """Closes the connection pool (not an `http_client` you passed in)."""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _call(
        self,
        operation_id: str,
        path: Mapping[str, str] | None,
        query: Mapping[str, Any] | None,
        body: Any,
        options: RequestOptions,
    ) -> Any:
        return self._client._call(operation_id, path, query, body, options)


Invoice = InvoiceResponseDto
"""A document as `invoices.retrieve` returns it."""
InvoiceListItem = InvoiceListItemResponseDto
"""A document as `invoices.list` returns it."""
CreateInvoiceParams = CreateInvoiceDto
Customer = CreateCustomerResponseDto
CreateCustomerParams = CreateCustomerDto
Item = CreateItemResponseDto
CreateItemParams = CreateItemDto
Company = CompanyResponseDto
ApiErrorBody = ErrorResponseDto

__all__ = [
    "API_VERSION",
    "DEFAULT_BASE_URL",
    "OPERATIONS",
    "VERSION",
    "ApiErrorBody",
    "AppInfo",
    "Company",
    "CreateCustomerParams",
    "CreateInvoiceParams",
    "CreateItemParams",
    "Customer",
    "Environment",
    "Fiz",
    "FizApiError",
    "FizAuthenticationError",
    "FizBadRequestError",
    "FizClient",
    "FizConflictError",
    "FizConnectionError",
    "FizError",
    "FizNotFoundError",
    "FizPermissionError",
    "FizRateLimitError",
    "FizResponseInfo",
    "FizServerError",
    "FizTimeoutError",
    "FizUnprocessableEntityError",
    "Invoice",
    "InvoiceListItem",
    "Item",
    "Operation",
    "OperationId",
    "RequestOptions",
    "__version__",
]
