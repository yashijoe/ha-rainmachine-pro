"""Number platform for RainMachine Pro - Rain Delay control."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RainMachineProCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RainMachineRainDelayNumber(coordinator, entry)])


class RainMachineRainDelayNumber(CoordinatorEntity, NumberEntity):
    """Number entity for setting rain delay days."""

    _attr_has_entity_name = True
    _attr_name = "Rain delay days"
    _attr_icon = "mdi:weather-rainy"
    _attr_native_min_value = 0
    _attr_native_max_value = 14
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "days"

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry):
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rain_delay_days"
        self._value = 0

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
        }

    @property
    def native_value(self):
        """Return current value."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set rain delay and apply immediately."""
        days = int(value)
        self._value = days
        self.async_write_ha_state()

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await self.coordinator.client.authenticate(session)
                await self.coordinator.client.set_rain_delay(session, days)
            _LOGGER.info("Rain delay set to %d days", days)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set rain delay: %s", err)
