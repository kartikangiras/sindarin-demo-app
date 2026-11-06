"""A minimal HTTP server: the orders page and GET /orders.csv (SPEC-1).

Run with `python -m app.server`.
"""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.orders import COLUMNS, export_last_month, recent_sample_orders, utcnow

ORDERS = recent_sample_orders()

# The request clock; tests replace it to pin "now".
now = utcnow

ROWS_HEADER = "X-Export-Rows"
MATCHED_HEADER = "X-Export-Matched"
TRUNCATED_HEADER = "X-Export-Truncated"
NOTICE_HEADER = "X-Export-Notice"
EXPORT_PATH = "/orders.csv"


def orders_page(orders) -> str:
    """The orders page with its Export CSV action."""
    head = "".join(f"<th>{html.escape(c)}</th>" for c in COLUMNS)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(getattr(o, c)))}</td>" for c in COLUMNS) + "</tr>"
        for o in orders
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Orders</title></head><body>"
        "<h1>Orders</h1>"
        f'<p><a id="export-csv" href="{EXPORT_PATH}" download="orders.csv">Export CSV</a></p>'
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        "</body></html>"
    )


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, content_type: str, body: bytes, extra=()) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path in ("/", "/orders"):
            self._send(200, "text/html; charset=utf-8", orders_page(ORDERS).encode("utf-8"))
            return
        if self.path != EXPORT_PATH:
            self.send_error(404)
            return
        # Criterion 2: only orders created in the 30 days before this request.
        export = export_last_month(ORDERS, now())
        extra = [
            # Criterion 1: a .csv attachment.
            ("Content-Disposition", 'attachment; filename="orders.csv"'),
            (ROWS_HEADER, str(export.rows)),
            (MATCHED_HEADER, str(export.matched)),
            (TRUNCATED_HEADER, "true" if export.truncated else "false"),
        ]
        if export.truncated:
            extra.append((NOTICE_HEADER, export.notice))
        self._send(
            200,
            "text/csv; charset=utf-8; header=present",
            export.text.encode("utf-8"),
            extra=extra,
        )


def main() -> None:
    HTTPServer(("127.0.0.1", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
