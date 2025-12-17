from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up V2H sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    async_add_entities([
        V2HChargingPowerSensor(coordinator),
        V2HDischargingPowerSensor(coordinator),
        V2HModeSensor(coordinator),
    ])


class BaseV2HSensor(SensorEntity):
    """Base class for V2H coordinator-backed sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        return False

    async def async_update(self):
        """We don't poll; coordinator handles updates."""
        pass

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class V2HChargingPowerSensor(BaseV2HSensor):
    _attr_name = "Charging Power"
    _attr_unique_id = "v2h_charging_power_kw"
    _attr_native_unit_of_measurement = "kW"

    @property
    def native_value(self):
        status = self.coordinator.data
        return status.charging_power_kw if status else None


class V2HDischargingPowerSensor(BaseV2HSensor):
    _attr_name = "Discharging Power"
    _attr_unique_id = "v2h_discharging_power_kw"
    _attr_native_unit_of_measurement = "kW"

    @property
    def native_value(self):
        status = self.coordinator.data
        return status.discharging_power_kw if status else None


class V2HModeSensor(BaseV2HSensor):
    _attr_name = "Mode"
    _attr_unique_id = "v2h_mode"

    @property
    def native_value(self):
        status = self.coordinator.data
        return status.mode if status else None
