from __future__ import annotations

import contextlib
import json
import math
import os
import platform
import random
import re
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Any, Literal
from urllib.parse import quote, urlencode

import httpx

from ._compat import Self
from .errors import FizApiError, FizConnectionError, FizError, FizTimeoutError
from .generated.calls import TypedCalls
from .generated.operations import OPERATIONS
from .options import AppInfo, RequestOptions
from .version import VERSION

DEFAULT_BASE_URL = "https://api.fiz.co"
SANDBOX_KEY_PREFIX = "fiz_test_"
DEFAULT_MAX_RETRIES = 2
DEFAULT_TIMEOUT = 60.0
MAX_RETRY_AFTER = 60.0
"""A longer Retry-After (seconds) is not waited for: the error is raised instead."""
MAX_REDIRECTS = 5
IDEMPOTENCY_KEY_PATTERN = re.compile(r"[\x21-\x7e]{1,128}")
"""What the API accepts as an Idempotency-Key: 1–128 visible ASCII characters."""
_HTTP_WHITESPACE = " \t\r\n"

Environment = Literal["production", "sandbox"]


@dataclass(frozen=True)
class FizResponseInfo:
    """What `on_response` receives for each response."""

    operation_id: str
    """The OpenAPI operation, e.g. `InvoicesController_issue`."""
    method: str
    path: str
    """The route as documented, e.g. `/invoices/{id}/issue`."""
    status: int
    request_id: str | None
    """`X-Request-Id`: quote it to FIZ support."""
    idempotency_key: str | None
    """The key a write was sent with."""
    replayed: bool
    """True when the API replayed the stored result of an earlier attempt."""
    attempt: int
    """1 for the first attempt, 2 for the first retry, …"""
    duration_ms: float
    """From sending the request to receiving the response headers."""


class FizClient(TypedCalls):
    """Low-level HTTP client: auth, Idempotency-Key, retries and error mapping. Each
    resource method is a typed wrapper around `call()`."""

    base_url: str
    max_retries: int
    timeout: float
    environment: Environment
    """`sandbox` for a `fiz_test_` key; OAuth tokens and other keys reach production."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        base_url: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
        app_info: AppInfo | None = None,
        on_response: Callable[[FizResponseInfo], object] | None = None,
    ) -> None:
        """
        Args:
            api_key: API key (`x-api-key`), created at
                https://app.fiz.co/settings/integrations. Defaults to the `FIZ_API_KEY`
                environment variable. A key starting with `fiz_test_` reaches the sandbox:
                AT test services, no fiscal effect.
            access_token: OAuth access token of a registered app, sent as a bearer token.
            base_url: Default `https://api.fiz.co`.
            max_retries: Automatic retries of a failed attempt (default 2). See the README.
            timeout: Timeout of each attempt, in seconds (default 60): it bounds connecting,
                sending and each read.
            http_client: An `httpx.Client` to send requests with (proxies, custom transport).
                The SDK never lets it follow redirects. A file the API links to on another
                host (where a PDF is stored) is fetched with a client of the SDK's own, so
                nothing configured on yours (headers, cookies, auth, event hooks) reaches
                that host; it honours the HTTP(S)_PROXY and SSL_CERT_FILE environment
                variables. Closing yours is yours.
            app_info: Your integration's name and version, added to the User-Agent.
            on_response: Called with every response to an API operation, retries included
                (not the file download behind `download_pdf`): for logging the request id
                of each call (support, audit) or measuring latency. Whatever it raises is
                ignored: it never fails the call.
        """
        if api_key and access_token:
            raise FizError("Pass either api_key or access_token, not both.")
        key = None
        if not access_token:
            key = api_key if api_key is not None else (os.environ.get("FIZ_API_KEY") or None)
        if not key and not access_token:
            raise FizError(
                "No credential: pass api_key (or set FIZ_API_KEY) or access_token. "
                "API keys are created at https://app.fiz.co/settings/integrations."
            )
        self._auth_headers = (
            {"x-api-key": key} if key else {"authorization": f"Bearer {access_token}"}
        )
        self.environment = "sandbox" if key and key.startswith(SANDBOX_KEY_PREFIX) else "production"
        self.base_url = (base_url if base_url is not None else DEFAULT_BASE_URL).rstrip("/")
        self.max_retries = max_retries
        self.timeout = timeout
        self._http = http_client if http_client is not None else httpx.Client()
        self._owns_http = http_client is None
        # For files on another origin, created on first use (see download()).
        self._file_http: httpx.Client | None = None
        # Two threads downloading at once must not each create one: close() would
        # close only the one stored last.
        self._file_http_lock = threading.Lock()
        self._user_agent = _user_agent(app_info)
        self._on_response = on_response

    def close(self) -> None:
        """Closes the connection pools (not an `http_client` you passed in)."""
        if self._owns_http:
            self._http.close()
        with self._file_http_lock:
            if self._file_http is not None:
                self._file_http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _call(
        self,
        operation_id: str,
        path: Mapping[str, str] | None,
        query: Mapping[str, Any] | None,
        body: Any,
        options: RequestOptions,
    ) -> Any:
        operation = OPERATIONS.get(operation_id)
        if operation is None:
            raise FizError(f"Unknown operation {operation_id}")

        url_path = _expand_path(operation.path, path)
        url = self.base_url + url_path + _query_string(query)
        request = f"{operation.method} {url_path}"
        # Case-insensitive: a caller's `Idempotency-Key` next to our `idempotency-key`
        # must end up as one header, not two.
        headers = httpx.Headers(
            {"accept": "application/json", "user-agent": self._user_agent, **self._auth_headers}
        )
        for name, value in (options.get("headers") or {}).items():
            headers[name] = value
        # One key for the whole call, every retry included. A key the caller gave (option
        # or header) is checked here: an empty one would send no header while the retry
        # logic still treated the write as safe to repeat.
        idempotency_key: str | None = None
        if operation.idempotent:
            given = options.get("idempotency_key")
            if given is None and "idempotency-key" in headers:
                given = headers["idempotency-key"].strip(_HTTP_WHITESPACE)
            idempotency_key = _checked_idempotency_key(given)
            headers["idempotency-key"] = idempotency_key
        elif "idempotency-key" in headers:
            del headers["idempotency-key"]
        content = None
        if body is not None:
            headers["content-type"] = "application/json"
            content = json.dumps(
                body, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode()

        max_retries = options.get("max_retries", self.max_retries)
        timeout = options.get("timeout", self.timeout)
        # Safe to repeat without knowing whether the first attempt arrived: a read, or a
        # write carrying an Idempotency-Key (the API replays the first result).
        repeatable = operation.method == "GET" or idempotency_key is not None

        attempt = 0
        while True:
            can_retry = attempt < max_retries
            # Two ways an attempt can go without a usable answer, decided apart:
            #  - no status at all (the request may or may not have arrived): repeat only
            #    what is safe to repeat blind;
            #  - a status whose body was cut off: the status still decides, exactly as
            #    with a body (a 503 or 429 keeps its own rules and Retry-After). Only a
            #    success whose body is lost is a lost response, which the same
            #    Idempotency-Key recovers.
            try:
                sent_at = time.monotonic()
                response = self._send(operation.method, url, headers, content, timeout)
            except httpx.RequestError as error:
                if not repeatable or not can_retry:
                    raise _no_response_error(error, request, timeout, idempotency_key) from error
                _sleep(_backoff(attempt))
                attempt += 1
                continue

            payload: Any = None
            body_lost: Exception | None = None
            try:
                self._report(
                    FizResponseInfo(
                        operation_id=operation_id,
                        method=operation.method,
                        path=operation.path,
                        status=response.status_code,
                        request_id=response.headers.get("x-request-id"),
                        idempotency_key=idempotency_key,
                        replayed=response.headers.get("idempotent-replayed") == "true",
                        attempt=attempt + 1,
                        duration_ms=(time.monotonic() - sent_at) * 1000,
                    )
                )
                try:
                    raw = response.read()
                    # Every operation answers a success in JSON (tests/test_coverage.py
                    # holds the API document to that), so a success is parsed as JSON
                    # whatever Content-Type says, and one that does not parse is a lost
                    # response: issue() must not "succeed" with half an invoice or an HTML
                    # page. Strictly JSON: Python's NaN and Infinity are not, and would hand
                    # the caller a number no API response contains. An error body is read
                    # loosely; its status decides.
                    payload = _parse_json(raw) if response.is_success else _parse_error_body(raw)
                except (httpx.RequestError, ValueError) as error:
                    body_lost = error
            finally:
                response.close()

            if response.is_success:
                if body_lost is None:
                    return payload
                if not repeatable or not can_retry:
                    raise _no_response_error(
                        body_lost, request, timeout, idempotency_key
                    ) from body_lost
                _sleep(_backoff(attempt))
                attempt += 1
                continue
            if 300 <= response.status_code < 400:
                # Not followed: the credentials go to the API's origin only.
                raise FizError(
                    f"{request} answered with a redirect{_location(response)}; it was not followed."
                )

            api_error = FizApiError.from_response(
                status=response.status_code,
                body=payload,
                headers=response.headers,
                method=operation.method,
                path=url_path,
                idempotency_key=idempotency_key,
            )
            retry_after = _retry_after(response.headers)
            if (
                not can_retry
                # Waiting less than the server asked would only earn another refusal.
                or (retry_after is not None and retry_after > MAX_RETRY_AFTER)
                or not _should_retry(
                    response.status_code, operation.method, idempotency_key, retry_after
                )
            ):
                raise api_error
            _sleep(retry_after if retry_after is not None else _backoff(attempt))
            attempt += 1

    def download(self, file_url: str, *, timeout: float | None = None) -> bytes:
        """Downloads a file the API linked to (a PDF, an export). Credentials are sent only
        to the API's own origin, checked again on every redirect (at most 5)."""
        api_origin = _origin(httpx.URL(self.base_url))
        attempt_timeout = timeout if timeout is not None else self.timeout
        url = httpx.URL(file_url)
        for _hop in range(MAX_REDIRECTS + 1):
            label = f"Downloading {url.path}"
            try:
                if _origin(url) == api_origin:
                    headers = httpx.Headers({"user-agent": self._user_agent, **self._auth_headers})
                    response = self._send("GET", url, headers, None, attempt_timeout)
                else:
                    response = self._send_foreign(url, attempt_timeout)
            except httpx.RequestError as error:
                raise _no_response_error(error, label, attempt_timeout, None) from error
            try:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location:
                        raise FizError(f"{label}: a redirect without a Location header")
                    url = url.join(location)
                    continue
                if not response.is_success:
                    raise FizError(f"{label} failed with {response.status_code}")
                try:
                    return response.read()
                except httpx.RequestError as error:
                    raise _no_response_error(error, label, attempt_timeout, None) from error
            finally:
                response.close()
        raise FizError(
            f"Downloading {httpx.URL(file_url).path}: more than {MAX_REDIRECTS} redirects"
        )

    def _report(self, info: FizResponseInfo) -> None:
        if self._on_response is None:
            return
        # A logging hook must never fail or retry the call it observes.
        with contextlib.suppress(Exception):
            self._on_response(info)

    def _send(
        self,
        method: str,
        url: str | httpx.URL,
        headers: httpx.Headers,
        content: bytes | None,
        timeout: float,
    ) -> httpx.Response:
        request = self._http.build_request(
            method, url, headers=headers, content=content, timeout=timeout
        )
        # Never followed automatically: a redirect keeps custom headers such as x-api-key,
        # whatever origin it points to. Streamed, so that a status whose body is then cut
        # off is still known.
        return self._http.send(request, stream=True, follow_redirects=False)

    def _send_foreign(self, url: httpx.URL, timeout: float) -> httpx.Response:
        """A GET to another origin (where a file is stored), never through the caller's
        http_client: its default headers, cookies and auth could be stripped from a
        request, but its event hooks and transport would still run on it, and either may
        add a credential. The SDK's own client carries none of that."""
        client = self._file_client()
        request = client.build_request(
            "GET", url, headers={"user-agent": self._user_agent}, timeout=timeout
        )
        return client.send(request, stream=True, follow_redirects=False)

    def _file_client(self) -> httpx.Client:
        client = self._file_http
        if client is None:
            with self._file_http_lock:
                client = self._file_http
                if client is None:
                    client = self._file_http = httpx.Client()
        return client


def _should_retry(
    status: int, method: str, idempotency_key: str | None, retry_after: float | None
) -> bool:
    """Which failed responses are retried, following the API's idempotency rules:

    - 429: refused before the request ran.
    - 409 with Retry-After on a keyed write: the first attempt is still running; the same
      key returns its result once done. A 409 without Retry-After means the outcome is
      unknown and must not be retried blindly.
    - 502/503/504 on a read. On a write, a 5xx may already have taken effect and the key is
      spent; retrying would only answer 409.
    """
    if status == 429:
        return True
    if status == 409:
        return idempotency_key is not None and retry_after is not None
    if status in (502, 503, 504):
        return method == "GET"
    return False


def _expand_path(template: str, params: Mapping[str, Any] | None) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        value = params.get(name) if params else None
        if value is None or value == "":
            raise FizError(f'Missing path parameter "{name}" for {template}')
        # What encodeURIComponent leaves as is.
        return quote(str(value), safe="!*'()")

    return re.sub(r"\{([^}]+)\}", replace, template)


def _query_string(query: Mapping[str, Any] | None) -> str:
    if not query:
        return ""
    pairs: list[tuple[str, str]] = []
    for key, value in query.items():
        for item in value if isinstance(value, (list, tuple)) else [value]:
            if item is None:
                continue
            pairs.append((key, _query_value(item)))
    text = urlencode(pairs)
    return f"?{text}" if text else ""


def _query_value(item: Any) -> str:
    if isinstance(item, bool):
        return "true" if item else "false"
    if isinstance(item, datetime):
        # As JavaScript's toISOString(): UTC, milliseconds, `Z`. A naive value is local.
        utc = item.astimezone(timezone.utc).isoformat(timespec="milliseconds")
        return utc.replace("+00:00", "Z")
    if isinstance(item, date):
        return item.isoformat()
    if isinstance(item, float) and item.is_integer():
        return str(int(item))
    return str(item)


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")


def _parse_json(raw: bytes) -> Any:
    """A success body as strict JSON (RFC 8259): `json.loads` alone also takes NaN,
    Infinity and -Infinity, which no JSON encoder writes."""
    return json.loads(raw, parse_constant=_reject_constant)


def _parse_error_body(raw: bytes) -> Any:
    """An error response's body: its JSON when it is JSON, else the text, if any."""
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except ValueError:
        return text or None


def _retry_after(headers: httpx.Headers) -> float | None:
    """Retry-After in seconds (a number of seconds or an HTTP date), never negative."""
    value = headers.get("retry-after")
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        seconds = math.nan
    if not math.isfinite(seconds):
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    return max(seconds, 0.0)


def _backoff(attempt: int) -> float:
    """0.5 s, 1 s, 2 s, … capped at 8 s, with ±25 % jitter."""
    base: float = min(0.5 * 2**attempt, 8.0)
    return base * (0.75 + random.random() * 0.5)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _user_agent(app_info: AppInfo | None) -> str:
    """`fiz-sdk-python/<version> python/<version> <app>/<version>`."""
    parts = [f"fiz-sdk-python/{VERSION}", f"python/{platform.python_version()}"]
    if app_info:
        version = app_info.get("version")
        parts.append(f"{app_info['name']}/{version}" if version else app_info["name"])
    return " ".join(parts)


def _no_response_error(
    error: Exception, request: str, timeout: float, idempotency_key: str | None
) -> FizConnectionError:
    """The error for an attempt that got no response: a timeout or a network failure."""
    if isinstance(error, httpx.TimeoutException):
        return FizTimeoutError(f"{request} timed out after {timeout:g} s", idempotency_key)
    reason = str(error) or type(error).__name__
    return FizConnectionError(f"{request} failed: no complete response ({reason})", idempotency_key)


def _checked_idempotency_key(given: str | None) -> str:
    """The caller's Idempotency-Key, refused before sending when the API would refuse it;
    a new UUID when there is none."""
    if given is None:
        return str(uuid.uuid4())
    if not isinstance(given, str) or not IDEMPOTENCY_KEY_PATTERN.fullmatch(given):
        raise FizError(
            "idempotency_key must be 1 to 128 visible ASCII characters (no spaces); "
            "omit it to have one generated."
        )
    return given


def _location(response: httpx.Response) -> str:
    target = response.headers.get("location")
    return f" to {target}" if target else ""


def _origin(url: httpx.URL) -> tuple[str, str, int | None]:
    default_port = {"http": 80, "https": 443}.get(url.scheme)
    return (url.scheme, url.host, url.port or default_port)
