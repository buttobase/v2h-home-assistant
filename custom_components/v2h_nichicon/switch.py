from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Nichicon V2H switches from a config entry."""
    _LOGGER.info("Setting up Nichicon V2H switches")
    async_add_entities([V2HDebugSwitch()])


class V2HDebugSwitch(SwitchEntity):
    """Simple placeholder switch."""

    _attr_name = "V2H Debug Switch"
    _attr_unique_id = "v2h_debug_switch"

    def __init__(self) -> None:
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
