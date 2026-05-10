"""Tests voor de pure beslislogica: prijs + max_watts -> target_watts."""
import pytest

from decide import decide_target_watts, should_write


@pytest.mark.parametrize("prijs,max_watts,expected", [
    # Negatieve prijs -> 0 W
    (-0.0001, 5500, 0.0),
    (-0.5,    5500, 0.0),
    # Nul -> volle limit (strikt negatief is de drempel)
    (0.0,     5500, 5500.0),
    # Positief -> volle limit
    (0.0001,  5500, 5500.0),
    (0.42,    5500, 5500.0),
    # Andere max_watts respecteren
    (-0.1,    3000, 0.0),
    (0.1,     3000, 3000.0),
])
def test_decide_target_watts(prijs, max_watts, expected):
    assert decide_target_watts(prijs, max_watts) == expected


@pytest.mark.parametrize("current,target,expected", [
    # Identiek -> niet schrijven
    (5500.0, 5500.0, False),
    (0.0,    0.0,    False),
    # Verschil > 1 W -> schrijven
    (5500.0, 0.0,    True),
    (0.0,    5500.0, True),
    # Drift binnen 1 W -> niet schrijven (omvormer rapporteert soms 5499.8)
    (5499.8, 5500.0, False),
    (0.5,    0.0,    False),
    # Drift net buiten 1 W -> wel schrijven
    (5498.0, 5500.0, True),
])
def test_should_write(current, target, expected):
    assert should_write(current, target) is expected
