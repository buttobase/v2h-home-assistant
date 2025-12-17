from __future__ import annotations

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .v2h_api import NichiconV2HClient
from .coordinator import V2HCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "v2h_nichicon"
PLATFORMS: Final[list[Platform]] = [Platform.SENSOR, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up via YAML (unused)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nichicon V2H from config entry."""

    # Default host for now
    host = "192.168.0.20"   # <-- we will move this into config flow later

    _LOGGER.info("Setting up Nichicon V2H for host %s", host)

    # Create async API client
    client = NichiconV2HClient(host)

    # Create DataUpdateCoordinator
    coordinator = V2HCoordinator(hass, client)

    # Store coordinator for platforms to access
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    # Start polling
    await coordinator.async_config_entry_first_refresh()

    # Forward entry to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
