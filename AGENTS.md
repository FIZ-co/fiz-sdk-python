# Agent rules for fiz-sdk-python

Rules every coding agent (Codex, Cursor, Claude Code, …) and every human
contributor follows in this repository. `CLAUDE.md` imports this file.

## This repository is public

Everything written here is world-readable and permanent: code, comments,
commit messages, pull request titles and descriptions, review comments, issue
replies. A force-push does not take it back; forks and mirrors keep it.

Write from the public API's side, as an outside integrator would read it:

- **Refer to the API only by what is public.** Operations as the OpenAPI
  document names them (`POST /invoices/{id}/issue`), fields and error `code`s
  as documented, the docs at https://api.fiz.co, the changelog at
  https://api.fiz.co/docs/changelog. Write "the API now returns `updatedAt`
  when a draft is created", not where that change was made.
- **Name no internal system.** Not FIZ's private repositories, internal
  services or their components, infrastructure, deploy pipelines, internal
  tools, trackers, chats, dashboards, or internal pull request and ticket
  numbers. If the reason for a change only makes sense with internal context,
  state the observable behaviour instead.
- **No customer or account data.** No company or person names, tax numbers,
  document numbers, record ids, request ids or log excerpts from any account,
  sandbox accounts included: sandbox output is shaped like real data and
  is treated as such. Examples use the placeholders the README uses
  (`Example customer`, `inv1`, `order-1042`).
- **No credentials.** Never commit an API key, live or `fiz_test_`. Tests and
  scripts read `FIZ_API_KEY` / `FIZ_TEST_API_KEY` from the environment;
  `.env` is ignored.
- **No internal process.** Who reviewed what, internal schedules, staffing,
  or decisions made elsewhere stay out. A commit explains *why* from the code
  and the API's documented behaviour.
- **English only**, in code, comments, commits, pull requests and reviews.

Before every push, read the diff, the commit message and the pull request
text once more against this list. Something internal that needs recording
belongs in FIZ's internal tracker, not here.

## What this is

The official Python client for the FIZ API: certified invoicing in Portugal
(documents numbered, with ATCUD and QR code, reported to the AT). Published
to PyPI as `fiz-sdk`, imported as `fiz_sdk`. Python 3.10+; the only runtime
dependency is `httpx` (and `typing-extensions` before Python 3.13). It
behaves like the JavaScript SDK (https://github.com/FIZ-co/fiz-sdk-js): same
resources and methods (in snake_case), same options, same safety rules.

```
openapi/openapi.json       the API document (from https://api.fiz.co/-json)
src/fiz_sdk/generated/     TypedDicts, the operation table and call() overloads
src/fiz_sdk/client.py      HTTP: auth, Idempotency-Key, retries, errors
src/fiz_sdk/errors.py      the exception classes
src/fiz_sdk/resources/     one typed method per API operation
src/fiz_sdk/__init__.py    the Fiz class and public exports
tests/                     unit tests (mocked transport); tests/sandbox/ hits the API
tests/typecheck/           compile-time checks, run by mypy
examples/quickstart.py     the runnable example
scripts/                   generate, update_spec, check_readme, check.sh
```

## Commands

```bash
uv sync                                  # create .venv with the pinned tools
uv run python scripts/update_spec.py     # download the live API document and regenerate
uv run python scripts/generate.py        # regenerate src/fiz_sdk/generated/
./scripts/check.sh                       # lint, format, types, README, tests, build
FIZ_TEST_API_KEY=fiz_test_… uv run pytest -m sandbox   # against the API sandbox
```

`./scripts/check.sh` is what CI runs, after checking that the generated code
is up to date; run both before every push.

## Rules of the code

- **Never edit `src/fiz_sdk/generated/` by hand.** Change the spec source or
  the generator and run `scripts/generate.py`; CI fails when the generated
  files differ.
- **Every API operation has a resource method.** `tests/test_coverage.py`
  fails until a new operation is wrapped; until then it is reachable through
  `fiz.call("<operationId>")`.
- **`method-map.json` follows the resource methods.** The API docs at
  api.fiz.co show each operation in Python from it (method and arguments).
  After adding or renaming a method run `uv run python scripts/method_map.py`;
  `tests/test_method_map.py` fails while it is out of date.
- **The client's safety rules are behaviour, not style.** A change to any of
  them comes with a test that fails on the previous client:
  - one `Idempotency-Key` per call, reused by every retry; an invalid key is
    refused before sending;
  - retries only where a repeat is safe (no response, 429, a 409 with
    `Retry-After` on a keyed write, 502/503/504 on reads), honouring
    `Retry-After`; a known status decides even when its body is lost;
  - a success must be JSON; anything else is a lost response;
  - redirects are not followed with credentials; credentials go only to the
    API origin.
- **Fiscal methods say so.** A method that issues, pays, cancels or credits
  (reported to the AT, irreversible with a production key) states it in its
  docstring.
- **Examples are safe to copy.** README and `examples/` run against the
  sandbox first, never issue without an explicit step, and issue exactly the
  draft that was reviewed. Every ```python block of the README compiles and
  type-checks (`scripts/check_readme.py`).

## Commits, pull requests, releases

- Conventional commits (`feat:`, `fix:`, `docs:`, `chore(spec):`, `ci:`),
  following the public-repository rules above.
- A change a user of the package can notice gets a line in `CHANGELOG.md`.
- Releasing: `VERSION` in `src/fiz_sdk/version.py` and `CHANGELOG.md`, then a
  `v<version>` tag; the Release workflow publishes to PyPI through trusted
  publishing. Details in the README, "Development".
