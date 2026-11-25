import builtins
from collections.abc import Iterator

from .._compat import Unpack
from ..generated.schemas import (
    CancelInvoiceDto,
    CancelInvoiceResponseDto,
    CreateCreditNoteDto,
    CreateCreditNoteResponseDto,
    CreateInvoiceDto,
    CreateInvoiceResponseDto,
    CreateScheduledInvoiceDto,
    DeleteInvoiceResponseDto,
    DownloadInvoicePdfResponseDto,
    InvoiceListItemResponseDto,
    InvoiceResponseDto,
    InvoicesControllerFindAllQuery,
    InvoicesControllerGetPdfQuery,
    IssueInvoiceDto,
    IssueInvoiceResponseDto,
    PayInvoiceDto,
    PayInvoiceResponseDto,
    ScheduledInvoiceResponseDto,
    ScheduledInvoicesControllerFindAllQuery,
    UpdateInvoiceDto,
    UpdateScheduledInvoiceDto,
)
from ..options import RequestOptions
from ..pagination import DEFAULT_PAGE_SIZE, paginate_by_offset
from ._base import Resource, require_url


class Invoices(Resource):
    """Invoices, simplified invoices, invoice-receipts and the receipts and credit notes raised
    from them. A document is created as a draft (no fiscal effect) and becomes a fiscal
    document only when issued."""

    def create(
        self, body: CreateInvoiceDto, **options: Unpack[RequestOptions]
    ) -> CreateInvoiceResponseDto:
        """Creates a draft. Not reported to the AT until `issue`."""
        return self._client.call("InvoicesController_create", body=body, **options)

    def list(
        self,
        query: InvoicesControllerFindAllQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> builtins.list[InvoiceListItemResponseDto]:
        """One page of documents, newest first by default."""
        return self._client.call("InvoicesController_findAll", query=query, **options)

    def list_all(
        self,
        query: InvoicesControllerFindAllQuery | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        **options: Unpack[RequestOptions],
    ) -> Iterator[InvoiceListItemResponseDto]:
        """Every document matching the filters, fetching pages as you iterate."""
        return paginate_by_offset(lambda page: self.list(page, **options), query, page_size)

    def retrieve(self, id: str, **options: Unpack[RequestOptions]) -> InvoiceResponseDto:
        return self._client.call("InvoicesController_findOne", path={"id": id}, **options)

    def update(
        self, id: str, body: UpdateInvoiceDto, **options: Unpack[RequestOptions]
    ) -> CreateInvoiceResponseDto:
        """Changes a draft. Issued documents cannot be changed."""
        return self._client.call("InvoicesController_update", path={"id": id}, body=body, **options)

    def delete(self, id: str, **options: Unpack[RequestOptions]) -> DeleteInvoiceResponseDto:
        """Deletes a draft."""
        return self._client.call("InvoicesController_delete", path={"id": id}, **options)

    def issue(
        self,
        id: str,
        body: IssueInvoiceDto | None = None,
        **options: Unpack[RequestOptions],
    ) -> IssueInvoiceResponseDto:
        """Issues a draft: numbers it in its series, adds the ATCUD and QR code and reports it
        to the AT. **Fiscal and irreversible** (with a production key). Pass the draft's
        `updatedAt` (from `create`, `update` or `retrieve`) as `expectedUpdatedAt`; if it is
        missing, do not issue. A draft changed since you read it is refused instead of
        issued."""
        return self._client.call(
            "InvoicesController_issue",
            path={"id": id},
            body=body if body is not None else {},
            **options,
        )

    def pay(
        self, id: str, body: PayInvoiceDto, **options: Unpack[RequestOptions]
    ) -> PayInvoiceResponseDto:
        """Records a payment and issues its receipt. **Fiscal and irreversible.**"""
        return self._client.call("InvoicesController_pay", path={"id": id}, body=body, **options)

    def cancel(
        self, id: str, body: CancelInvoiceDto, **options: Unpack[RequestOptions]
    ) -> CancelInvoiceResponseDto:
        """Cancels an issued document and reports it to the AT. **Fiscal and irreversible.**"""
        return self._client.call("InvoicesController_cancel", path={"id": id}, body=body, **options)

    def pdf(
        self,
        id: str,
        query: InvoicesControllerGetPdfQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> DownloadInvoicePdfResponseDto:
        """Link to the document's PDF. Use `download_pdf` for the bytes."""
        return self._client.call(
            "InvoicesController_getPdf", path={"id": id}, query=query, **options
        )

    def download_pdf(
        self,
        id: str,
        query: InvoicesControllerGetPdfQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> bytes:
        """The document's PDF file."""
        file = self.pdf(id, query, **options)
        return self._client.download(
            require_url(file.get("url"), id), timeout=options.get("timeout")
        )


class CreditNotes(Resource):
    """Credit notes on an issued invoice, total or per line."""

    def create(
        self, body: CreateCreditNoteDto, **options: Unpack[RequestOptions]
    ) -> CreateCreditNoteResponseDto:
        """Creates a credit note. Without `items` it reverses the invoice in full; with `items`
        it changes the quantity or price of the given lines.

        **Issued at once by default**: without `"issue": False` the note is numbered and
        reported to the AT in this call, which with a production key is fiscal and
        irreversible. Pass `"issue": False` for a draft, then `invoices.issue(note["id"], ...)`
        once it has been reviewed."""
        return self._client.call("InvoicesController_createCreditNote", body=body, **options)


class RecurringInvoices(Resource):
    """Recurring invoices: a template FIZ issues — and reports to the AT — on its own schedule.
    Every document it issues carries its id as `scheduleTemplateId`
    (`invoices.list({"scheduleTemplateId": ...})`)."""

    def create(
        self, body: CreateScheduledInvoiceDto, **options: Unpack[RequestOptions]
    ) -> ScheduledInvoiceResponseDto:
        return self._client.call("ScheduledInvoicesController_create", body=body, **options)

    def list(
        self,
        query: ScheduledInvoicesControllerFindAllQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> builtins.list[ScheduledInvoiceResponseDto]:
        return self._client.call("ScheduledInvoicesController_findAll", query=query, **options)

    def list_all(
        self,
        query: ScheduledInvoicesControllerFindAllQuery | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        **options: Unpack[RequestOptions],
    ) -> Iterator[ScheduledInvoiceResponseDto]:
        return paginate_by_offset(lambda page: self.list(page, **options), query, page_size)

    def retrieve(self, id: str, **options: Unpack[RequestOptions]) -> ScheduledInvoiceResponseDto:
        return self._client.call("ScheduledInvoicesController_findOne", path={"id": id}, **options)

    def update(
        self, id: str, body: UpdateScheduledInvoiceDto, **options: Unpack[RequestOptions]
    ) -> ScheduledInvoiceResponseDto:
        """Changes the schedule, or pauses and resumes it (`status`)."""
        return self._client.call(
            "ScheduledInvoicesController_update", path={"id": id}, body=body, **options
        )

    def delete(self, id: str, **options: Unpack[RequestOptions]) -> DeleteInvoiceResponseDto:
        """Ends the schedule. Documents already issued are kept."""
        return self._client.call("ScheduledInvoicesController_delete", path={"id": id}, **options)
