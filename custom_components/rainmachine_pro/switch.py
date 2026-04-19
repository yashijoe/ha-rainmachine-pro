"""Switch platform for RainMachine Pro."""

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PROGRAMS, CONF_ZONES
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)

_DEFAULT_ZONE_DURATION = 600  # 10 minutes

_FREQUENCY_LABELS = {
    "en": {
        "daily": "Daily",
        "every_n": "Every {n} days",
        "odd": "Odd days",
        "even": "Even days",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    },
    "it": {
        "daily": "Ogni giorno",
        "every_n": "Ogni {n} giorni",
        "odd": "Giorni dispari",
        "even": "Giorni pari",
        "days": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
    },
    "de": {
        "daily": "T\u00e4glich",
        "every_n": "Alle {n} Tage",
        "odd": "Ungerade Tage",
        "even": "Gerade Tage",
        "days": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    },
    "fr": {
        "daily": "Quotidien",
        "every_n": "Tous les {n} jours",
        "odd": "Jours impairs",
        "even": "Jours pairs",
        "days": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
    },
    "es": {
        "daily": "Diario",
        "every_n": "Cada {n} d\u00edas",
        "odd": "D\u00edas impares",
        "even": "D\u00edas pares",
        "days": ["Lun", "Mar", "Mi\u00e9", "Jue", "Vie", "S\u00e1b", "Dom"],
    },
}

_DURATION_TYPE_LABELS = {
    "en": {"suggested": "suggested", "fixed": "fixed"},
    "it": {"suggested": "suggerito", "fixed": "fisso"},
    "de": {"suggested": "vorgeschlagen", "fixed": "fest"},
    "fr": {"suggested": "sugg\u00e9r\u00e9", "fixed": "fixe"},
    "es": {"suggested": "sugerido", "fixed": "fijo"},
}


def _next_run_with_time(prog: dict) -> str | None:
    """Combine program nextRun date with startTime."""
    next_run = prog.get("nextRun")
    if not next_run:
        return None
    start_time = prog.get("startTime")
    if start_time is None:
        return next_run
    try:
        minutes = int(start_time)
        h, m = divmod(minutes, 60)
        return f"{next_run} {h:02d}:{m:02d}"
    except (TypeError, ValueError):
        if isinstance(start_time, str) and ":" in start_time:
            return f"{next_run} {start_time}"
        return next_run


def _frequency_label(freq: dict, lang: str = "en") -> str:
    """Return a translated human-readable label for a program frequency."""
    t = _FREQUENCY_LABELS.get(lang, _FREQUENCY_LABELS["en"])
    ftype = int(freq.get("type", 0))
    param = freq.get("param", "0")
    if ftype == 0:
        return t["daily"]
    if ftype == 1:
        try:
            return t["every_n"].format(n=int(param))
        except (ValueError, TypeError):
            return t["every_n"].format(n=param)
    if ftype == 4:
        return t["odd"] if str(param) == "1" else t["even"]
    if ftype == 2:
        day_order = {8: 0, 7: 1, 6: 2, 5: 3, 4: 4, 3: 5, 2: 6}
        s = str(param)
        active_indices = sorted(
            (day_order[i] for i, c in enumerate(s) if c == "1" and i in day_order)
        )
        day_names = t["days"]
        return ", ".join(day_names[idx] for idx in active_indices) or "Custom"
    return f"type={ftype} param={param}"


def _zone_planned_seconds(wt: dict, zone_properties: dict) -> int:
    """Return planned duration in seconds for a wateringTime entry."""
    fixed_dur = wt.get("duration", 0)
    if fixed_dur > 0:
        return fixed_dur
    zid = wt["id"]
    zprops = zone_properties.get(zid, {})
    ref_time = zprops.get("waterSense", {}).get("referenceTime", 0)
    if ref_time > 0:
        return int(ref_time * wt.get("userPercentage", 1.0))
    return 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    entities: list[SwitchEntity] = []

    zones_config = entry.options.get(CONF_ZONES, {})
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})

    for zone in fast_coordinator.data.get("zones", []):
        uid = zone["uid"]
        zone_cfg = zones_config.get(str(uid), {})
        if not zone_cfg.get("enabled", False):
            continue
        name = zone_cfg.get("name") or zone.get("name", f"Zone {uid}")
        entities.append(RainMachineZoneRunSwitch(fast_coordinator, coordinator, entry, uid, name))
        entities.append(RainMachineZoneEnabledSwitch(coordinator, entry, uid, name))

    for program in fast_coordinator.data.get("programs", []):
        pid = program["uid"]
        name = program.get("name", f"Program {pid}")
        prog_cfg = enabled_programs.get(str(pid), {})
        if prog_cfg.get("enabled", True):
            entities.append(RainMachineProgramRunSwitch(fast_coordinator, coordinator, entry, pid, name))
            entities.append(RainMachineProgramEnabledSwitch(coordinator, entry, pid, name))

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
        for item in self.coordinator.data.get("queue", []):
            if item.get("zid") == self._uid and item.get("running"):
                return True
        return False

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}

        next_run_found = False
        for item in self.coordinator.data.get("queue", []):
            if item.get("zid") == self._uid and not item.get("running"):
                attrs["next_run"] = item.get("startTime") or item.get("eta")
                next_run_found = True
                break

        if not next_run_found:
            candidates = []
            for prog in self._slow_coordinator.data.get("programs", []):
                if not prog.get("active"):
                    continue
                for pz in prog.get("zones", []):
                    if pz.get("uid") == self._uid:
                        nr = _next_run_with_time(prog)
                        if nr:
                            candidates.append(nr)
                        break
            if candidates:
                attrs["next_run"] = min(candidates)

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
        try:
            await self.coordinator.client.action_start_zone(self._uid, _DEFAULT_ZONE_DURATION)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start zone %s: %s", self._uid, err)

    async def async_turn_off(self, **kwargs) -> None:
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
        for item in self.coordinator.data.get("queue", []):
            if item.get("pid") == self._pid and item.get("running"):
                return True
        return False

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}
        lang = self._get_lang()
        type_labels = _DURATION_TYPE_LABELS.get(lang, _DURATION_TYPE_LABELS["en"])
        zones_cfg = self._entry.options.get(CONF_ZONES, {})
        zone_properties = self._slow_coordinator.data.get("zone_properties", {})

        for prog in self._slow_coordinator.data.get("programs", []):
            if prog["uid"] != self._pid:
                continue

            attrs["enabled"] = "on" if prog.get("active", False) else "off"

            next_run = _next_run_with_time(prog)
            last_run = prog.get("lastRun")
            start_time = prog.get("startTime")
            freq = prog.get("frequency")
            if next_run:
                attrs["next_run"] = next_run
            if last_run:
                attrs["last_run"] = last_run
            if start_time:
                attrs["start_time"] = start_time
            if freq is not None:
                attrs["frequency"] = _frequency_label(freq, lang)

            total_duration = 0
            for wt in prog.get("wateringTimes", []):
                if not wt.get("active", False):
                    continue
                zid = wt["id"]
                ha_name = zones_cfg.get(str(zid), {}).get("name") or wt.get("name", f"Zone {zid}")
                seconds = _zone_planned_seconds(wt, zone_properties)
                duration_type = "fixed" if wt.get("duration", 0) > 0 else "suggested"
                attrs[ha_name] = seconds
                attrs[f"{ha_name}_type"] = type_labels[duration_type]
                total_duration += seconds

            if total_duration > 0:
                attrs["total_duration"] = total_duration
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
            await self.coordinator.client.action_set_global_restriction({"freezeProtectEnabled": True})
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable freeze protection: %s", err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_global_restriction({"freezeProtectEnabled": False})
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
            await self.coordinator.client.action_set_global_restriction({"hotDaysExtraWatering": True})
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable extra water on hot days: %s", err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_global_restriction({"hotDaysExtraWatering": False})
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable extra water on hot days: %s", err)
