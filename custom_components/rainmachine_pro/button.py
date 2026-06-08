"""Button platform for RainMachine Pro."""

import logging
from datetime import datetime, timedelta

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PROGRAMS, CONF_ZONES
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})
    zones_config = entry.options.get(CONF_ZONES, {})

    entities = [
        RainMachineRebootButton(coordinator, entry),
        RainMachinePauseButton(coordinator, entry),
    ]

    # Per-zone: manual start + ET coefficient apply
    for uid_str, zone_cfg in zones_config.items():
        if not zone_cfg.get("enabled", False):
            continue
        uid = int(uid_str)
        zone_name = zone_cfg.get("name") or f"Zone {uid}"
        entities.append(RainMachineZoneStartButton(coordinator, entry, uid, zone_name))
        entities.append(RainMachineZoneApplyETCoefButton(coordinator, entry, uid, zone_name))

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


class RainMachinePauseButton(RainMachineBaseEntity, ButtonEntity):
    _attr_name = "Pause watering"
    _attr_icon = "mdi:pause-circle"

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_pause_watering"

    async def async_press(self) -> None:
        duration_min = float(
            self.hass.data[DOMAIN].get(f"{self._entry.entry_id}_pause_duration_min", 0.0)
        )
        duration_sec = int(duration_min * 60)
        try:
            await self.coordinator.client.action_pause_watering(duration_sec)
            if duration_sec > 0:
                end_time = datetime.now().astimezone() + timedelta(seconds=duration_sec)
                self.hass.data[DOMAIN][f"{self._entry.entry_id}_pause_end_time"] = end_time
                _LOGGER.info("Watering paused for %d seconds", duration_sec)
            else:
                self.hass.data[DOMAIN][f"{self._entry.entry_id}_pause_end_time"] = None
                _LOGGER.info("Watering pause cancelled")
            fast_coord = self.hass.data[DOMAIN].get(f"{self._entry.entry_id}_fast")
            if fast_coord:
                await fast_coord.async_request_refresh()
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to pause watering: %s", err)


class RainMachineZoneStartButton(RainMachineBaseEntity, ButtonEntity):
    _attr_icon = "mdi:play-circle"

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator, entry)
        self._uid = uid
        self._attr_name = f"{zone_name} start manual"
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_start_manual"

    async def async_press(self) -> None:
        duration_min = float(
            self.hass.data[DOMAIN].get(
                f"{self._entry.entry_id}_zone_{self._uid}_manual_duration", 10.0
            )
        )
        duration_sec = int(duration_min * 60)
        try:
            await self.coordinator.client.action_start_zone(self._uid, duration_sec)
            fast_coord = self.hass.data[DOMAIN].get(f"{self._entry.entry_id}_fast")
            if fast_coord:
                await fast_coord.async_request_refresh()
            _LOGGER.info("Zone %s manual start for %d seconds", self._uid, duration_sec)
        except Exception as err:
            _LOGGER.error("Failed to start zone %s: %s", self._uid, err)


class RainMachineZoneApplyETCoefButton(RainMachineBaseEntity, ButtonEntity):
    """Button to write the pending ET coefficient value to the device."""

    _attr_icon = "mdi:check-circle-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator, entry)
        self._uid = uid
        self._attr_name = f"{zone_name} apply ET coefficient"
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_apply_et_coef"

    async def async_press(self) -> None:
        pending_key = f"{self._entry.entry_id}_zone_{self._uid}_et_coef_pending"
        value = self.hass.data[DOMAIN].get(pending_key)
        if value is None:
            props = self.coordinator.data.get("zone_properties", {}).get(self._uid, {})
            value = props.get("ETcoef")
        if value is None:
            _LOGGER.warning("No ET coefficient available for zone %s", self._uid)
            return
        try:
            await self.coordinator.client.action_set_zone_et_coef(self._uid, float(value))
            self.hass.data[DOMAIN][pending_key] = None
            await self.coordinator.async_request_refresh()
            _LOGGER.info("ET coefficient for zone %s set to %s", self._uid, value)
        except Exception as err:
            _LOGGER.error("Failed to apply ET coefficient for zone %s: %s", self._uid, err)


class RainMachineProgramIncreaseButton(RainMachineBaseEntity, ButtonEntity):
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
