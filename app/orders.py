"""Orders and their CSV export (SPEC-1)."""

from __future__ import annotations

import csv
import io
from dataclasses import astuple, dataclass, fields

MAX_ROWS = 10_000


@dataclass(frozen=True)
class Order:
    id: int
    customer: str
    total_cents: int
    placed_at: str  # ISO date


# Every order field, one column each, in declaration order (criterion 2).
COLUMNS = tuple(f.name for f in fields(Order))


@dataclass(frozen=True)
class CsvExport:
    text: str
    rows: int


class ExportTooLarge(Exception):
    """Raised before any CSV is built when a request exceeds the row limit (criterion 5)."""

    def __init__(self, requested: int, limit: int = MAX_ROWS) -> None:
        self.requested = requested
        self.limit = limit
        super().__init__(
            f"Orders export is limited to {limit:,} rows; this request has {requested:,} orders. "
            "Narrow the request and try again."
        )


def sample_orders(n: int = 3) -> list[Order]:
    return [Order(i, f"acme-{i}", 1000 * i, f"2026-11-0{(i % 9) + 1}") for i in range(1, n + 1)]


def export_orders(orders: list[Order], limit: int = MAX_ROWS) -> CsvExport:
    """Orders as RFC 4180 CSV with a header row and one data row per order.

    More than `limit` orders raises `ExportTooLarge` up front: no partial or truncated file is
    ever produced (criteria 4, 5). The csv module quotes fields holding commas, quotes or
    newlines, doubles inner quotes and ends records with CRLF (criterion 3).
    """
    if len(orders) > limit:
        raise ExportTooLarge(len(orders), limit)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(COLUMNS)
    for order in orders:
        writer.writerow(astuple(order))
    return CsvExport(text=buf.getvalue(), rows=len(orders))


def export_csv(orders: list[Order], limit: int = MAX_ROWS) -> str:
    """CSV text only; see `export_orders` for the row count and the limit."""
    return export_orders(orders, limit).text
