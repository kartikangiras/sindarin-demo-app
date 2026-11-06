"""Orders and their CSV export (SPEC-1)."""

from __future__ import annotations

import csv
import io
from dataclasses import astuple, dataclass, fields
from datetime import date, datetime, timedelta, timezone

MAX_ROWS = 10_000
WINDOW_DAYS = 30


@dataclass(frozen=True)
class Order:
    id: int
    customer: str
    total_cents: int
    placed_at: str  # ISO date (YYYY-MM-DD) or ISO datetime


# Every order field, one column each, in declaration order (criterion 3: header row).
COLUMNS = tuple(f.name for f in fields(Order))


@dataclass(frozen=True)
class CsvExport:
    text: str
    rows: int  # data rows in the file
    matched: int  # orders that matched the request
    truncated: bool  # True when matched > rows

    @property
    def notice(self) -> str:
        if not self.truncated:
            return ""
        return (
            f"Export truncated: {self.matched:,} orders matched, only the first "
            f"{self.rows:,} rows are included (limit {MAX_ROWS:,} rows per export)."
        )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sample_orders(n: int = 3) -> list[Order]:
    return [Order(i, f"acme-{i}", 1000 * i, f"2026-11-0{(i % 9) + 1}") for i in range(1, n + 1)]


def recent_sample_orders(n: int = 3, now: datetime | None = None) -> list[Order]:
    """Sample orders placed in the last few days, so the demo export is never empty."""
    today = (now or utcnow()).date()
    return [Order(i, f"acme-{i}", 1000 * i, (today - timedelta(days=i - 1)).isoformat()) for i in range(1, n + 1)]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def in_window(order: Order, now: datetime, days: int = WINDOW_DAYS) -> bool:
    """True when the order was created in the `days` days before `now`, up to `now` (criterion 2).

    Date-only values compare by calendar day: today and the day `days` days ago are included,
    the day before that is not. Full timestamps compare exactly against `now - days`.
    """
    now = _as_utc(now)
    text = order.placed_at.strip()
    if len(text) == 10:  # YYYY-MM-DD
        placed = date.fromisoformat(text)
        return (now - timedelta(days=days)).date() <= placed <= now.date()
    placed_at = _as_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    return now - timedelta(days=days) <= placed_at <= now


def last_month(orders: list[Order], now: datetime | None = None, days: int = WINDOW_DAYS) -> list[Order]:
    """Orders created in the last `days` days, in their stored order (criterion 2)."""
    now = now or utcnow()
    return [o for o in orders if in_window(o, now, days)]


def export_orders(orders: list[Order], limit: int = MAX_ROWS) -> CsvExport:
    """Orders as RFC 4180 CSV with a header row and one data row per order.

    The header is always written, so an empty list yields a header-only file (criterion 5).
    The csv module quotes fields holding commas, quotes or newlines, doubles inner quotes and
    ends records with CRLF (criterion 4). At most `limit` orders are written; when more match
    the export is marked truncated.
    """
    matched = len(orders)
    kept = orders[:limit]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(COLUMNS)
    for order in kept:
        writer.writerow(astuple(order))
    return CsvExport(text=buf.getvalue(), rows=len(kept), matched=matched, truncated=matched > limit)


def export_last_month(orders: list[Order], now: datetime | None = None, limit: int = MAX_ROWS) -> CsvExport:
    """The finance export: orders from the last 30 days as CSV (criteria 2-5)."""
    return export_orders(last_month(orders, now), limit)


def export_csv(orders: list[Order], limit: int = MAX_ROWS) -> str:
    """CSV text only; see `export_orders` for the row count and truncation flag."""
    return export_orders(orders, limit).text
