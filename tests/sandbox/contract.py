"""Checks every response the API really sends against the API document
(openapi/openapi.json), with a strict validator: the schema a generated client trusts must
accept what the API returns, or that client breaks on a real response. Used by the sandbox
tests.

A failure names the operation, the status and the JSON path that failed, never the value:
these are real (sandbox) records, and AGENTS.md keeps account data out of logs that may be
published.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from jsonschema import Draft7Validator
from referencing import Registry
from referencing.jsonschema import DRAFT7

from fiz_sdk import OPERATIONS

SPEC: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parents[2] / "openapi" / "openapi.json").read_text(encoding="utf-8")
)


@dataclass(frozen=True)
class ContractFailure:
    operation: str
    status: int
    problem: str


def to_json_schema(node: Any) -> Any:
    """OpenAPI 3.0 → JSON Schema draft 7: `nullable: true` admits null, and boolean
    exclusiveMinimum/Maximum become numbers. Formats are not checked."""
    if isinstance(node, list):
        return [to_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {key: to_json_schema(value) for key, value in node.items() if key != "nullable"}
    for bound, limit in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
        if isinstance(out.get(bound), bool):
            if out[bound]:
                out[bound] = out.get(limit)
            else:
                del out[bound]
            out.pop(limit, None)
    if node.get("nullable") is True:
        return {"anyOf": [out, {"type": "null"}]}
    return out


_REGISTRY: Registry[Any] = Registry().with_resource(
    "spec", DRAFT7.create_resource(to_json_schema(SPEC))
)


def _pointer(*parts: str) -> str:
    return "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


@dataclass(frozen=True)
class _Template:
    operation_id: str
    method: str
    path: str
    pattern: re.Pattern[str]


_TEMPLATES = [
    _Template(
        operation_id,
        op.method,
        op.path,
        re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", op.path) + "$"),
    )
    for operation_id, op in OPERATIONS.items()
]


def _operation_of(method: str, path: str) -> _Template | None:
    """The operation an API request belongs to; literal routes win over `{id}`."""
    candidates = [t for t in _TEMPLATES if t.method == method and t.pattern.match(path)]
    return min(candidates, key=lambda t: t.path.count("{"), default=None)


def _problem(error: Any) -> str:
    where = "/" + "/".join(str(part) for part in error.absolute_path) if error.absolute_path else ""
    rule = error.validator
    if rule == "required":
        # Property names come from the schema, not from the record.
        instance = error.instance if isinstance(error.instance, dict) else {}
        missing = [name for name in error.validator_value if name not in instance]
        return f"{where or '(body)'} must have required properties {missing}"
    detail = json.dumps(error.validator_value, ensure_ascii=False)
    if len(detail) > 200:
        detail = detail[:200] + "…"
    return f"{where or '(body)'} fails {rule}: {detail}"


def check(method: str, path: str, status: int, content: bytes) -> list[ContractFailure]:
    operation = _operation_of(method, path)
    if operation is None:
        return [ContractFailure(f"{method} {path}", status, "no operation in the API document")]
    name = f"{operation.method} {operation.path}"
    responses = SPEC["paths"][operation.path][operation.method.lower()]["responses"]
    if str(status) not in responses:
        return [ContractFailure(name, status, "status not documented")]
    if "application/json" not in responses[str(status)].get("content", {}):
        return []
    try:
        body = json.loads(content)
    except ValueError:
        return [ContractFailure(name, status, "body is not JSON")]
    ref = "spec#/" + _pointer(
        "paths",
        operation.path,
        operation.method.lower(),
        "responses",
        str(status),
        "content",
        "application/json",
        "schema",
    )
    validator = Draft7Validator({"$ref": ref}, registry=_REGISTRY)
    return [ContractFailure(name, status, _problem(e)) for e in validator.iter_errors(body)]


class ContractTransport(httpx.BaseTransport):
    """A transport that validates every response from `api_origin` and records what does not
    match. Other hosts (a PDF on storage) pass through unchecked."""

    def __init__(self, api_origin: httpx.URL, failures: list[ContractFailure]) -> None:
        self._inner = httpx.HTTPTransport()
        self._origin = (api_origin.scheme, api_origin.host, api_origin.port)
        self._failures = failures

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self._inner.handle_request(request)
        url = request.url
        # Redirects (3xx) carry no documented body; everything else is checked.
        if (url.scheme, url.host, url.port) == self._origin and not (
            300 <= response.status_code < 400
        ):
            content = response.read()
            self._failures.extend(check(request.method, url.path, response.status_code, content))
        return response

    def close(self) -> None:
        self._inner.close()
