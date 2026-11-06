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


# Every order field, one column each, in declaration order (criterion 1).
COLUMNS = tuple(f.name for f in fields(Order))


@dataclass(frozen=True)
class CsvExport:
    text: str
    rows: int  # data rows in the file
    matched: int  # orders that matched the request
    truncated: bool  # True when matched > rows (criterion 3)

    @property
    def notice(self) -> str:
        if not self.truncated:
            return ""
        return (
            f"Export truncated: {self.matched:,} orders matched, only the first "
            f"{self.rows:,} rows are included (limit {MAX_ROWS:,} rows per export)."
        )


def sample_orders(n: int = 3) -> list[Order]:
    return [Order(i, f"acme-{i}", 1000 * i, f"2026-11-0{(i % 9) + 1}") for i in range(1, n + 1)]


def export_orders(orders: list[Order], limit: int = MAX_ROWS) -> CsvExport:
    """Orders as RFC 4180 CSV with a header row and one data row per order.

    At most `limit` orders are written; when more match, the export holds exactly `limit`
    data rows and is marked truncated (criterion 3). The csv module quotes fields holding
    commas, quotes or newlines, doubles inner quotes and ends records with CRLF (criterion 4).
    """
    matched = len(orders)
    kept = orders[:limit]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(COLUMNS)
    for order in kept:
        writer.writerow(astuple(order))
    return CsvExport(text=buf.getvalue(), rows=len(kept), matched=matched, truncated=matched > limit)


def export_csv(orders: list[Order], limit: int = MAX_ROWS) -> str:
    """CSV text only; see `export_orders` for the row count and truncation flag."""
    return export_orders(orders, limit).text
