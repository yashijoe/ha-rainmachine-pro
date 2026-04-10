"""Select platform for RainMachine Pro."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)

# Supported freeze protection temperatures in °C
_FREEZE_TEMPS = [str(t) for t in range(-7, 5)]  # -7 to 4 inclusive


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RainMachineFreezeProtectionTemp(coordinator, entry)])


class RainMachineFreezeProtectionTemp(RainMachineBaseEntity, SelectEntity):
    """Select entity for freeze protection temperature."""

    _attr_name = "Freeze protection temperature"
    _attr_icon = "mdi:thermometer-snowflake"
    _attr_options = _FREEZE_TEMPS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_freeze_protection_temperature"

    @property
    def current_option(self) -> str | None:
        """Return current freeze protection temperature."""
        temp = self.coordinator.data.get("restrictions_global", {}).get("freezeProtectTemp")
        if temp is None:
            return None
        val = str(int(temp))
        return val if val in _FREEZE_TEMPS else None

    async def async_select_option(self, option: str) -> None:
        """Set freeze protection temperature."""
        try:
            await self.coordinator.client.action_set_global_restriction(
                {"freezeProtectTemp": int(option)}
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set freeze protection temperature: %s", err)
