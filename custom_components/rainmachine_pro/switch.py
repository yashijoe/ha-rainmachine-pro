"""Switch platform for RainMachine Pro."""

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PROGRAMS
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
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    entities: list[SwitchEntity] = []

    enabled_programs = entry.options.get(CONF_PROGRAMS, {})

    # Zone switches — run uses fast coordinator, enabled uses slow
    for zone in fast_coordinator.data.get("zones", []):
        uid = zone["uid"]
        name = zone.get("name", f"Zone {uid}")
        entities.append(RainMachineZoneRunSwitch(fast_coordinator, coordinator, entry, uid, name))
        entities.append(RainMachineZoneEnabledSwitch(coordinator, entry, uid, name))

    # Program switches — filtered by enabled programs, run uses fast coordinator, enabled uses slow
    for program in fast_coordinator.data.get("programs", []):
        pid = program["uid"]
        name = program.get("name", f"Program {pid}")
        prog_cfg = enabled_programs.get(str(pid), {})
        if prog_cfg.get("enabled", True):
            entities.append(RainMachineProgramRunSwitch(fast_coordinator, coordinator, entry, pid, name))
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

    def __init__(self, coordinator, slow_coordinator, entry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator, entry)
        self._uid = uid
        self._slow_coordinator = slow_coordinator
        self._attr_name = zone_name
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_run"

    @property
    def is_on(self) -> bool:
        """Return True if zone is currently running (check queue)."""
        for item in self.coordinator.data.get("queue", []):
            if item.get("zid") == self._uid and item.get("running"):
                return True
        return False

    @property
    def extra_state_attributes(self) -> dict:
        """Return last_run and next_run attributes."""
        attrs = {}

        # next_run: first scheduled (not yet running) queue item for this zone
        for item in self.coordinator.data.get("queue", []):
            if item.get("zid") == self._uid and not item.get("running"):
                attrs["next_run"] = item.get("startTime") or item.get("eta")
                break

        # last_run: from slow coordinator watering details
        try:
            details = self._slow_coordinator.data.get("details", {})
            days = details.get("waterLog", {}).get("days", [])
            if days:
                for prog in days[0].get("programs", []):
                    for zone in prog.get("zones", []):
                        if zone.get("uid") == self._uid:
                            cycle = zone.get("cycles", [{}])[0]
                            start = cycle.get("startTime")
                            real_dur = int(cycle.get("realDuration", 0))
                            if start:
                                attrs["last_run_start"] = start
                            if start and real_dur:
                                from datetime import datetime, timedelta
                                try:
                                    dt = datetime.fromisoformat(start)
                                    attrs["last_run_end"] = (dt + timedelta(seconds=real_dur)).isoformat()
                                except (ValueError, TypeError):
                                    pass
                            break
        except Exception:
            pass

        return attrs

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
    _attr_entity_category = EntityCategory.CONFIG

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

    def __init__(self, coordinator, slow_coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._slow_coordinator = slow_coordinator
        self._attr_name = program_name
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_run"

    @property
    def is_on(self) -> bool:
        """Return True if program is currently running (check queue)."""
        for item in self.coordinator.data.get("queue", []):
            if item.get("pid") == self._pid and item.get("running"):
                return True
        return False

    @property
    def extra_state_attributes(self) -> dict:
        """Return last_run and next_run from program data."""
        attrs = {}
        for prog in self._slow_coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                next_run = prog.get("nextRun")
                last_run = prog.get("lastRun")
                if next_run:
                    attrs["next_run"] = next_run
                if last_run:
                    attrs["last_run"] = last_run
                break
        return attrs

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
    _attr_entity_category = EntityCategory.CONFIG

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
    _attr_entity_category = EntityCategory.CONFIG

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
    _attr_entity_category = EntityCategory.CONFIG

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
