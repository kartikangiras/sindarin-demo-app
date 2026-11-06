"""SPEC-1 acceptance tests: CSV export of orders for finance."""

from __future__ import annotations

import csv
import io
import threading
from dataclasses import asdict, fields
from http.client import HTTPConnection
from http.server import HTTPServer

import pytest

import app.server as server_module
from app.orders import (
    COLUMNS,
    MAX_ROWS,
    ExportTooLarge,
    Order,
    export_csv,
    export_orders,
    sample_orders,
)
from app.server import Handler


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()


def get(srv, path="/orders.csv"):
    conn = HTTPConnection("127.0.0.1", srv.server_port, timeout=10)
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read().decode("utf-8")
    return r, body


def get_export(srv):
    return get(srv, "/orders.csv")


def parse(text):
    return list(csv.reader(io.StringIO(text, newline="")))


def many(n):
    return [Order(i, "c", 1, "2026-11-01") for i in range(n)]


# Criterion 1: content-type text/csv and a .csv filename.


def test_content_type(server):
    r, _ = get_export(server)
    assert r.status == 200
    assert r.getheader("Content-Type", "").startswith("text/csv")


def test_csv_filename(server):
    r, _ = get_export(server)
    disposition = r.getheader("Content-Disposition", "")
    assert disposition.startswith("attachment")
    assert 'filename="orders.csv"' in disposition


def test_export_action_on_orders_page(server):
    r, body = get(server, "/orders")
    assert r.status == 200
    assert r.getheader("Content-Type", "").startswith("text/html")
    assert 'href="/orders.csv"' in body and "Export CSV" in body


# Criterion 2: header naming every order field, one row per order, a value for every column.


def test_header_names_every_order_field(server):
    _, body = get_export(server)
    assert parse(body)[0] == [f.name for f in fields(Order)]


def test_header_row_when_empty():
    text = export_csv([])
    assert text.splitlines()[0] == ",".join(COLUMNS)
    assert parse(text) == [list(COLUMNS)]


def test_rows_follow_header():
    text = export_csv(sample_orders(2))
    lines = text.splitlines()
    assert lines[0] == ",".join(COLUMNS) and len(lines) == 3
    assert lines[1].startswith("1,acme-1,")


def test_one_row_per_order_matching_values(server, monkeypatch):
    orders = sample_orders(25)
    monkeypatch.setattr(server_module, "ORDERS", orders)
    _, body = get_export(server)
    rows = parse(body)[1:]
    assert len(rows) == len(orders)
    for order, row in zip(orders, rows):
        assert len(row) == len(COLUMNS)
        assert row == [str(v) for v in asdict(order).values()]


# Criterion 3: RFC 4180 escaping, round-trips through a standard parser.


TRICKY = [
    "comma, inc",
    'say "hi"',
    "line1\nline2",
    "crlf\r\nline",
    '"all", of\nthem"',
    "",
    " leading space",
]


def test_escaping_round_trips(server, monkeypatch):
    orders = [Order(i, c, i, "2026-11-01") for i, c in enumerate(TRICKY, start=1)]
    monkeypatch.setattr(server_module, "ORDERS", orders)
    _, body = get_export(server)
    rows = parse(body)[1:]
    assert [row[1] for row in rows] == TRICKY


def test_rfc4180_quoting():
    text = export_csv([Order(1, 'a,"b"\nc', 2, "2026-11-01")])
    assert text == 'id,customer,total_cents,placed_at\r\n1,"a,""b""\nc",2,2026-11-01\r\n'


# Criterion 4: up to 10,000 orders succeeds with exactly that many data rows.


def test_exactly_cap_succeeds():
    export = export_orders(many(MAX_ROWS))
    rows = parse(export.text)[1:]
    assert export.rows == MAX_ROWS == len(rows)
    assert rows[-1][0] == str(MAX_ROWS - 1)


def test_response_at_cap_has_every_row(server, monkeypatch):
    monkeypatch.setattr(server_module, "ORDERS", many(MAX_ROWS))
    r, body = get_export(server)
    assert r.status == 200
    assert r.getheader("X-Export-Rows") == str(MAX_ROWS)
    assert len(parse(body)) - 1 == MAX_ROWS


# Criterion 5: above 10,000 orders, a clear error naming the limit, no truncated file.


def test_above_cap_raises():
    with pytest.raises(ExportTooLarge) as exc:
        export_orders(many(MAX_ROWS + 1))
    assert "10,000" in str(exc.value)


def test_response_above_cap_is_clear_error(server, monkeypatch):
    monkeypatch.setattr(server_module, "ORDERS", many(MAX_ROWS + 5))
    r, body = get_export(server)
    assert r.status == 422
    assert r.getheader("Content-Type", "").startswith("text/plain")
    assert r.getheader("Content-Disposition") is None
    assert "10,000 rows" in body
    assert "id,customer" not in body
