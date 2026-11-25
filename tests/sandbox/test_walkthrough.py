"""End to end against the FIZ API sandbox, and a contract test: every response the API sends
is validated against the API document (tests/sandbox/contract.py), so a schema that rejects
what the API really returns fails here instead of in a client's code.

Runs only with a sandbox key (FIZ_TEST_API_KEY=fiz_test_…): `uv run pytest -m sandbox`.
Sandbox documents go to the AT test services and have no fiscal effect; a production key is
refused before any request. The tests run in order and share the records they create.
"""

from __future__ import annotations

import os
import time
import warnings
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from contract import ContractFailure, ContractTransport

from fiz_sdk import DEFAULT_BASE_URL, Fiz, FizNotFoundError

pytestmark = pytest.mark.sandbox

API_KEY = os.environ.get("FIZ_TEST_API_KEY")
TAG = str(int(time.time() * 1000))
FAILURES: list[ContractFailure] = []
STATE: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def sleeps() -> None:
    """Against the real API the client really waits (Retry-After, backoff)."""
    return None


def key(step: str) -> str:
    return f"sdk-ci-{TAG}-{step}"


@pytest.fixture(scope="module")
def fiz() -> Iterator[Fiz]:
    if not API_KEY:
        pytest.skip("FIZ_TEST_API_KEY is not set")
    if not API_KEY.startswith("fiz_test_"):
        pytest.fail("FIZ_TEST_API_KEY must be a sandbox key (fiz_test_…)", pytrace=False)
    base_url = os.environ.get("FIZ_BASE_URL", DEFAULT_BASE_URL)
    http_client = httpx.Client(transport=ContractTransport(httpx.URL(base_url), FAILURES))
    with http_client:
        yield Fiz(
            api_key=API_KEY,
            base_url=base_url,
            http_client=http_client,
            app_info={"name": "fiz-sdk-python-ci"},
        )


def test_reaches_the_sandbox(fiz: Fiz) -> None:
    company = fiz.company.retrieve()
    assert fiz.environment == "sandbox"
    assert company["environment"] == "sandbox"


def test_reads_the_lists(fiz: Fiz) -> None:
    fiz.invoices.list({"limit": 5})
    fiz.customers.list({"limit": 5})
    fiz.items.list({"limit": 5})
    fiz.proposals.list({"limit": 5})
    fiz.recurring_invoices.list({"limit": 5})
    fiz.transport_documents.list({"limit": 5})
    fiz.series.list()
    fiz.templates.list()


def test_creates_updates_prints_and_issues_an_invoice(fiz: Fiz) -> None:
    company = fiz.company.retrieve()
    if not company["cae"]:
        pytest.fail("The sandbox company has no CAE")
    cae = company["cae"][0]
    customer = fiz.customers.create(
        {"name": f"SDK sandbox customer {TAG}", "country": "PT"}, idempotency_key=key("customer")
    )
    item = fiz.items.create(
        {
            "name": f"SDK sandbox service {TAG}",
            "type": "SERVICE",
            "unitPrice": 10,
            "vatRate": "NORMAL",
        },
        idempotency_key=key("item"),
    )
    STATE["customer_id"] = customer["id"]
    STATE["item_id"] = item["id"]
    fiz.customers.retrieve(customer["id"])
    fiz.items.retrieve(item["id"])

    created = fiz.invoices.create(
        {
            "type": "INVOICE",
            "cae": cae,
            "customerId": customer["id"],
            "items": [{"id": item["id"], "quantity": 2}],
        },
        idempotency_key=key("draft"),
    )
    assert created["number"] is None
    updated = fiz.invoices.update(created["id"], {"notes": "Updated by the SDK sandbox test"})
    fiz.invoices.retrieve(created["id"])
    pdf = fiz.invoices.download_pdf(created["id"])
    assert pdf[:5] == b"%PDF-"

    if not company["readiness"]["ready"]:
        warnings.warn("The sandbox company is not ready to issue; issuing skipped.", stacklevel=1)
        return
    # A revision is required: issuing without one would skip the check that the draft is the
    # one just updated.
    revision = updated.get("updatedAt")
    assert revision
    issued = fiz.invoices.issue(created["id"], {"expectedUpdatedAt": revision})
    assert issued["number"]
    assert issued["atcud"]
    STATE["invoice_id"] = created["id"]
    fiz.invoices.retrieve(created["id"])


def test_raises_and_issues_a_partial_credit_note(fiz: Fiz) -> None:
    if "invoice_id" not in STATE:
        pytest.skip("no issued invoice")
    note = fiz.credit_notes.create(
        {
            "parentInvoiceId": STATE["invoice_id"],
            "reasonCode": "RETURN_GOODS_SERVICES",
            "items": [{"itemId": STATE["item_id"], "quantity": 1}],
            "issue": False,
        },
        idempotency_key=key("credit-note"),
    )
    assert note["number"] is None
    draft = fiz.invoices.retrieve(note["id"])
    revision = draft["updatedAt"]
    assert revision
    issued = fiz.invoices.issue(note["id"], {"expectedUpdatedAt": revision})
    assert issued["number"]
    fiz.invoices.retrieve(note["id"])


def test_answers_a_missing_record_with_the_documented_404(fiz: Fiz) -> None:
    with pytest.raises(FizNotFoundError) as caught:
        fiz.invoices.retrieve("000000000000000000000000")
    assert caught.value.request_id


def test_archives_the_customer_and_the_item_it_created(fiz: Fiz) -> None:
    if "customer_id" in STATE:
        fiz.customers.delete(STATE["customer_id"])
    if "item_id" in STATE:
        fiz.items.delete(STATE["item_id"])


def test_every_response_matched_the_api_document(fiz: Fiz) -> None:
    # Every response of every test above, against the API document.
    assert FAILURES == []
