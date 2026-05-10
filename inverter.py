"""Sync wrapper rond pykoplenti voor de StecaGrid 5513.

pykoplenti is async; controller.py is sync. Deze module verbergt asyncio
volledig en exposeert één synchrone functie: apply_power_limit().
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp
from pykoplenti import ApiClient

log = logging.getLogger(__name__)

# Module-id en setting-id zoals waargenomen in /api/v1/settings.
# Zie network-capture analyse in design-doc.
MODULE = "devices:local"
SETTING = "Inverter:ActivePowerLimitation"


@dataclass(frozen=True)
class ApplyResult:
    """Resultaat van een apply_power_limit-call."""
    previous_watts: float
    target_watts: float
    did_write: bool


def apply_power_limit(
    ip: str,
    password: str,
    target_watts: float,
    *,
    write_tolerance: float = 1.0,
) -> ApplyResult:
    """Lees de huidige limit, schrijf alleen als die meer dan tolerance afwijkt.

    Synchroon. Doet één login-sessie en sluit die af.

    :raises pykoplenti.AuthenticationException: bij verkeerd wachtwoord
    :raises aiohttp.ClientError: bij netwerk-/HTTP-fouten
    """
    return asyncio.run(_apply_power_limit_async(ip, password, target_watts, write_tolerance))


async def _apply_power_limit_async(
    ip: str,
    password: str,
    target_watts: float,
    write_tolerance: float,
) -> ApplyResult:
    async with aiohttp.ClientSession() as session:
        async with ApiClient(session, host=ip) as client:
            await client.login(password)

            current_str = (await client.get_setting_values(MODULE, SETTING))[MODULE][SETTING]
            current_watts = float(current_str)

            if abs(current_watts - target_watts) <= write_tolerance:
                log.debug("inverter: geen schrijfactie nodig (current=%.1f, target=%.1f)",
                          current_watts, target_watts)
                return ApplyResult(current_watts, target_watts, did_write=False)

            await client.set_setting_values(MODULE, {SETTING: str(target_watts)})
            log.debug("inverter: limit gewijzigd %.1f -> %.1f W", current_watts, target_watts)
            return ApplyResult(current_watts, target_watts, did_write=True)
