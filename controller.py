"""Main entrypoint — cron draait dit elke 15 minuten.

Architectuur:
- run() is testbaar: dependency injection voor price-getter en inverter-apply.
- main() is dun: config laden, logging opzetten, run() aanroepen, exit-code zetten.
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

import fetch_prices
import inverter
from decide import decide_target_watts

CONFIG_FILE = Path(__file__).parent / "config.yaml"

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunOutcome:
    price: float
    target_watts: float
    previous_watts: float
    did_write: bool


def run(
    *,
    price_getter: Callable[[], float],
    ip: str,
    password: str,
    max_watts: float,
    inverter_apply: Callable[..., inverter.ApplyResult],
) -> RunOutcome:
    """Pure orkestratie. Geen IO behalve via de injected callables."""
    price = price_getter()
    target = decide_target_watts(price, max_watts)
    log.info("prijs huidig uur: %+.4f EUR/kWh  -> target %.0f W", price, target)

    result = inverter_apply(ip, password, target)

    if result.did_write:
        log.info("limit gewijzigd: %.0f W -> %.0f W", result.previous_watts, target)
    else:
        log.info("no change (limit=%.0f W)", result.previous_watts)

    return RunOutcome(
        price=price,
        target_watts=target,
        previous_watts=result.previous_watts,
        did_write=result.did_write,
    )


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Geen config gevonden op {path}. "
            f"Kopieer config.example.yaml naar config.yaml en vul in."
        )
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def main() -> int:
    _setup_logging()

    try:
        cfg = _load_config(CONFIG_FILE)
        inv = cfg["inverter"]
        run(
            price_getter=fetch_prices.fetch_current_price,
            ip=inv["ip"],
            password=inv["password"],
            max_watts=float(inv["max_watts"]),
            inverter_apply=inverter.apply_power_limit,
        )
    except SystemExit:
        raise
    except Exception as e:
        log.error("run faalde: %s: %s", type(e).__name__, e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
