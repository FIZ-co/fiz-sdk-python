from __future__ import annotations

import re
from importlib.metadata import version
from pathlib import Path

from fiz_sdk import VERSION, __version__

ROOT = Path(__file__).resolve().parent.parent


def test_the_installed_distribution_has_this_version() -> None:
    # pyproject.toml reads the version from src/fiz_sdk/version.py.
    assert version("fiz-sdk") == VERSION == __version__


def test_the_changelog_describes_this_version() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = re.search(r"^## (\S+)", changelog, re.MULTILINE)
    assert first is not None
    assert first.group(1) == VERSION
