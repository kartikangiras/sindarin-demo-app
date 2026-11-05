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
from app.orders import COLUMNS, MAX_ROWS, Order, export_csv, export_orders, sample_orders
from app.server import Handler


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()


def get_export(srv):
    conn = HTTPConnection("127.0.0.1", srv.server_port)
    conn.request("GET", "/orders.csv")
    r = conn.getresponse()
    body = r.read().decode("utf-8")
    return r, body


def parse(text):
    return list(csv.reader(io.StringIO(text, newline="")))


# Criterion 1: 200, text/csv, header row naming every order field.


def test_content_type(server):
    r, _ = get_export(server)
    assert r.status == 200
    assert r.getheader("Content-Type", "").startswith("text/csv")


def test_header_names_every_order_field(server):
    _, body = get_export(server)
    assert parse(body)[0] == [f.name for f in fields(Order)]


def test_header_row_when_empty():
    text = export_csv([])
    assert text.splitlines()[0] == ",".join(COLUMNS)
    assert parse(text) == [list(COLUMNS)]


# Criterion 2: one data row per order, values match the order.


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
        assert row == [str(v) for v in asdict(order).values()]


# Criterion 3: above 10,000 orders, exactly 10,000 data rows and a truncation mark.


def test_truncated_at_cap():
    big = [Order(i, "c", 1, "2026-11-01") for i in range(MAX_ROWS + 1)]
    export = export_orders(big)
    rows = parse(export.text)[1:]
    assert export.truncated is True
    assert export.rows == MAX_ROWS == len(rows)
    assert rows[-1][0] == str(MAX_ROWS - 1)


def test_not_truncated_at_exactly_cap():
    export = export_orders([Order(i, "c", 1, "2026-11-01") for i in range(MAX_ROWS)])
    assert export.truncated is False
    assert export.rows == MAX_ROWS


def test_response_marks_truncation(server, monkeypatch):
    monkeypatch.setattr(
        server_module, "ORDERS", [Order(i, "c", 1, "2026-11-01") for i in range(MAX_ROWS + 5)]
    )
    r, body = get_export(server)
    assert r.status == 200
    assert r.getheader("X-Export-Truncated") == "true"
    assert r.getheader("X-Export-Rows") == str(MAX_ROWS)
    assert len(parse(body)) - 1 == MAX_ROWS


def test_response_not_truncated_normally(server):
    r, _ = get_export(server)
    assert r.getheader("X-Export-Truncated") == "false"


# Criterion 4: RFC 4180 escaping, round-trips through a standard parser.


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
