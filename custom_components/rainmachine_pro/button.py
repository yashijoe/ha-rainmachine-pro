"""Button platform for RainMachine Pro."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PROGRAMS
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
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})

    entities = [RainMachineRebootButton(coordinator, entry)]

    for program in fast_coordinator.data.get("programs", []):
        pid = program["uid"]
        prog_cfg = enabled_programs.get(str(pid), {})
        if not prog_cfg.get("enabled", True):
            continue
        name = prog_cfg.get("name") or program.get("name", f"Program {pid}")
        entities.append(RainMachineProgramIncreaseButton(fast_coordinator, coordinator, entry, pid, name))
        entities.append(RainMachineProgramDecreaseButton(fast_coordinator, coordinator, entry, pid, name))

    async_add_entities(entities)


class RainMachineRebootButton(RainMachineBaseEntity, ButtonEntity):
    """Button to reboot the RainMachine controller."""

    _attr_name = "Reboot"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reboot"

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.action_reboot()
            _LOGGER.info("RainMachine reboot initiated")
        except Exception as err:
            _LOGGER.error("Failed to reboot RainMachine: %s", err)


class RainMachineProgramIncreaseButton(RainMachineBaseEntity, ButtonEntity):
    """Button to increase all active zone durations by 5% of WaterSense referenceTime."""

    _attr_icon = "mdi:plus-circle-outline"

    def __init__(self, coordinator, slow_coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._slow_coordinator = slow_coordinator
        self._attr_name = f"{program_name} increase duration"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_increase_duration"

    async def async_press(self) -> None:
        zone_properties = self._slow_coordinator.data.get("zone_properties", {})
        try:
            await self.coordinator.client.action_adjust_program_durations(self._pid, +1, zone_properties)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to increase program %s duration: %s", self._pid, err)


class RainMachineProgramDecreaseButton(RainMachineBaseEntity, ButtonEntity):
    """Button to decrease all active zone durations by 5% of WaterSense referenceTime."""

    _attr_icon = "mdi:minus-circle-outline"

    def __init__(self, coordinator, slow_coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._slow_coordinator = slow_coordinator
        self._attr_name = f"{program_name} decrease duration"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_decrease_duration"

    async def async_press(self) -> None:
        zone_properties = self._slow_coordinator.data.get("zone_properties", {})
        try:
            await self.coordinator.client.action_adjust_program_durations(self._pid, -1, zone_properties)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to decrease program %s duration: %s", self._pid, err)
