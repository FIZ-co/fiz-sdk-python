import builtins
from collections.abc import Iterator

from .._compat import Unpack
from ..generated.schemas import (
    CreateProposalDto,
    CreateTransportDocumentDto,
    DeleteProposalResponseDto,
    DownloadProposalPdfResponseDto,
    DownloadTransportDocumentPdfResponseDto,
    IssueTransportDocumentDto,
    ProposalResponseDto,
    ProposalsControllerFindAllQuery,
    ProposalsControllerGetPdfQuery,
    TransportDocumentResponseDto,
    TransportDocumentsControllerFindAllQuery,
    TransportDocumentsControllerGetPdfQuery,
    UpdateTransportDocumentDto,
)
from ..options import RequestOptions
from ..pagination import DEFAULT_PAGE_SIZE, paginate_by_offset
from ._base import Resource, require_url


class Proposals(Resource):
    """Pro formas: numbered at creation, never reported to the AT, no fiscal effect."""

    def create(
        self, body: CreateProposalDto, **options: Unpack[RequestOptions]
    ) -> ProposalResponseDto:
        return self._client.call("ProposalsController_create", body=body, **options)

    def list(
        self,
        query: ProposalsControllerFindAllQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> builtins.list[ProposalResponseDto]:
        return self._client.call("ProposalsController_findAll", query=query, **options)

    def list_all(
        self,
        query: ProposalsControllerFindAllQuery | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        **options: Unpack[RequestOptions],
    ) -> Iterator[ProposalResponseDto]:
        return paginate_by_offset(lambda page: self.list(page, **options), query, page_size)

    def retrieve(self, id: str, **options: Unpack[RequestOptions]) -> ProposalResponseDto:
        return self._client.call("ProposalsController_findOne", path={"id": id}, **options)

    def delete(self, id: str, **options: Unpack[RequestOptions]) -> DeleteProposalResponseDto:
        return self._client.call("ProposalsController_delete", path={"id": id}, **options)

    def cancel(self, id: str, **options: Unpack[RequestOptions]) -> ProposalResponseDto:
        return self._client.call("ProposalsController_cancel", path={"id": id}, **options)

    def pdf(
        self,
        id: str,
        query: ProposalsControllerGetPdfQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> DownloadProposalPdfResponseDto:
        return self._client.call(
            "ProposalsController_getPdf", path={"id": id}, query=query, **options
        )

    def download_pdf(
        self,
        id: str,
        query: ProposalsControllerGetPdfQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> bytes:
        file = self.pdf(id, query, **options)
        return self._client.download(
            require_url(file.get("url"), id), timeout=options.get("timeout")
        )


class TransportDocuments(Resource):
    """Transport documents (guias de transporte: GR, GT, GA, GC, GD)."""

    def create(
        self, body: CreateTransportDocumentDto, **options: Unpack[RequestOptions]
    ) -> TransportDocumentResponseDto:
        """Creates a draft. `movementStartTime` must be in the future."""
        return self._client.call("TransportDocumentsController_create", body=body, **options)

    def list(
        self,
        query: TransportDocumentsControllerFindAllQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> builtins.list[TransportDocumentResponseDto]:
        return self._client.call("TransportDocumentsController_findAll", query=query, **options)

    def list_all(
        self,
        query: TransportDocumentsControllerFindAllQuery | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        **options: Unpack[RequestOptions],
    ) -> Iterator[TransportDocumentResponseDto]:
        return paginate_by_offset(lambda page: self.list(page, **options), query, page_size)

    def retrieve(self, id: str, **options: Unpack[RequestOptions]) -> TransportDocumentResponseDto:
        return self._client.call("TransportDocumentsController_findOne", path={"id": id}, **options)

    def update(
        self, id: str, body: UpdateTransportDocumentDto, **options: Unpack[RequestOptions]
    ) -> TransportDocumentResponseDto:
        return self._client.call(
            "TransportDocumentsController_update", path={"id": id}, body=body, **options
        )

    def delete(self, id: str, **options: Unpack[RequestOptions]) -> TransportDocumentResponseDto:
        return self._client.call("TransportDocumentsController_delete", path={"id": id}, **options)

    def issue(
        self,
        id: str,
        body: IssueTransportDocumentDto | None = None,
        **options: Unpack[RequestOptions],
    ) -> TransportDocumentResponseDto:
        """Issues the document and reports it to the AT. **Fiscal and irreversible.**"""
        return self._client.call(
            "TransportDocumentsController_issue",
            path={"id": id},
            body=body if body is not None else {},
            **options,
        )

    def cancel(self, id: str, **options: Unpack[RequestOptions]) -> TransportDocumentResponseDto:
        """Cancels an issued document at the AT. **Fiscal and irreversible.**"""
        return self._client.call("TransportDocumentsController_cancel", path={"id": id}, **options)

    def pdf(
        self,
        id: str,
        query: TransportDocumentsControllerGetPdfQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> DownloadTransportDocumentPdfResponseDto:
        return self._client.call(
            "TransportDocumentsController_getPdf", path={"id": id}, query=query, **options
        )

    def download_pdf(
        self,
        id: str,
        query: TransportDocumentsControllerGetPdfQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> bytes:
        file = self.pdf(id, query, **options)
        return self._client.download(
            require_url(file.get("url"), id), timeout=options.get("timeout")
        )
