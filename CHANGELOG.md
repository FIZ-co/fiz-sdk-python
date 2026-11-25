# Changelog

Versions follow [semver](https://semver.org). Changes to the API itself are
in the [API changelog](https://api.fiz.co/docs/changelog).

## 0.1.0 — 2026-11-25

First release.

- Every operation of the FIZ API, with `TypedDict` request and response
  types generated from its OpenAPI document.
- An `Idempotency-Key` on every write, reused by automatic retries.
- Retries of rate-limited requests, of writes still in progress and of
  failed reads, honouring `Retry-After`.
- Errors as exceptions with `status`, `code`, `messages` and `request_id`.
- `list_all` iterators over every list, and PDF downloads.
- API key or OAuth access token; a `fiz_test_` key reaches the sandbox.
- Credentials go to the API's origin only: redirects are never followed
  on API calls, and a file download drops them when a redirect leaves the
  API origin.
- An `Idempotency-Key` the API would refuse (empty, spaces, over 128
  characters) is refused before sending; a response whose body is cut off
  is retried with the same key, or reported with it.
- `on_response` hook: every response's operation, status, `request_id`,
  key, replay flag, attempt and timing.
- Python 3.10 or later; `httpx` is the only runtime dependency (plus
  `typing-extensions` before Python 3.13).
