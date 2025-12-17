from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfPower
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Panasonic BT3802 sensors (YAML platform)."""

    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities(
        [
            PanasonicGridPowerBoughtSensor(coordinator),
            PanasonicGridPowerSoldSensor(coordinator),
        ]
    )


class _BasePanasonicSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = "power"
    _attr_state_class = "measurement"
    _attr_should_poll = False

    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "bt3802")},
            name="Panasonic BT3802",
            manufacturer="Panasonic",
            model="BT3802",
        )


class PanasonicGridPowerBoughtSensor(_BasePanasonicSensor):
    _attr_name = "Grid Power Bought"
    _attr_unique_id = "panasonic_bt3802_grid_power_bought"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get("grid_power_bought_kw")


class PanasonicGridPowerSoldSensor(_BasePanasonicSensor):
    _attr_name = "Grid Power Sold"
    _attr_unique_id = "panasonic_bt3802_grid_power_sold"

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get("grid_power_sold_kw")
