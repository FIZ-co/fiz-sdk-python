"""Compile-time checks: `mypy` fails on these, nothing runs them. A `type: ignore[...]` here
expects that error; mypy's strict mode reports it as unused once the error goes away."""

from __future__ import annotations

from collections.abc import Iterator

from typing_extensions import assert_type

from fiz_sdk import ApiErrorBody, Fiz, Invoice, InvoiceListItem
from fiz_sdk.types import CreateCustomerDto, TemplateDto


def responses_follow_the_api_document(fiz: Fiz, invoice_id: str) -> None:
    assert_type(fiz.invoices.retrieve(invoice_id), Invoice)
    assert_type(fiz.invoices.list(), list[InvoiceListItem])
    assert_type(fiz.invoices.list_all(), Iterator[InvoiceListItem])
    assert_type(fiz.call("InvoicesController_findOne", path={"id": invoice_id}), Invoice)
    body: ApiErrorBody = {"statusCode": 404, "message": "Invoice not found"}
    assert_type(body["statusCode"], int)


def a_credit_note_draft(fiz: Fiz, parent_invoice_id: str) -> None:
    # The API documents it: a credit note is issued at once unless issue is False.
    fiz.credit_notes.create(
        {
            "parentInvoiceId": parent_invoice_id,
            "reasonCode": "RETURN_GOODS_SERVICES",
            "issue": False,
        }
    )


def a_template_read_back_as_an_import(fiz: Fiz, template: TemplateDto) -> None:
    # The API documents it: GET /templates/{id} can be sent to POST /templates as is.
    fiz.templates.create(template)


def request_bodies_follow_the_api_document(fiz: Fiz, invoice_id: str) -> None:
    customer: CreateCustomerDto = {"name": "Example customer", "country": "PT"}
    fiz.customers.create(customer)
    # `issue` takes expectedUpdatedAt, not arbitrary fields.
    fiz.invoices.issue(invoice_id, {"notAField": True})  # type: ignore[arg-type]
    # Per-call options are checked too.
    fiz.customers.create(customer, idempotency_key=42)  # type: ignore[arg-type]
