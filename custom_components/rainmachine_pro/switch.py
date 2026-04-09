"""Switch platform for RainMachine Pro."""

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)

# Default duration (seconds) when starting a zone manually
_DEFAULT_ZONE_DURATION = 600  # 10 minutes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SwitchEntity] = []

    # Zone switches — one pair per zone from the API
    for zone in coordinator.data.get("zones", []):
        uid = zone["uid"]
        name = zone.get("name", f"Zone {uid}")
        entities.append(RainMachineZoneRunSwitch(coordinator, entry, uid, name))
        entities.append(RainMachineZoneEnabledSwitch(coordinator, entry, uid, name))

    # Program switches — one pair per program
    for program in coordinator.data.get("programs", []):
        pid = program["uid"]
        name = program.get("name", f"Program {pid}")
        entities.append(RainMachineProgramRunSwitch(coordinator, entry, pid, name))
        entities.append(RainMachineProgramEnabledSwitch(coordinator, entry, pid, name))

    # Global switches
    entities.append(RainMachineFreezeProtectionSwitch(coordinator, entry))
    entities.append(RainMachineExtraWaterSwitch(coordinator, entry))

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# Zone switches
# ---------------------------------------------------------------------------

class RainMachineZoneRunSwitch(RainMachineBaseEntity, SwitchEntity):
    """Switch to start/stop a zone."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:water"

    def __init__(self, coordinator, entry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator, entry)
        self._uid = uid
        self._attr_name = zone_name
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_run"

    @property
    def is_on(self) -> bool:
        """Return True if zone is currently running."""
        for zone in self.coordinator.data.get("zones", []):
            if zone["uid"] == self._uid:
                return zone.get("state", 0) != 0
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Start zone irrigation."""
        try:
            await self.coordinator.client.action_start_zone(self._uid, _DEFAULT_ZONE_DURATION)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start zone %s: %s", self._uid, err)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop zone irrigation."""
        try:
            await self.coordinator.client.action_stop_zone(self._uid)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop zone %s: %s", self._uid, err)


class RainMachineZoneEnabledSwitch(RainMachineBaseEntity, SwitchEntity):
    """Switch to enable/disable a zone."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:cog"
    _attr_entity_category = "config"

    def __init__(self, coordinator, entry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator, entry)
        self._uid = uid
        self._attr_name = f"{zone_name} enabled"
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_enabled"

    @property
    def is_on(self) -> bool:
        """Return True if zone is active/enabled."""
        for zone in self.coordinator.data.get("zones", []):
            if zone["uid"] == self._uid:
                return zone.get("active", False)
        return False

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_zone_active(self._uid, True)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable zone %s: %s", self._uid, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_zone_active(self._uid, False)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable zone %s: %s", self._uid, err)


# ---------------------------------------------------------------------------
# Program switches
# ---------------------------------------------------------------------------

class RainMachineProgramRunSwitch(RainMachineBaseEntity, SwitchEntity):
    """Switch to start/stop a program."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:water-outline"

    def __init__(self, coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._attr_name = program_name
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_run"

    @property
    def is_on(self) -> bool:
        """Return True if program is currently running."""
        for program in self.coordinator.data.get("programs", []):
            if program["uid"] == self._pid:
                return program.get("status", 0) != 0
        return False

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_start_program(self._pid)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start program %s: %s", self._pid, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_stop_program(self._pid)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop program %s: %s", self._pid, err)


class RainMachineProgramEnabledSwitch(RainMachineBaseEntity, SwitchEntity):
    """Switch to enable/disable a program."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:cog"
    _attr_entity_category = "config"

    def __init__(self, coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._attr_name = f"{program_name} enabled"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_enabled"

    @property
    def is_on(self) -> bool:
        for program in self.coordinator.data.get("programs", []):
            if program["uid"] == self._pid:
                return program.get("active", False)
        return False

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_program_active(self._pid, True)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable program %s: %s", self._pid, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_program_active(self._pid, False)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable program %s: %s", self._pid, err)


# ---------------------------------------------------------------------------
# Global switches
# ---------------------------------------------------------------------------

class RainMachineFreezeProtectionSwitch(RainMachineBaseEntity, SwitchEntity):
    """Switch for freeze protection."""

    _attr_name = "Freeze protection"
    _attr_icon = "mdi:snowflake"
    _attr_entity_category = "config"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_freeze_protection"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("restrictions_global", {}).get(
            "freezeProtectEnabled", False
        )

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_global_restriction(
                {"freezeProtectEnabled": True}
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable freeze protection: %s", err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_global_restriction(
                {"freezeProtectEnabled": False}
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable freeze protection: %s", err)


class RainMachineExtraWaterSwitch(RainMachineBaseEntity, SwitchEntity):
    """Switch for extra water on hot days."""

    _attr_name = "Extra water on hot days"
    _attr_icon = "mdi:thermometer-water"
    _attr_entity_category = "config"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_extra_water_hot_days"

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("restrictions_global", {}).get(
            "hotDaysExtraWatering", False
        )

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_global_restriction(
                {"hotDaysExtraWatering": True}
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable extra water on hot days: %s", err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_global_restriction(
                {"hotDaysExtraWatering": False}
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable extra water on hot days: %s", err)
