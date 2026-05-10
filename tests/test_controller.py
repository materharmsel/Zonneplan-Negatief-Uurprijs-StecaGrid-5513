"""Tests voor de orkestratie-laag: run() doet de juiste calls op basis van prijs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pytest

from controller import run, RunOutcome
from inverter import ApplyResult


def make_inverter_apply(current_watts: float) -> tuple[Callable, list]:
    """Bouw een fake inverter.apply_power_limit + log van calls."""
    calls = []

    def fake(ip, password, target_watts):
        calls.append({"ip": ip, "password": password, "target": target_watts})
        did_write = abs(current_watts - target_watts) > 1.0
        return ApplyResult(
            previous_watts=current_watts,
            target_watts=target_watts,
            did_write=did_write,
        )

    return fake, calls


def test_run_writes_zero_when_price_negative():
    fake_apply, calls = make_inverter_apply(current_watts=5500.0)
    outcome = run(
        price_getter=lambda: -0.0023,
        ip="1.2.3.4",
        password="pw",
        max_watts=5500,
        inverter_apply=fake_apply,
    )
    assert calls == [{"ip": "1.2.3.4", "password": "pw", "target": 0.0}]
    assert outcome.did_write is True
    assert outcome.target_watts == 0.0
    assert outcome.price == -0.0023


def test_run_writes_max_when_price_positive():
    fake_apply, calls = make_inverter_apply(current_watts=0.0)
    outcome = run(
        price_getter=lambda: 0.0412,
        ip="1.2.3.4",
        password="pw",
        max_watts=5500,
        inverter_apply=fake_apply,
    )
    assert calls[0]["target"] == 5500.0
    assert outcome.did_write is True


def test_run_no_write_when_already_correct():
    fake_apply, calls = make_inverter_apply(current_watts=5500.0)
    outcome = run(
        price_getter=lambda: 0.0412,  # positief -> target 5500
        ip="1.2.3.4",
        password="pw",
        max_watts=5500,
        inverter_apply=fake_apply,
    )
    assert outcome.did_write is False


def test_run_zero_price_does_not_limit():
    """Drempel is strikt < 0; precies 0.0 telt niet als negatief."""
    fake_apply, calls = make_inverter_apply(current_watts=5500.0)
    outcome = run(
        price_getter=lambda: 0.0,
        ip="1.2.3.4",
        password="pw",
        max_watts=5500,
        inverter_apply=fake_apply,
    )
    assert calls[0]["target"] == 5500.0
    assert outcome.did_write is False


def test_run_propagates_price_getter_exception():
    fake_apply, calls = make_inverter_apply(current_watts=5500.0)

    def bad_getter():
        raise RuntimeError("Zonneplan API down")

    with pytest.raises(RuntimeError, match="Zonneplan"):
        run(
            price_getter=bad_getter,
            ip="1.2.3.4",
            password="pw",
            max_watts=5500,
            inverter_apply=fake_apply,
        )
    # inverter mag niet zijn aangeroepen als prijs ophalen faalt
    assert calls == []
