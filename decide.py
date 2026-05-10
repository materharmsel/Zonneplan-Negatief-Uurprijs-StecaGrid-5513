"""Pure beslislogica voor de power-limit van de omvormer.

Geen IO, geen imports buiten stdlib. Volledig unit-testbaar.
"""

# Schrijven we alleen als de huidige limit meer dan deze marge afwijkt
# van de gewenste waarde. Voorkomt onnodige writes bij meet-drift (bv.
# 5499.8 i.p.v. 5500.0).
WRITE_TOLERANCE_WATTS = 1.0


def decide_target_watts(price_eur_per_kwh: float, max_watts: float) -> float:
    """Bepaal de gewenste vermogenslimiet voor het huidige uur.

    Strikt negatieve prijs -> 0 W (geen teruglevering).
    Anders -> volle nominale max_watts.
    """
    if price_eur_per_kwh < 0:
        return 0.0
    return float(max_watts)


def should_write(current_watts: float, target_watts: float) -> bool:
    """Bepaal of een schrijfactie nodig is (idempotentie)."""
    return abs(current_watts - target_watts) > WRITE_TOLERANCE_WATTS
