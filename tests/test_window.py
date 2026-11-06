"""SPEC-1 criteria 1, 2, 3 and 5 for the finance export of the last 30 days."""

from __future__ import annotations

import csv
import io
import threading
from datetime import timedelta
from http.client import HTTPConnection
from http.server import HTTPServer

import pytest

import app.server as server_module
from app.orders import COLUMNS, Order, export_last_month, in_window, last_month
from app.server import Handler
from tests.conftest import FROZEN_NOW


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


def get_export(srv):
    conn = HTTPConnection("127.0.0.1", srv.server_port, timeout=10)
    conn.request("GET", "/orders.csv")
    r = conn.getresponse()
    return r, r.read().decode("utf-8")


def parse(text):
    return list(csv.reader(io.StringIO(text, newline="")))


def days_ago(n: int) -> str:
    return (FROZEN_NOW - timedelta(days=n)).date().isoformat()


# Criterion 1: text/csv with a .csv filename.


def test_csv_content_type_and_filename(server):
    r, _ = get_export(server)
    assert r.status == 200
    assert r.getheader("Content-Type", "").startswith("text/csv")
    disposition = r.getheader("Content-Disposition", "")
    assert disposition.startswith("attachment") and '.csv"' in disposition


# Criterion 2: exactly the orders from the 30 days before the request.


def test_today_included_31_days_ago_excluded(server, monkeypatch):
    orders = [
        Order(1, "today", 100, days_ago(0)),
        Order(2, "thirty", 200, days_ago(30)),
        Order(3, "thirty-one", 300, days_ago(31)),
        Order(4, "ten", 400, days_ago(10)),
        Order(5, "tomorrow", 500, days_ago(-1)),
    ]
    monkeypatch.setattr(server_module, "ORDERS", orders)
    _, body = get_export(server)
    ids = [row[0] for row in parse(body)[1:]]
    assert ids == ["1", "2", "4"]


def test_window_with_timestamps():
    now = FROZEN_NOW
    inside = Order(1, "a", 1, (now - timedelta(days=30) + timedelta(seconds=1)).isoformat())
    edge = Order(2, "b", 1, (now - timedelta(days=30)).isoformat())
    outside = Order(3, "c", 1, (now - timedelta(days=30, seconds=1)).isoformat())
    at_request = Order(4, "d", 1, now.isoformat().replace("+00:00", "Z"))
    after_request = Order(5, "e", 1, (now + timedelta(seconds=1)).isoformat())
    kept = last_month([inside, edge, outside, at_request, after_request], now)
    assert [o.id for o in kept] == [1, 2, 4]


def test_in_window_naive_timestamp_is_utc():
    assert in_window(Order(1, "a", 1, "2026-11-20T11:59:00"), FROZEN_NOW)
    assert not in_window(Order(1, "a", 1, "2026-10-21T11:59:00"), FROZEN_NOW)


# Criterion 3: header first, every row as wide as the header.


def test_every_row_matches_header_width(server, monkeypatch):
    orders = [Order(i, f"c,{i}\n\"x\"", i, days_ago(i % 30)) for i in range(50)]
    monkeypatch.setattr(server_module, "ORDERS", orders)
    _, body = get_export(server)
    rows = parse(body)
    assert rows[0] == list(COLUMNS)
    assert len(rows) == 51
    assert all(len(row) == len(rows[0]) for row in rows[1:])


# Criterion 5: no orders in the window gives a header-only file, no error.


def test_empty_window_header_only(server, monkeypatch):
    monkeypatch.setattr(server_module, "ORDERS", [Order(1, "old", 1, days_ago(45))])
    r, body = get_export(server)
    assert r.status == 200
    assert r.getheader("Content-Type", "").startswith("text/csv")
    assert parse(body) == [list(COLUMNS)]


def test_no_orders_at_all_header_only(server, monkeypatch):
    monkeypatch.setattr(server_module, "ORDERS", [])
    r, body = get_export(server)
    assert r.status == 200
    assert parse(body) == [list(COLUMNS)]


def test_export_last_month_empty():
    export = export_last_month([Order(1, "old", 1, days_ago(31))], FROZEN_NOW)
    assert export.rows == 0 and not export.truncated
    assert parse(export.text) == [list(COLUMNS)]
