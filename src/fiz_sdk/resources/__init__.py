"""One typed method per API operation, grouped as the `Fiz` client exposes them."""

from .account import Bank, Company, Expenses, Exports, Vat
from .catalog import Customers, Items, Series, Templates
from .documents import Proposals, TransportDocuments
from .invoices import CreditNotes, Invoices, RecurringInvoices

__all__ = [
    "Bank",
    "Company",
    "CreditNotes",
    "Customers",
    "Expenses",
    "Exports",
    "Invoices",
    "Items",
    "Proposals",
    "RecurringInvoices",
    "Series",
    "Templates",
    "TransportDocuments",
    "Vat",
]
