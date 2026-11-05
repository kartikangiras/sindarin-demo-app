"""A minimal HTTP server: GET /orders.csv (SPEC-1). Run with `python -m app.server`."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer

from app.orders import export_orders, sample_orders

ORDERS = sample_orders()

TRUNCATED_HEADER = "X-Export-Truncated"
ROWS_HEADER = "X-Export-Rows"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path != "/orders.csv":
            self.send_error(404)
            return
        export = export_orders(ORDERS)
        body = export.text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8; header=present")
        self.send_header("Content-Disposition", 'attachment; filename="orders.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header(ROWS_HEADER, str(export.rows))
        self.send_header(TRUNCATED_HEADER, "true" if export.truncated else "false")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    HTTPServer(("127.0.0.1", 8080), Handler).serve_forever()


if __name__ == "__main__":
    main()
