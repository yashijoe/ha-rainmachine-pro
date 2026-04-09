"""Button platform for RainMachine Pro."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RainMachineRebootButton(coordinator, entry)])


class RainMachineRebootButton(RainMachineBaseEntity, ButtonEntity):
    """Button to reboot the RainMachine controller."""

    _attr_name = "Reboot"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reboot"

    async def async_press(self) -> None:
        """Reboot the controller."""
        try:
            await self.coordinator.client.action_reboot()
            _LOGGER.info("RainMachine reboot initiated")
        except Exception as err:
            _LOGGER.error("Failed to reboot RainMachine: %s", err)
