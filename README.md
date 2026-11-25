# FIZ SDK for Python

Issue **AT-certified invoices in Portugal** from your code. FIZ is invoicing
software certified by the Autoridade Tributária (No. 3041): it numbers each
document in its series, adds the ATCUD and the QR code, reports it to the AT
when it is issued and returns the number and the PDF.

This is the official client for the [FIZ API](https://api.fiz.co): every
operation typed from the API's OpenAPI document, with safe retries built in.

[Português](#português) · [API reference](https://api.fiz.co) ·
[Quickstart](https://api.fiz.co/docs/quickstart) ·
[Changelog](https://api.fiz.co/docs/changelog)

```bash
pip install fiz-sdk
```

Python 3.10 or later (CI tests 3.10 to 3.13). Keep the key on your server: an
API key acts for the whole company, so it must never ship inside an app or
page that other people run.

## Quickstart

Run it with a **sandbox key**: create one at [app.fiz.co → Settings → Integrations](https://app.fiz.co/settings/integrations)
and put it in `FIZ_API_KEY`. A key starting with `fiz_test_` sends documents
to the AT test services, with no fiscal effect. The walkthrough below stops on
any other key, because its last step issues a real invoice with a production
key.

```python
from fiz_sdk import Fiz

fiz = Fiz()  # reads FIZ_API_KEY
if fiz.environment != "sandbox":
    raise SystemExit("Use a sandbox key (fiz_test_…) for this walkthrough.")

# Which company is this, and can it issue yet?
company = fiz.company.retrieve()
if not company["readiness"]["ready"]:
    print(company["readiness"]["reasons"])
# Every invoice states one of the company's activity codes (CAE).
if not company["cae"]:
    raise SystemExit("The company has no CAE yet: add its activity in FIZ first.")
cae = company["cae"][0]

customer = fiz.customers.create({"name": "Example customer", "country": "PT"})
item = fiz.items.create(
    {"name": "Example service", "type": "SERVICE", "unitPrice": 10, "vatRate": "NORMAL"}
)

# A draft has no number and no fiscal effect.
draft = fiz.invoices.create(
    {
        "type": "INVOICE",
        "cae": cae,
        "customerId": customer["id"],
        "items": [{"id": item["id"], "quantity": 1}],
    }
)
pdf = fiz.invoices.download_pdf(draft["id"])  # bytes

# Issuing is fiscal and irreversible with a production key: numbered, ATCUD,
# reported to the AT. expectedUpdatedAt issues exactly the draft you looked
# at, and refuses it if it changed since.
# Without a revision there is nothing to check against: stop rather than
# issue whatever the draft is by then.
revision = draft["updatedAt"]
if not revision:
    raise SystemExit("The draft came back without its revision.")
invoice = fiz.invoices.issue(draft["id"], {"expectedUpdatedAt": revision})
print(invoice["number"], invoice["atcud"])
```

A runnable version is in [`examples/quickstart.py`](examples/quickstart.py).
It issues in two runs: the first creates the draft and saves its PDF, the
second issues that draft by its id, after you have looked at it.

## What it covers

| | |
|---|---|
| `fiz.invoices` | invoices, simplified invoices, invoice-receipts: `create`, `list`, `list_all`, `retrieve`, `update`, `delete`, `issue`, `pay`, `cancel`, `pdf`, `download_pdf` |
| `fiz.credit_notes` | full or per-line credit notes (issued at once unless `"issue": False`) |
| `fiz.recurring_invoices` | invoices FIZ issues on a schedule |
| `fiz.proposals` | pro formas (no fiscal effect) |
| `fiz.transport_documents` | guias de transporte (GR, GT, GA, GC, GD) |
| `fiz.customers`, `fiz.items` | customers and the item catalogue |
| `fiz.series`, `fiz.templates` | invoice series, PDF templates |
| `fiz.company`, `fiz.vat` | the company and issuance readiness, VAT rules |
| `fiz.expenses`, `fiz.bank` | e-Fatura expenses, bank transactions |
| `fiz.exports` | SAF-T PT export |

Methods marked **fiscal and irreversible** in their documentation (`issue`,
`pay`, `cancel`, credit notes) report to the AT when used with a production
key.

Requests and responses are plain dicts with the API's own field names
(`customerId`, `updatedAt`), typed as `TypedDict`s. Any operation of the API
is also reachable by its OpenAPI `operationId`, typed the same way, including
ones this SDK version does not wrap in a method yet:

```python
series = fiz.call("SeriesController_getAll")
```

## Errors

Every failed request raises a `FizApiError` subclass. Branch on `status` and
`code`; the message is for people and its wording may change.

```python
from fiz_sdk import FizApiError, FizNotFoundError

try:
    fiz.invoices.retrieve(invoice_id)
except FizNotFoundError:
    ...  # 404
except FizApiError as error:
    print(error.status, error.code, error.messages)
    print("Quote to support:", error.request_id)
    raise
```

| Class | Status |
|---|---|
| `FizBadRequestError` | 400 — refused as invalid; `messages` has one line per field |
| `FizAuthenticationError` | 401 — key or token missing, invalid or revoked |
| `FizPermissionError` | 403 — scope, plan or permission |
| `FizNotFoundError` | 404 |
| `FizConflictError` | 409 — see [Retries](#retries-and-idempotency) |
| `FizUnprocessableEntityError` | 422 — Idempotency-Key reused with a different request |
| `FizRateLimitError` | 429 |
| `FizServerError` | 5xx |
| `FizConnectionError`, `FizTimeoutError` | no response |

All of them derive from `FizError`.

## Retries and idempotency

Every write carries an `Idempotency-Key`. The API remembers it for 30 days
and answers a repeat with the original response, so a timeout never costs a
duplicate invoice. The SDK generates one per call (a UUID) and reuses it for
its own retries. Pass yours to make retries safe across restarts too, for
example the id of the order the invoice is for:

```python
fiz.invoices.create(draft, idempotency_key=f"order-{order.id}-invoice")
```

The SDK retries (default `max_retries=2`) only what is safe to repeat:

- no response at all, on a read or a write carrying a key;
- `429`, after `Retry-After` (a wait longer than a minute is not taken: the error is raised);
- `409` with `Retry-After`: the first attempt is still running, and the same
  key returns its result;
- `502`, `503`, `504` on a read.

It does **not** retry a `409` without `Retry-After` or a `5xx` on a write:
the first attempt may have taken effect. Check whether it did (list the
documents), then repeat with a **new** key. `error.idempotency_key` tells you
which key was spent.

## Pagination

`list` returns one page. `list_all` walks every page as you iterate:

```python
for listed in fiz.invoices.list_all({"status": "ISSUED"}):
    print(listed["number"])
```

## OAuth apps

A [registered app](https://api.fiz.co/docs/apps) calls the API on behalf of
the companies that installed it, with an OAuth access token:

```python
fiz = Fiz(access_token=access_token)
```

Getting and refreshing the token is your app's part of the flow; see the
[partner guide](https://api.fiz.co/docs/apps).

## Options

```python
import httpx

fiz = Fiz(
    api_key="fiz_…",  # default: the FIZ_API_KEY environment variable
    # access_token="…",  # instead of api_key
    base_url="https://api.fiz.co",
    max_retries=2,
    timeout=60.0,  # per attempt, seconds
    http_client=httpx.Client(),  # proxies, custom transport; never follows redirects
    app_info={"name": "my-shop", "version": "1.2.0"},  # added to the User-Agent
    on_response=lambda r: print(r.operation_id, r.status, r.request_id),  # every response
)
```

`on_response` is called with every response to an API operation, retries
included (the file download behind `download_pdf` is not an operation and is
not reported). It receives the operation, status, `request_id`, the
`Idempotency-Key`, whether the API replayed an earlier result, the attempt
number and the time to the response headers: enough to log the request id of
every invoice you issue. Whatever it raises is ignored.

Each method also takes per-call keyword options: `idempotency_key`,
`max_retries`, `timeout` and `headers`. `Fiz` is a context manager
(`with Fiz() as fiz:`) and has `close()`, which closes its connection pool.

## Types

Request and response types come from the API's OpenAPI document. Named
aliases cover the common ones (`Invoice`, `Customer`, `Item`, `Company`, …);
every schema is in `fiz_sdk.types`, by its name in the document:

```python
from fiz_sdk.types import CreateInvoiceDto, InvoiceItemDto


def invoice_for(customer_id: str, cae: str, lines: list[InvoiceItemDto]) -> CreateInvoiceDto:
    return {"type": "INVOICE", "cae": cae, "customerId": customer_id, "items": lines}
```

The package ships `py.typed`; mypy and pyright check your requests and
responses against these types.

## Coding agents

Using Claude Code, Cursor or Codex? Point the agent at
[`api.fiz.co/llms.txt`](https://api.fiz.co/llms.txt): it routes the agent by
task and states the fiscal rules first. The FIZ connector for Claude and
ChatGPT is described at [api.fiz.co/docs/mcp](https://api.fiz.co/docs/mcp).

## Development

With [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run python scripts/update_spec.py   # download https://api.fiz.co/-json and regenerate
./scripts/check.sh                     # lint, types, README examples, unit tests, build
FIZ_TEST_API_KEY=fiz_test_… uv run pytest -m sandbox
```

`src/fiz_sdk/generated/` is generated from `openapi/openapi.json`
(`uv run python scripts/generate.py`); never edit it by hand. When the API
adds an operation, the tests fail until a resource method wraps it.

**Releasing.** Bump `VERSION` in `src/fiz_sdk/version.py` and add the version
to `CHANGELOG.md`, merge, and push a tag (`git tag v0.1.1 && git push origin
v0.1.1`): the Release workflow runs the checks, builds, and publishes to PyPI
through trusted publishing, with no token. One-time setup is at the top of
`.github/workflows/release.yml`.

## Português

**Faturação certificada em Portugal a partir do seu código.** O FIZ é um
programa de faturação certificado pela AT (n.º 3041): numera cada documento
na série, junta o ATCUD e o código QR, comunica-o à AT no momento da emissão
e devolve o número e o PDF. Este é o cliente oficial da
[API FIZ](https://api.fiz.co/?lang=pt) para Python.

```bash
pip install fiz-sdk
```

1. Crie uma chave API em [app.fiz.co → Definições → Integrações](https://app.fiz.co/settings/integrations)
   e guarde-a em `FIZ_API_KEY`. Uma chave `fiz_test_` usa o **sandbox**:
   serviços de teste da AT, sem efeito fiscal.
2. Siga o exemplo do [Quickstart](#quickstart) com uma chave de sandbox:
   cliente e artigo → rascunho e PDF → emissão. Um rascunho não tem efeito
   fiscal; com uma chave de produção, a emissão é irreversível e comunicada à
   AT.
3. Cada escrita leva uma `Idempotency-Key`, reutilizada nas repetições
   automáticas: um timeout nunca dá origem a uma fatura duplicada.

Os erros trazem `status`, `code` e `request_id` (indique-o ao suporte). Guia
completo em [api.fiz.co/docs/quickstart?lang=pt](https://api.fiz.co/docs/quickstart?lang=pt).

## License

MIT
