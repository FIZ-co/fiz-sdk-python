import builtins
from collections.abc import Iterator

from .._compat import Unpack
from ..generated.schemas import (
    BankConnectionResponseDto,
    BankControllerGetTransactionsQuery,
    BankTransactionResponseDto,
    CalculateVatDto,
    CalculateVatResponseDto,
    CompanyResponseDto,
    ExpenseResponseDto,
    ExpensesControllerFindAllQuery,
    ExpensesControllerStatsQuery,
    ExpenseStatsResponseDto,
    ExportSaftPtResponseDto,
    ExportsControllerExportSaftPtQuery,
    ValidateClientVatDto,
    ValidateClientVatResponseDto,
)
from ..options import RequestOptions
from ..pagination import DEFAULT_PAGE_SIZE, paginate_by_offset, paginate_by_page
from ._base import Resource


class Company(Resource):
    """The connected company."""

    def retrieve(self, **options: Unpack[RequestOptions]) -> CompanyResponseDto:
        """The company and its issuance readiness (`readiness`): check it before issuing.
        `environment` says whether the key reaches production or the sandbox."""
        return self._client.call("CompanyController_getCompany", **options)


class Vat(Resource):
    def calculate(
        self, body: CalculateVatDto, **options: Unpack[RequestOptions]
    ) -> CalculateVatResponseDto:
        """The VAT rate and exemption that apply to an item for a customer."""
        return self._client.call("VatController_calculate", body=body, **options)

    def validate_client(
        self, body: ValidateClientVatDto, **options: Unpack[RequestOptions]
    ) -> ValidateClientVatResponseDto:
        return self._client.call("VatController_validateClient", body=body, **options)


class Expenses(Resource):
    """Purchase documents imported from e-Fatura. Read-only."""

    def list(
        self,
        query: ExpensesControllerFindAllQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> builtins.list[ExpenseResponseDto]:
        return self._client.call("ExpensesController_findAll", query=query, **options)

    def list_all(
        self,
        query: ExpensesControllerFindAllQuery | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        **options: Unpack[RequestOptions],
    ) -> Iterator[ExpenseResponseDto]:
        return paginate_by_offset(lambda page: self.list(page, **options), query, page_size)

    def stats(
        self,
        query: ExpensesControllerStatsQuery | None = None,
        **options: Unpack[RequestOptions],
    ) -> ExpenseStatsResponseDto:
        return self._client.call("ExpensesController_stats", query=query, **options)


class Bank(Resource):
    """Bank connections and transactions (open banking). Production only."""

    def connections(
        self, **options: Unpack[RequestOptions]
    ) -> builtins.list[BankConnectionResponseDto]:
        return self._client.call("BankController_getConnections", **options)

    def transactions(
        self, query: BankControllerGetTransactionsQuery, **options: Unpack[RequestOptions]
    ) -> builtins.list[BankTransactionResponseDto]:
        return self._client.call("BankController_getTransactions", query=query, **options)

    def transactions_all(
        self,
        query: BankControllerGetTransactionsQuery,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        **options: Unpack[RequestOptions],
    ) -> Iterator[BankTransactionResponseDto]:
        return paginate_by_page(lambda page: self.transactions(page, **options), query, page_size)


class Exports(Resource):
    def saft_pt(
        self, query: ExportsControllerExportSaftPtQuery, **options: Unpack[RequestOptions]
    ) -> ExportSaftPtResponseDto:
        """Generates the company's SAF-T PT for a month or a period and returns a temporary
        download link."""
        return self._client.call("ExportsController_exportSaftPt", query=query, **options)
