import builtins
from collections.abc import Iterator

from .._compat import Unpack
from ..generated.schemas import (
    CheckTemplateDto,
    CreateCustomerDto,
    CreateCustomerResponseDto,
    CreateItemDto,
    CreateItemResponseDto,
    CreateTemplateDto,
    CustomersControllerFindAllQuery,
    DeleteTemplateResponseDto,
    GetSeriesResponseDto,
    ItemsControllerFindAllQuery,
    PreviewTemplateDto,
    TemplateDto,
    TemplateFieldReferenceDto,
    TemplatePreviewResponseDto,
    TemplatesControllerGetAllQuery,
    TemplateStarterDataDto,
    TemplateStarterDto,
    TemplateSummaryDto,
    TemplateValidationDto,
    UpdateCustomerDto,
    UpdateItemDto,
    UpdateTemplateDto,
)
from ..options import RequestOptions
from ..pagination import DEFAULT_PAGE_SIZE, paginate_by_offset
from ._base import Resource


class Customers(Resource):
    def create(
        self, body: CreateCustomerDto, **options: Unpack[RequestOptions]
    ) -> CreateCustomerResponseDto:
        return self._client.call("CustomersController_create", body=body, **options)

    def list(
        self,
        query: CustomersControllerFindAllQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> builtins.list[CreateCustomerResponseDto]:
        return self._client.call("CustomersController_findAll", query=query, **options)

    def list_all(
        self,
        query: CustomersControllerFindAllQuery | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        **options: Unpack[RequestOptions],
    ) -> Iterator[CreateCustomerResponseDto]:
        return paginate_by_offset(lambda page: self.list(page, **options), query, page_size)

    def retrieve(self, id: str, **options: Unpack[RequestOptions]) -> CreateCustomerResponseDto:
        return self._client.call("CustomersController_findOne", path={"id": id}, **options)

    def update(
        self, id: str, body: UpdateCustomerDto, **options: Unpack[RequestOptions]
    ) -> CreateCustomerResponseDto:
        return self._client.call(
            "CustomersController_update", path={"id": id}, body=body, **options
        )

    def delete(self, id: str, **options: Unpack[RequestOptions]) -> CreateCustomerResponseDto:
        """Archives the customer; `restore` brings it back."""
        return self._client.call("CustomersController_delete", path={"id": id}, **options)

    def restore(self, id: str, **options: Unpack[RequestOptions]) -> CreateCustomerResponseDto:
        return self._client.call("CustomersController_restore", path={"id": id}, **options)


class Items(Resource):
    """Catalogue items (products and services) with their VAT."""

    def create(
        self, body: CreateItemDto, **options: Unpack[RequestOptions]
    ) -> CreateItemResponseDto:
        return self._client.call("ItemsController_create", body=body, **options)

    def list(
        self,
        query: ItemsControllerFindAllQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> builtins.list[CreateItemResponseDto]:
        return self._client.call("ItemsController_findAll", query=query, **options)

    def list_all(
        self,
        query: ItemsControllerFindAllQuery | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        **options: Unpack[RequestOptions],
    ) -> Iterator[CreateItemResponseDto]:
        return paginate_by_offset(lambda page: self.list(page, **options), query, page_size)

    def retrieve(self, id: str, **options: Unpack[RequestOptions]) -> CreateItemResponseDto:
        return self._client.call("ItemsController_findOne", path={"id": id}, **options)

    def update(
        self, id: str, body: UpdateItemDto, **options: Unpack[RequestOptions]
    ) -> CreateItemResponseDto:
        return self._client.call("ItemsController_update", path={"id": id}, body=body, **options)

    def delete(self, id: str, **options: Unpack[RequestOptions]) -> CreateItemResponseDto:
        return self._client.call("ItemsController_delete", path={"id": id}, **options)


class Series(Resource):
    """Invoice series and their AT registration."""

    def list(self, **options: Unpack[RequestOptions]) -> builtins.list[GetSeriesResponseDto]:
        return self._client.call("SeriesController_getAll", **options)


class Templates(Resource):
    """PDF templates: build, validate, preview and install."""

    def list(
        self,
        query: TemplatesControllerGetAllQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> builtins.list[TemplateSummaryDto]:
        return self._client.call("TemplatesController_getAll", query=query, **options)

    def create(self, body: CreateTemplateDto, **options: Unpack[RequestOptions]) -> TemplateDto:
        return self._client.call("TemplatesController_create", body=body, **options)

    def retrieve(self, id: str, **options: Unpack[RequestOptions]) -> TemplateDto:
        return self._client.call("TemplatesController_findOne", path={"id": id}, **options)

    def update(
        self, id: str, body: UpdateTemplateDto, **options: Unpack[RequestOptions]
    ) -> TemplateDto:
        """Replaces the template."""
        return self._client.call(
            "TemplatesController_update", path={"id": id}, body=body, **options
        )

    def delete(self, id: str, **options: Unpack[RequestOptions]) -> DeleteTemplateResponseDto:
        return self._client.call("TemplatesController_delete", path={"id": id}, **options)

    def fields(self, **options: Unpack[RequestOptions]) -> builtins.list[TemplateFieldReferenceDto]:
        """The fields a template can print."""
        return self._client.call("TemplatesController_fields", **options)

    def starters(self, **options: Unpack[RequestOptions]) -> builtins.list[TemplateStarterDto]:
        return self._client.call("TemplatesController_starters", **options)

    def starter(self, starter_id: str, **options: Unpack[RequestOptions]) -> TemplateStarterDataDto:
        return self._client.call(
            "TemplatesController_starter", path={"starterId": starter_id}, **options
        )

    def validate(
        self, body: CheckTemplateDto, **options: Unpack[RequestOptions]
    ) -> TemplateValidationDto:
        """Answers as `create` would, without storing anything."""
        return self._client.call("TemplatesController_validate", body=body, **options)

    def preview(
        self, body: PreviewTemplateDto, **options: Unpack[RequestOptions]
    ) -> TemplatePreviewResponseDto:
        """Renders the template on a sample document."""
        return self._client.call("TemplatesController_preview", body=body, **options)
