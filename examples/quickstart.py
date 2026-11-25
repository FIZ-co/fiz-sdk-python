"""The quickstart in two runs, so that what gets issued is the draft you looked at.

  FIZ_API_KEY=fiz_test_… python examples/quickstart.py
    → checks the company, creates a customer, an item and a draft, saves draft.pdf and
      prints the draft's id and revision.

  FIZ_API_KEY=fiz_test_… python examples/quickstart.py --issue <draft id> <revision>
    → issues THAT draft at THAT revision (its updatedAt when the PDF was made): if anyone
      changed it since, the API refuses instead of issuing a version you have not seen.

With a sandbox key (fiz_test_…) the invoice goes to the AT test services and has no fiscal
effect. With a production key, issuing is fiscal and irreversible, so the second run asks
you to add --production as well.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fiz_sdk import Fiz, FizApiError, FizConflictError


def create_draft(fiz: Fiz) -> None:
    # 1. Which company is this key for, and can it issue yet?
    company = fiz.company.retrieve()
    readiness = company["readiness"]
    print(f"{company['name']} ({company['environment']}), ready to issue: {readiness['ready']}")
    for reason in readiness["reasons"]:
        print(f"  - {reason['code']}: {reason['actionUrl']}")
    # Every invoice states one of the company's activity codes (CAE).
    if not company["cae"]:
        print("The company has no CAE yet: add its activity in FIZ first.")
        return
    cae = company["cae"][0]

    # 2. A customer and an item. A fixed Idempotency-Key per record makes a re-run return
    #    the same records instead of creating new ones.
    customer = fiz.customers.create(
        {"name": "Example customer", "country": "PT"}, idempotency_key="quickstart-customer"
    )
    item = fiz.items.create(
        {"name": "Example service", "type": "SERVICE", "unitPrice": 10, "vatRate": "NORMAL"},
        idempotency_key="quickstart-item",
    )

    # 3. A draft: no number, no fiscal effect. Then its PDF, to look at.
    draft = fiz.invoices.create(
        {
            "type": "INVOICE",
            "cae": cae,
            "customerId": customer["id"],
            "items": [{"id": item["id"], "quantity": 1}],
        }
    )
    Path("draft.pdf").write_bytes(fiz.invoices.download_pdf(draft["id"]))
    # The revision is what makes the second run issue exactly this draft. Without one there
    # is nothing to check against, so there is no command.
    revision = draft["updatedAt"]
    if not revision:
        print(f"Draft {draft['id']} saved to draft.pdf, but the API returned no revision for it.")
        print("Issue it from the FIZ app after reviewing it, or create it again.")
        return
    print(f"Draft {draft['id']} saved to draft.pdf. Look at it, then issue it with:")
    print(f"  python examples/quickstart.py --issue {draft['id']} {revision}")


def issue_draft(fiz: Fiz, id: str, revision: str, production: bool) -> None:
    if not id or not revision:
        print("Usage: --issue <draft id> <revision>, as the first run printed them.")
        return
    if fiz.environment == "production" and not production:
        print("This is a production key: issuing reports a real invoice to the AT.")
        print(f"Add --production to issue draft {id}.")
        return
    # 4. Issue the draft at the revision you looked at: numbered, ATCUD and QR code,
    #    reported to the AT. Not re-read here on purpose: the revision from the first run is
    #    what makes a later change refuse the issue.
    try:
        issued = fiz.invoices.issue(id, {"expectedUpdatedAt": revision})
    except FizConflictError as error:
        if error.code == "INVOICE_DRAFT_MODIFIED":
            print(
                "The draft changed after its PDF was made, so it was not issued. "
                "Run the first step again."
            )
            return
        raise
    print(f"Issued {issued['number']}, ATCUD {issued['atcud']}")


def main(argv: list[str]) -> int:
    fiz = Fiz()  # reads FIZ_API_KEY
    try:
        if "--issue" in argv:
            at = argv.index("--issue")
            args = [*argv[at + 1 : at + 3], "", ""]
            issue_draft(fiz, args[0], args[1], "--production" in argv)
        else:
            create_draft(fiz)
    except FizApiError as error:
        print(f"{error.status} {error.code or ''}: {'; '.join(error.messages)}", file=sys.stderr)
        print(f"Request id for support: {error.request_id}", file=sys.stderr)
        return 1
    finally:
        fiz.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
