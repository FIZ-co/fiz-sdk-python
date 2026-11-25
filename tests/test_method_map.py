from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fiz_sdk import OPERATIONS

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("method_map", ROOT / "scripts" / "method_map.py")
assert spec and spec.loader
method_map = importlib.util.module_from_spec(spec)
spec.loader.exec_module(method_map)


def test_method_map_json_matches_the_code() -> None:
    """The API docs show each operation in Python from this file: regenerate it with
    `uv run python scripts/method_map.py` after adding or renaming a method."""
    assert (ROOT / "method-map.json").read_text(encoding="utf-8") == method_map.render()


def test_every_operation_has_a_method_in_the_map() -> None:
    operations = json.loads((ROOT / "method-map.json").read_text(encoding="utf-8"))["operations"]
    assert sorted(operations) == sorted(OPERATIONS)
