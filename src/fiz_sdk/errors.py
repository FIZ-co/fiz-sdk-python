from __future__ import annotations

from typing import Any

import httpx


class FizError(Exception):
    """Base class of every error this SDK raises."""


class FizApiError(FizError):
    """The API answered with a 4xx or 5xx status. Branch on `status` and `code`;
    the message is for people and its wording may change."""

    status: int
    """HTTP status of the response."""
    code: str | None
    """Stable, machine-readable reason, when the invoicing system refused the request
    (e.g. `ENTITY_NOT_FOUND`). Absent on request validation and authentication errors."""
    messages: list[str]
    """Every message of the response: one per field when validation fails."""
    request_id: str | None
    """`X-Request-Id` of the response. Quote it when contacting FIZ support."""
    idempotency_key: str | None
    """The Idempotency-Key the request carried, if it was a write. After a 409 whose outcome
    is unknown, check whether the write took effect before retrying with a NEW key."""
    body: Any
    """Parsed response body, as received."""
    headers: httpx.Headers

    def __init__(
        self,
        *,
        status: int,
        body: Any,
        headers: httpx.Headers,
        method: str,
        path: str,
        idempotency_key: str | None,
    ) -> None:
        messages = _messages_of(body)
        super().__init__(
            f"{method} {path} failed with {status}: {'; '.join(messages) or 'no message'}"
        )
        self.status = status
        self.body = body
        self.headers = headers
        self.messages = messages
        self.code = _code_of(body)
        self.request_id = headers.get("x-request-id")
        self.idempotency_key = idempotency_key

    @staticmethod
    def from_response(
        *,
        status: int,
        body: Any,
        headers: httpx.Headers,
        method: str,
        path: str,
        idempotency_key: str | None,
    ) -> FizApiError:
        """Builds the subclass that matches the status."""
        cls = _ERROR_BY_STATUS.get(status) or (FizServerError if status >= 500 else FizApiError)
        return cls(
            status=status,
            body=body,
            headers=headers,
            method=method,
            path=path,
            idempotency_key=idempotency_key,
        )


class FizBadRequestError(FizApiError):
    """400: the request was refused as invalid. Nothing was written."""


class FizAuthenticationError(FizApiError):
    """401: the API key or access token is missing, invalid or revoked."""


class FizPermissionError(FizApiError):
    """403: the credential cannot do this (scope, plan or permission)."""


class FizNotFoundError(FizApiError):
    """404: the record does not exist or is not visible to this credential."""


class FizConflictError(FizApiError):
    """409: a conflict. With an Idempotency-Key it means the first attempt is still running
    (the SDK already waited and retried) or that its outcome is unknown: check whether it took
    effect, then retry with a NEW key."""


class FizUnprocessableEntityError(FizApiError):
    """422: the Idempotency-Key was already used with a different request."""


class FizRateLimitError(FizApiError):
    """429: too many requests. The SDK already retried, honouring `Retry-After`."""


class FizServerError(FizApiError):
    """5xx: the API or a service behind it failed."""


_ERROR_BY_STATUS: dict[int, type[FizApiError]] = {
    400: FizBadRequestError,
    401: FizAuthenticationError,
    403: FizPermissionError,
    404: FizNotFoundError,
    409: FizConflictError,
    422: FizUnprocessableEntityError,
    429: FizRateLimitError,
}


class FizConnectionError(FizError):
    """No response arrived (network failure or timeout). A write that carried an
    Idempotency-Key is safe to repeat with the SAME key, which the SDK does automatically
    before raising this."""

    idempotency_key: str | None

    def __init__(self, message: str, idempotency_key: str | None) -> None:
        super().__init__(message)
        self.idempotency_key = idempotency_key


class FizTimeoutError(FizConnectionError):
    """An attempt exceeded the timeout."""


def _messages_of(body: Any) -> list[str]:
    if isinstance(body, str):
        return [body] if body else []
    if not isinstance(body, dict):
        return []
    message = body.get("message")
    if isinstance(message, str):
        return [message]
    if isinstance(message, list):
        return [m for m in message if isinstance(m, str)]
    return []


def _code_of(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    code = body.get("code")
    return code if isinstance(code, str) and code else None
