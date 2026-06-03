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
        "daily": "Täglich",
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
        "every_n": "Cada {n} días",
        "odd": "Días impares",
        "even": "Días pares",
        "days": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
    },
}

_DURATION_TYPE_LABELS = {
    "en": {"suggested": "suggested", "custom": "custom", "not_set": "not set"},
    "it": {"suggested": "suggerita", "custom": "personalizzata", "not_set": "non impostata"},
    "de": {"suggested": "vorgeschlagen", "custom": "benutzerdefiniert", "not_set": "nicht gesetzt"},
    "fr": {"suggested": "suggérée", "custom": "personnalisée", "not_set": "non définie"},
    "es": {"suggested": "sugerida", "custom": "personalizada", "not_set": "no definida"},
}

_DAY_POS = [8, 7, 6, 5, 4, 3, 2]
_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _param_to_days(param) -> list:
    s = str(param).zfill(10)
    return [s[pos] == '1' for pos in _DAY_POS]


def _days_to_param(days: list) -> str:
    chars = ['0'] * 10
    for i, active in enumerate(days):
        chars[_DAY_POS[i]] = '1' if active else '0'
    return ''.join(chars)


def _next_run_with_time(prog: dict) -> str | None:
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
        days = _param_to_days(param)
        day_names = t["days"]
        active = [day_names[i] for i, on in enumerate(days) if on]
        return ", ".join(active) or "Custom"
    return f"type={ftype} param={param}"


def _zone_planned_seconds(wt: dict, zone_properties: dict) -> int:
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
        if not prog_cfg.get("enabled", True):
            continue

        entities.append(RainMachineProgramRunSwitch(fast_coordinator, coordinator, entry, pid, name))
        entities.append(RainMachineProgramEnabledSwitch(coordinator, entry, pid, name))

        freq_key = f"{entry.entry_id}_prog_freq_{pid}"
        if freq_key not in hass.data[DOMAIN]:
            freq_state = {"interval": 2, "days": [True] * 7}
            freq = program.get("frequency", {})
            ftype = int(freq.get("type", 0))
            if ftype == 1:
                try:
                    freq_state["interval"] = int(freq.get("param", 2))
                except (ValueError, TypeError):
                    pass
            elif ftype == 2:
                freq_state["days"] = _param_to_days(freq.get("param", "0000000000"))
            hass.data[DOMAIN][freq_key] = freq_state
        else:
            freq_state = hass.data[DOMAIN][freq_key]

        for day_idx in range(7):
            entities.append(
                RainMachineProgramFrequencyDaySwitch(
                    fast_coordinator, entry, pid, name, day_idx, freq_state
                )
            )

        entities.append(RainMachineProgramWeatherAdaptiveSwitch(fast_coordinator, entry, pid, name))
        entities.append(RainMachineProgramAdaptiveFrequencySwitch(fast_coordinator, entry, pid, name))

    entities.append(RainMachineFreezeProtectionSwitch(coordinator, entry))
    entities.append(RainMachineExtraWaterSwitch(coordinator, entry))

    async_add_entities(entities)


class RainMachineZoneRunSwitch(RainMachineBaseEntity, SwitchEntity):
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
            for prog in self.coordinator.data.get("programs", []):
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


class RainMachineProgramRunSwitch(RainMachineBaseEntity, SwitchEntity):
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
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                return prog.get("status", 0) == 1
        return False

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}
        lang = self._get_lang()
        type_labels = _DURATION_TYPE_LABELS.get(lang, _DURATION_TYPE_LABELS["en"])
        zones_cfg = self._entry.options.get(CONF_ZONES, {})
        zone_properties = self._slow_coordinator.data.get("zone_properties", {})

        for prog in self.coordinator.data.get("programs", []):
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
                zid = wt["id"]
                if not zones_cfg.get(str(zid), {}).get("enabled", False):
                    continue
                zone_active = wt.get("active", False)
                ha_name = zones_cfg.get(str(zid), {}).get("name") or wt.get("name", f"Zone {zid}")
                fixed_dur = wt.get("duration", 0)
                if not zone_active:
                    duration_type = "not_set"
                    seconds = 0
                elif fixed_dur > 0:
                    duration_type = "custom"
                    seconds = fixed_dur
                else:
                    duration_type = "suggested"
                    seconds = _zone_planned_seconds(wt, zone_properties)
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


class RainMachineProgramFrequencyDaySwitch(RainMachineBaseEntity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:calendar-today"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, entry, pid: int, program_name: str, day_idx: int, freq_state: dict
    ) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._day_idx = day_idx
        self._freq_state = freq_state
        self._attr_name = f"{program_name} frequency {_DAY_NAMES[day_idx]}"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_frequency_day_{day_idx}"

    def _get_program(self) -> dict | None:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                return prog
        return None

    @property
    def is_on(self) -> bool:
        prog = self._get_program()
        if prog and int(prog.get("frequency", {}).get("type", -1)) == 2:
            return _param_to_days(prog["frequency"].get("param", "0000000000"))[self._day_idx]
        return self._freq_state["days"][self._day_idx]

    async def async_turn_on(self, **kwargs) -> None:
        prog = self._get_program()
        if prog and int(prog.get("frequency", {}).get("type", -1)) == 2:
            days = _param_to_days(prog["frequency"].get("param", "0000000000"))
            days[self._day_idx] = True
            try:
                await self.coordinator.client.action_set_program_frequency(
                    self._pid, {"type": 2, "param": _days_to_param(days)}
                )
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.error("Failed to set frequency day for program %s: %s", self._pid, err)
        else:
            self._freq_state["days"][self._day_idx] = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        prog = self._get_program()
        if prog and int(prog.get("frequency", {}).get("type", -1)) == 2:
            days = _param_to_days(prog["frequency"].get("param", "0000000000"))
            days[self._day_idx] = False
            try:
                await self.coordinator.client.action_set_program_frequency(
                    self._pid, {"type": 2, "param": _days_to_param(days)}
                )
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.error("Failed to set frequency day for program %s: %s", self._pid, err)
        else:
            self._freq_state["days"][self._day_idx] = False
            self.async_write_ha_state()


class RainMachineProgramWeatherAdaptiveSwitch(RainMachineBaseEntity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:weather-cloudy"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._attr_name = f"{program_name} weather adaptive watering"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_weather_adaptive"

    @property
    def is_on(self) -> bool:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                return not prog.get("ignoreInternetWeather", False)
        return False

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_program_ignore_weather(self._pid, False)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable weather adaptive watering for program %s: %s", self._pid, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_program_ignore_weather(self._pid, True)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable weather adaptive watering for program %s: %s", self._pid, err)


class RainMachineProgramAdaptiveFrequencySwitch(RainMachineBaseEntity, SwitchEntity):
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:chart-timeline-variant"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._attr_name = f"{program_name} use adaptive frequency"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_adaptive_frequency"

    @property
    def is_on(self) -> bool:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                return prog.get("freq_modified", 0) > 0
        return False

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_program_freq_modified(self._pid, 50)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to enable adaptive frequency for program %s: %s", self._pid, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.client.action_set_program_freq_modified(self._pid, 0)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to disable adaptive frequency for program %s: %s", self._pid, err)


class RainMachineFreezeProtectionSwitch(RainMachineBaseEntity, SwitchEntity):
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
