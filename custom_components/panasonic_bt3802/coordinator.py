from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    PANASONIC_URL,
    CSV_DATA_LINE_INDEX,
    CSV_COL_BOUGHT,
    CSV_COL_SOLD,
)

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=60)


def _safe_float(value: str) -> float:
    try:
        return float(value.strip())
    except Exception:
        return 0.0


def _parse_bt3802_csv(csv_text: str) -> tuple[float, float]:
    """
    Parse Panasonic BT3802 sys_current.csv.

    Your confirmed format:
    - raw CSV line 3 contains the current values row
    - column 65 = bought (kW), column 66 = sold (kW)
    """
    lines = csv_text.splitlines()
    if len(lines) <= CSV_DATA_LINE_INDEX:
        raise ValueError(f"CSV too short: {len(lines)} lines")

    row = lines[CSV_DATA_LINE_INDEX].split(",")
    if len(row) <= max(CSV_COL_BOUGHT, CSV_COL_SOLD):
        raise ValueError(f"CSV row too short: {len(row)} cols")

    bought = _safe_float(row[CSV_COL_BOUGHT])
    sold = _safe_float(row[CSV_COL_SOLD])

    # Enforce exclusivity
    if bought > 0:
        sold = 0.0
    elif sold > 0:
        bought = 0.0

    return round(bought, 3), round(sold, 3)


class PanasonicBT3802Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Panasonic BT3802 polling."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Panasonic BT3802 Coordinator",
            update_interval=POLL_INTERVAL,
        )
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with self._session.get(PANASONIC_URL, timeout=10) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP {resp.status}")

                raw = await resp.read()
                # Panasonic CSV is typically CP932/Shift-JIS.
                text = raw.decode("cp932", errors="ignore")

            bought, sold = _parse_bt3802_csv(text)
            return {
                "grid_power_bought_kw": bought,
                "grid_power_sold_kw": sold,
            }

        except Exception as err:
            raise UpdateFailed(f"Error fetching/parsing BT3802 CSV: {err}") from err
