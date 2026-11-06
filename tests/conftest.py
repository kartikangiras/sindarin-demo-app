"""Pin the export clock so the 30-day window (SPEC-1 criterion 2) is deterministic."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import app.server as server_module

FROZEN_NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    monkeypatch.setattr(server_module, "now", lambda: FROZEN_NOW)
    return FROZEN_NOW
