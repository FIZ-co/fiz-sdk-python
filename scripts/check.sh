#!/bin/sh
# What CI runs on every push: lint, format, types, README examples, unit tests, build.
set -eu
cd "$(dirname "$0")/.."
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts/check_readme.py
uv run pytest
uv build
