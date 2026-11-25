from __future__ import annotations

import pytest

import fiz_sdk.client


@pytest.fixture(autouse=True)
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """No test waits: every pause the client takes is recorded here instead, in seconds."""
    recorded: list[float] = []
    monkeypatch.setattr(fiz_sdk.client, "_sleep", recorded.append)
    return recorded
