"""Downloads the canonical (English) OpenAPI document into openapi/openapi.json,
then regenerates src/fiz_sdk/generated/. FIZ_SPEC_URL overrides the source,
e.g. an API running locally.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    url = os.environ.get("FIZ_SPEC_URL", "https://api.fiz.co/-json")
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        spec = json.load(response)
    if not isinstance(spec, dict) or "openapi" not in spec or "paths" not in spec:
        raise SystemExit(f"{url} is not an OpenAPI document")
    # Written as JSON.stringify(spec, null, 2) writes it: the same bytes as
    # the other FIZ SDKs commit.
    (ROOT / "openapi" / "openapi.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Saved {url} ({len(spec['paths'])} paths)")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate.py")], check=True)


if __name__ == "__main__":
    main()
