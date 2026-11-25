from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fiz_sdk import OPERATIONS

ROOT = Path(__file__).resolve().parent.parent
SPEC: dict[str, Any] = json.loads((ROOT / "openapi" / "openapi.json").read_text(encoding="utf-8"))
RESOURCE_SOURCE = "\n".join(
    path.read_text(encoding="utf-8")
    for path in (ROOT / "src" / "fiz_sdk" / "resources").glob("*.py")
)


@pytest.mark.parametrize("operation_id", sorted(OPERATIONS))
def test_every_api_operation_has_a_resource_method(operation_id: str) -> None:
    """When `scripts/update_spec.py` brings a new operation, this fails until a resource
    method wraps it (it is already callable through `fiz.call`)."""
    assert f'"{operation_id}"' in RESOURCE_SOURCE


def test_the_generated_operation_table_matches_the_spec() -> None:
    from_spec = [
        op["operationId"]
        for item in SPEC["paths"].values()
        for method, op in item.items()
        if method in ("get", "post", "put", "patch", "delete")
    ]
    assert sorted(OPERATIONS) == sorted(from_spec)


def test_marks_the_writes_that_take_an_idempotency_key() -> None:
    assert OPERATIONS["InvoicesController_issue"].idempotent is True
    assert OPERATIONS["InvoicesController_findAll"].idempotent is False
    assert OPERATIONS["VatController_calculate"].idempotent is False


def test_every_success_of_every_operation_is_json_as_the_client_assumes() -> None:
    # The client parses a success as JSON and treats anything else as a lost response.
    # An operation answering something else (a file, CSV) needs the client taught first.
    not_json = []
    for path, item in SPEC["paths"].items():
        for method, op in item.items():
            for status, response in op.get("responses", {}).items():
                if not status.startswith("2"):
                    continue
                types = list(response.get("content", {}))
                if not types or any(t != "application/json" for t in types):
                    not_json.append(
                        f"{method.upper()} {path} {status}: {', '.join(types) or 'no body'}"
                    )
    assert not_json == []
