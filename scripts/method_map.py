"""Writes method-map.json: which method of the client wraps each API operation, and the
arguments it takes, in order. The API docs (api.fiz.co, the reference by resource) read
it to show each operation in Python; tests/test_method_map.py keeps it equal to the code.

  uv run python scripts/method_map.py          # rewrites method-map.json
  uv run python scripts/method_map.py --check  # fails when it is out of date
"""

from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

from fiz_sdk import OPERATIONS, Fiz
from fiz_sdk.resources._base import Resource

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "method-map.json"
CALL = re.compile(r'\.call\(\s*"(\w+)"')


def build() -> dict[str, Any]:
    fiz = Fiz(api_key="fiz_test_method_map")
    operations: dict[str, Any] = {}
    # Attributes and methods in the order they are declared: when two methods wrap one
    # operation, the first one declared is the one to show.
    for attr, resource in vars(fiz).items():
        if not isinstance(resource, Resource):
            continue
        for name, function in vars(type(resource)).items():
            if name.startswith("_") or not inspect.isfunction(function):
                continue
            source = inspect.getsource(function)
            found = CALL.search(source)
            if not found:
                continue  # a helper on top of another method (list_all, download_pdf)
            operation_id = found.group(1)
            if operation_id in operations:
                continue
            # `path={"starterId": starter_id}`: the argument behind each path parameter.
            path_dict = re.search(r"path=\{([^}]*)\}", source)
            path_args = {
                arg: param
                for param, arg in re.findall(
                    r'"(\w+)":\s*(\w+)', path_dict.group(1) if path_dict else ""
                )
            }
            expected = set(re.findall(r"\{(\w+)\}", OPERATIONS[operation_id].path))
            if set(path_args.values()) != expected:
                raise SystemExit(
                    f"{attr}.{name}: path parameters {sorted(expected)} not all passed"
                )
            params = []
            for parameter in list(inspect.signature(function).parameters.values())[1:]:
                if parameter.kind is parameter.VAR_KEYWORD:
                    continue
                where = (
                    "path"
                    if parameter.name in path_args
                    else parameter.name
                    if parameter.name in ("body", "query")
                    else None
                )
                if where is None:
                    raise SystemExit(
                        f"{attr}.{name}: argument {parameter.name!r} is neither a path "
                        "parameter, body nor query"
                    )
                entry: dict[str, Any] = {
                    "name": parameter.name,
                    "in": where,
                    "required": parameter.default is parameter.empty,
                }
                if where == "path":
                    entry["param"] = path_args[parameter.name]
                params.append(entry)
            operations[operation_id] = {"method": f"{attr}.{name}", "params": params}
    return {"language": "python", "operations": dict(sorted(operations.items()))}


def render() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("method-map.json is out of date: run scripts/method_map.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
