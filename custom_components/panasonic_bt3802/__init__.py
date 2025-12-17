from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN
from .coordinator import PanasonicBT3802Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    coordinator = PanasonicBT3802Coordinator(hass)
    hass.data.setdefault(DOMAIN, {})["coordinator"] = coordinator

    await coordinator.async_refresh()

    _LOGGER.info("Panasonic BT3802 polling started (static IP)")

    await async_load_platform(hass, "sensor", DOMAIN, {}, config)

    return True
