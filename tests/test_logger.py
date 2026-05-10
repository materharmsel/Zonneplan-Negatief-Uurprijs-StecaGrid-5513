"""Tests voor logger.py: schrijf-pad naar SQLite + integratie met controller.run()."""
from __future__ import annotations

import sqlite3

import pytest

import logger
from controller import run
from inverter import ApplyResult
from logger import LogReading, _write_reading


def _make_reading(timestamp: str = "2026-05-10T14:00:00+00:00", **overrides) -> LogReading:
    base = dict(
        timestamp=timestamp,
        price_eur_kwh=-0.0023,
        power_limit_w=0.0,
        pv_power_w=1234.5,
        grid_power_w=-987.0,
        inverter_state=6,
        yield_day_wh=12345.0,
        yield_month_wh=234567.0,
        yield_year_wh=3456789.0,
        yield_total_wh=45678900.0,
    )
    base.update(overrides)
    return LogReading(**base)


def test_write_creates_table(tmp_path):
    db = tmp_path / "t.db"
    _write_reading(db, _make_reading())

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='readings'"
        ).fetchall()
        assert rows == [("readings",)]
        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_readings_timestamp'"
        ).fetchall()
        assert idx == [("idx_readings_timestamp",)]
    finally:
        conn.close()


def test_write_all_nulls(tmp_path):
    db = tmp_path / "nulls.db"
    reading = LogReading(
        timestamp="2026-05-10T15:00:00+00:00",
        price_eur_kwh=0.05,
        power_limit_w=5500.0,
        pv_power_w=None,
        grid_power_w=None,
        inverter_state=None,
        yield_day_wh=None,
        yield_month_wh=None,
        yield_year_wh=None,
        yield_total_wh=None,
    )
    _write_reading(db, reading)

    conn = sqlite3.connect(db)
    try:
        row = conn.execute(
            "SELECT pv_power_w, grid_power_w, inverter_state, yield_day_wh,"
            " yield_month_wh, yield_year_wh, yield_total_wh FROM readings"
        ).fetchone()
        assert row == (None, None, None, None, None, None, None)
    finally:
        conn.close()


def test_write_idempotent(tmp_path):
    db = tmp_path / "idem.db"
    ts = "2026-05-10T16:00:00+00:00"
    _write_reading(db, _make_reading(timestamp=ts, pv_power_w=100.0))
    _write_reading(db, _make_reading(timestamp=ts, pv_power_w=200.0))

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT pv_power_w FROM readings WHERE timestamp = ?", (ts,)).fetchall()
        assert rows == [(200.0,)]
        count = conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
        assert count == 1
    finally:
        conn.close()


def _fake_apply(ip, password, target_watts):
    return ApplyResult(previous_watts=5500.0, target_watts=target_watts, did_write=False)


def test_controller_calls_logger(tmp_path):
    calls = []

    def fake_logger(*, ip, password, db_path, price_eur_kwh, power_limit_w):
        calls.append({
            "ip": ip, "password": password, "db_path": db_path,
            "price_eur_kwh": price_eur_kwh, "power_limit_w": power_limit_w,
        })
        return _make_reading()

    db = str(tmp_path / "ctrl.db")
    outcome = run(
        price_getter=lambda: -0.01,
        ip="1.2.3.4",
        password="pw",
        max_watts=5500,
        inverter_apply=_fake_apply,
        logger_fn=fake_logger,
        db_path=db,
    )

    assert outcome.target_watts == 0.0
    assert len(calls) == 1
    assert calls[0]["ip"] == "1.2.3.4"
    assert calls[0]["password"] == "pw"
    assert calls[0]["db_path"] == db
    assert calls[0]["price_eur_kwh"] == -0.01
    assert calls[0]["power_limit_w"] == 0.0


def test_controller_logger_failure_nonfatal(tmp_path):
    def boom(**kwargs):
        raise RuntimeError("DB stuk")

    outcome = run(
        price_getter=lambda: 0.05,
        ip="1.2.3.4",
        password="pw",
        max_watts=5500,
        inverter_apply=_fake_apply,
        logger_fn=boom,
        db_path=str(tmp_path / "x.db"),
    )

    # run moet gewoon een outcome opleveren ondanks dat logger crasht
    assert outcome.target_watts == 5500.0
    assert outcome.price == 0.05
