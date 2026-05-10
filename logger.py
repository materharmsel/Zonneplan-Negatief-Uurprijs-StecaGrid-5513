"""Telemetrie-logger: schrijf één rij per cron-run naar SQLite.

Patroon volgt inverter.py: sync publieke functie, asyncio.run() intern,
frozen dataclass als return-type. Faalt bewust niet hard wanneer telemetrie
niet beschikbaar is — alle telemetrievelden zijn nullable.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from pykoplenti.extended import ExtendedApiClient

log = logging.getLogger(__name__)

_REQUEST = {
    "_virt_": ["pv_P"],
    "devices:local": ["Grid:P", "Inverter:State"],
    "scb:statistic:EnergyFlow": [
        "Statistic:Yield:Day",
        "Statistic:Yield:Month",
        "Statistic:Yield:Year",
        "Statistic:Yield:Total",
    ],
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    timestamp        TEXT PRIMARY KEY,
    price_eur_kwh    REAL,
    power_limit_w    REAL,
    pv_power_w       REAL,
    grid_power_w     REAL,
    inverter_state   INTEGER,
    yield_day_wh     REAL,
    yield_month_wh   REAL,
    yield_year_wh    REAL,
    yield_total_wh   REAL
);
CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings (timestamp);
"""


@dataclass(frozen=True)
class LogReading:
    timestamp: str
    price_eur_kwh: float
    power_limit_w: float
    pv_power_w: float | None
    grid_power_w: float | None
    inverter_state: int | None
    yield_day_wh: float | None
    yield_month_wh: float | None
    yield_year_wh: float | None
    yield_total_wh: float | None


@dataclass(frozen=True)
class _Telemetry:
    pv_power_w: float | None
    grid_power_w: float | None
    inverter_state: int | None
    yield_day_wh: float | None
    yield_month_wh: float | None
    yield_year_wh: float | None
    yield_total_wh: float | None

    @classmethod
    def empty(cls) -> "_Telemetry":
        return cls(None, None, None, None, None, None, None)


def log_reading(
    *,
    ip: str,
    password: str,
    db_path: str | Path,
    price_eur_kwh: float,
    power_limit_w: float,
) -> LogReading:
    """Lees telemetrie van de omvormer en schrijf één rij naar de SQLite-DB.

    Mislukt nooit door omvormer-fouten: telemetrievelden worden None bij failure.
    Kan wél falen op DB-fouten (caller vangt die af als niet-fataal).
    """
    telemetry = asyncio.run(_fetch_telemetry(ip, password))
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    reading = LogReading(
        timestamp=timestamp,
        price_eur_kwh=price_eur_kwh,
        power_limit_w=power_limit_w,
        pv_power_w=telemetry.pv_power_w,
        grid_power_w=telemetry.grid_power_w,
        inverter_state=telemetry.inverter_state,
        yield_day_wh=telemetry.yield_day_wh,
        yield_month_wh=telemetry.yield_month_wh,
        yield_year_wh=telemetry.yield_year_wh,
        yield_total_wh=telemetry.yield_total_wh,
    )

    _write_reading(db_path, reading)
    return reading


async def _fetch_telemetry(ip: str, password: str) -> _Telemetry:
    try:
        async with aiohttp.ClientSession() as session:
            async with ExtendedApiClient(session, host=ip) as client:
                await client.login(password)
                values = await client.get_process_data_values(_REQUEST)

                virt = values.get("_virt_", {})
                local = values.get("devices:local", {})
                stats = values.get("scb:statistic:EnergyFlow", {})

                state_raw = local.get("Inverter:State")
                return _Telemetry(
                    pv_power_w=_to_float(virt.get("pv_P")),
                    grid_power_w=_to_float(local.get("Grid:P")),
                    inverter_state=int(state_raw) if state_raw is not None else None,
                    yield_day_wh=_to_float(stats.get("Statistic:Yield:Day")),
                    yield_month_wh=_to_float(stats.get("Statistic:Yield:Month")),
                    yield_year_wh=_to_float(stats.get("Statistic:Yield:Year")),
                    yield_total_wh=_to_float(stats.get("Statistic:Yield:Total")),
                )
    except Exception as exc:
        log.warning("telemetrie ophalen mislukt: %s: %s", type(exc).__name__, exc)
        return _Telemetry.empty()


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)


def _write_reading(db_path: str | Path, reading: LogReading) -> None:
    resolved = _resolve_path(db_path)
    conn = sqlite3.connect(resolved)
    try:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO readings (
                timestamp, price_eur_kwh, power_limit_w,
                pv_power_w, grid_power_w, inverter_state,
                yield_day_wh, yield_month_wh, yield_year_wh, yield_total_wh
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reading.timestamp,
                reading.price_eur_kwh,
                reading.power_limit_w,
                reading.pv_power_w,
                reading.grid_power_w,
                reading.inverter_state,
                reading.yield_day_wh,
                reading.yield_month_wh,
                reading.yield_year_wh,
                reading.yield_total_wh,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _resolve_path(db_path: str | Path) -> str:
    # sqlite3.connect accepteert :memory: alleen als string. Path('~') expandeert niet vanzelf.
    if isinstance(db_path, str) and db_path == ":memory:":
        return db_path
    s = os.path.expanduser(str(db_path))
    return s
