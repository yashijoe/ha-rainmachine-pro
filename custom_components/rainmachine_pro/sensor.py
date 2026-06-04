"""Sensor platform for RainMachine Pro."""

import logging
import re
from datetime import datetime, timedelta, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_ZONES,
    CONF_PROGRAMS,
    CONF_PARSERS,
    FLAG_MAP,
    WEATHER_CONDITIONS,
    WEATHER_CONDITIONS_TRANSLATED,
    WEATHER_ICONS,
)
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)

_DURATION_TYPE_LABELS = {
    "en": {"suggested": "suggested", "custom": "custom", "not_set": "not set"},
    "it": {"suggested": "suggerita", "custom": "personalizzata", "not_set": "non impostata"},
    "de": {"suggested": "vorgeschlagen", "custom": "benutzerdefiniert", "not_set": "nicht gesetzt"},
    "fr": {"suggested": "suggérée", "custom": "personnalisée", "not_set": "non définie"},
    "es": {"suggested": "sugerida", "custom": "personalizada", "not_set": "no definida"},
}


def _seconds_to_mmss(seconds: int) -> str:
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"


def _sum_details_today(data: dict, field: str) -> int:
    """Sum a cycle field across all programs/zones/cycles for today."""
    days = data.get("details", {}).get("waterLog", {}).get("days", [])
    today_str = datetime.now().strftime("%Y-%m-%d")
    for day in days:
        if day.get("date") == today_str:
            total = 0
            for prog in day.get("programs", []):
                for zone in prog.get("zones", []):
                    for cycle in zone.get("cycles", []):
                        total += int(cycle.get(field, 0))
            return total
    return 0


def _day_label(lang: str, delta: int) -> str:
    relative_map = {
        "it": {-1: "Ieri", 0: "Oggi", 1: "Domani"},
        "de": {-1: "Gestern", 0: "Heute", 1: "Morgen"},
        "fr": {-1: "Hier", 0: "Aujourd'hui", 1: "Demain"},
        "es": {-1: "Ayer", 0: "Hoy", 1: "Mañana"},
        "en": {-1: "Yesterday", 0: "Today", 1: "Tomorrow"},
    }
    day_names_map = {
        "it": {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"},
        "de": {0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 4: "Freitag", 5: "Samstag", 6: "Sonntag"},
        "fr": {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"},
        "es": {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"},
        "en": {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"},
    }
    relatives = relative_map.get(lang, relative_map["en"])
    if delta in relatives:
        return relatives[delta]
    day_names = day_names_map.get(lang, day_names_map["en"])
    target = datetime.today().date() + timedelta(days=delta)
    return day_names.get(target.weekday(), str(target))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    zones = entry.options.get(CONF_ZONES, {})

    entities: list[SensorEntity] = []

    entities.append(RainMachineTodayWateringSensor(coordinator, entry))
    entities.append(RainMachineTodayScheduledWateringSensor(coordinator, entry))
    entities.append(RainMachineRainDelaySensor(coordinator, entry))

    for uid_str, zone_data in zones.items():
        if zone_data.get("enabled", False):
            entities.append(
                RainMachineZoneSensor(
                    coordinator, entry, int(uid_str),
                    zone_data.get("name", f"Zone {uid_str}")
                )
            )

    parsers_config = entry.options.get(CONF_PARSERS, {})
    if isinstance(parsers_config, list):
        parsers_config = {
            str(p["uid"]): {"description": p.get("description", ""), "enabled": True}
            for p in coordinator.data.get("parsers", [])
            if p.get("uid") and p.get("description")
        }
    for uid_str, parser_cfg in parsers_config.items():
        if not isinstance(parser_cfg, dict) or not parser_cfg.get("enabled", True):
            continue
        display_name = (
            parser_cfg.get("name")
            or parser_cfg.get("description", f"Parser {uid_str}")
        )
        entities.append(
            RainMachineParserSensor(coordinator, entry, int(uid_str), display_name)
        )

    for i in range(7):
        entities.append(RainMachineForecastSensor(coordinator, entry, i))

    # Irrigation forecast: 7 sensors per enabled program
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})
    for program in coordinator.data.get("programs", []):
        pid = program["uid"]
        prog_cfg = enabled_programs.get(str(pid), {})
        if not prog_cfg.get("enabled", True):
            continue
        prog_name = prog_cfg.get("name") or program.get("name", f"Program {pid}")
        for i in range(7):
            entities.append(
                RainMachineIrrigationForecastSensor(coordinator, entry, pid, prog_name, i)
            )

    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    enabled_zones_cfg = entry.options.get(CONF_ZONES, {})

    for zone in fast_coordinator.data.get("zones", []):
        uid = zone["uid"]
        zone_cfg = enabled_zones_cfg.get(str(uid), {})
        if not zone_cfg.get("enabled", False):
            continue
        name = zone_cfg.get("name") or zone.get("name", f"Zone {uid}")
        entities.append(
            RainMachineZoneRunCountdown(
                fast_coordinator, coordinator, entry, uid, name
            )
        )

    for program in fast_coordinator.data.get("programs", []):
        pid = program["uid"]
        prog_cfg = enabled_programs.get(str(pid), {})
        if not prog_cfg.get("enabled", True):
            continue
        name = prog_cfg.get("name") or program.get("name", f"Program {pid}")
        entities.append(
            RainMachineProgramRunCountdown(
                fast_coordinator, coordinator, entry, pid, name
            )
        )

    entities.append(RainMachinePauseCountdown(fast_coordinator, coordinator, entry))

    async_add_entities(entities)


class RainMachineTodayWateringSensor(RainMachineBaseEntity, SensorEntity):
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:sprinkler"
    _attr_name = "Today watering"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_today_watering"
        self.entity_id = "sensor.rainmachine_today_watering"

    @property
    def last_reset(self) -> datetime:
        now = datetime.now().astimezone()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    @property
    def native_value(self):
        return _sum_details_today(self.coordinator.data, "realDuration") // 60

    @property
    def extra_state_attributes(self):
        today_str = datetime.now().strftime("%Y-%m-%d")
        user_duration = _sum_details_today(self.coordinator.data, "userDuration")
        mins = user_duration // 60
        secs = user_duration % 60
        return {"date": today_str, "userDuration": f"{mins}:{secs:02d}"}


class RainMachineTodayScheduledWateringSensor(RainMachineBaseEntity, SensorEntity):
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:sprinkler-variant"
    _attr_name = "Today watering scheduled"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_today_watering_scheduled"
        self.entity_id = "sensor.rainmachine_today_watering_scheduled"

    @property
    def last_reset(self) -> datetime:
        now = datetime.now().astimezone()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    @property
    def native_value(self):
        return _sum_details_today(self.coordinator.data, "userDuration") // 60


class RainMachineRainDelaySensor(RainMachineBaseEntity, SensorEntity):
    _attr_icon = "mdi:timer-sand"
    _attr_name = "Rain delay"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_rain_delay"
        self.entity_id = "sensor.rainmachine_rain_delay"

    @property
    def native_value(self):
        rd = self.coordinator.data.get("raindelay", {})
        delay_sec = int(rd.get("delayCounter", -1))
        if delay_sec <= 0:
            delay_sec = 0
        days = delay_sec // 86400
        hours = (delay_sec % 86400) // 3600
        minutes = (delay_sec % 3600) // 60
        return f"{days} giorni {hours} ore {minutes} minuti"

    @property
    def icon(self):
        rd = self.coordinator.data.get("raindelay", {})
        delay_sec = int(rd.get("delayCounter", -1))
        return "mdi:timer-sand" if delay_sec > 0 else "mdi:timer-off"

    @property
    def extra_state_attributes(self):
        rd = self.coordinator.data.get("raindelay", {})
        delay_sec = int(rd.get("delayCounter", -1))
        if delay_sec <= 0:
            return {"seconds_remaining": 0, "minutes_remaining": 0, "hours_remaining": 0, "days_remaining": 0, "ends_at": None}
        days = delay_sec // 86400
        hours = (delay_sec % 86400) // 3600
        minutes = (delay_sec % 3600) // 60
        ends_at = (datetime.now() + timedelta(seconds=delay_sec)).strftime("%Y-%m-%d %H:%M:%S")
        return {"days_remaining": days, "hours_remaining": hours, "minutes_remaining": minutes, "seconds_remaining": delay_sec, "ends_at": ends_at}


class RainMachineZoneSensor(RainMachineBaseEntity, SensorEntity):
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator, entry, uid: int, zone_name: str):
        super().__init__(coordinator, entry)
        self._uid = uid
        self._zone_name = zone_name
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}"
        self._attr_name = zone_name
        self.entity_id = f"sensor.rainmachine_uid{uid}_watering"

    def _get_zone_data(self) -> dict | None:
        details = self.coordinator.data.get("details", {})
        all_days = details.get("waterLog", {}).get("days", [])
        if not all_days:
            return None
        for program in all_days[0].get("programs", []):
            for zone in program.get("zones", []):
                if zone.get("uid") == self._uid:
                    return zone
        return None

    def _get_program_durations(self) -> dict:
        lang = self._get_lang()
        type_labels = _DURATION_TYPE_LABELS.get(lang, _DURATION_TYPE_LABELS["en"])
        zone_properties = self.coordinator.data.get("zone_properties", {})
        zprops = zone_properties.get(self._uid, {})
        ref_time = zprops.get("waterSense", {}).get("referenceTime", 0)
        programs_cfg = self._entry.options.get(CONF_PROGRAMS, {})
        result = {}
        for prog in self.coordinator.data.get("programs", []):
            for wt in prog.get("wateringTimes", []):
                if wt.get("id") == self._uid:
                    zone_active = wt.get("active", False)
                    fixed_dur = wt.get("duration", 0)
                    if not zone_active:
                        seconds = 0
                        duration_type = "not_set"
                    elif fixed_dur > 0:
                        seconds = fixed_dur
                        duration_type = "custom"
                    else:
                        seconds = int(ref_time * wt.get("userPercentage", 1.0))
                        duration_type = "suggested"
                    ha_name = (programs_cfg.get(str(prog["uid"]), {}).get("name") or prog.get("name", f"Program {prog['uid']}"))
                    result[ha_name] = seconds
                    result[f"{ha_name}_type"] = type_labels[duration_type]
                    break
        return result

    @property
    def native_value(self):
        zone = self._get_zone_data()
        if not zone:
            return 0
        cycle = zone.get("cycles", [{}])[0]
        return int(cycle.get("realDuration", 0)) // 60

    @property
    def extra_state_attributes(self):
        lang = self._get_lang()
        flag_map = FLAG_MAP.get(lang, FLAG_MAP["en"])
        zone = self._get_zone_data()
        if not zone:
            attrs = {
                "userDuration": 0, "userDuration_unit": "min", "realDuration": 0, "realDuration_unit": "min",
                "userDuration_display": "0 min previsti" if lang == "it" else "0 min scheduled",
                "realDuration_display": "0 min effettivi" if lang == "it" else "0 min actual",
                "startTime": None, "flag": flag_map.get(-1, "No watering"), "icon": "mdi:sprinkler",
            }
        else:
            cycle = zone.get("cycles", [{}])[0]
            real_dur = int(cycle.get("realDuration", 0)) // 60
            user_dur = int(cycle.get("userDuration", 0)) // 60
            flag = zone.get("flag", -1)
            if lang == "it":
                user_label, real_label = "previsti", "effettivi"
            elif lang == "de":
                user_label, real_label = "geplant", "tatsächlich"
            elif lang == "fr":
                user_label, real_label = "prévus", "effectifs"
            elif lang == "es":
                user_label, real_label = "previstos", "efectivos"
            else:
                user_label, real_label = "scheduled", "actual"
            attrs = {
                "userDuration": user_dur, "userDuration_unit": "min", "realDuration": real_dur, "realDuration_unit": "min",
                "userDuration_display": f"{user_dur} min {user_label}", "realDuration_display": f"{real_dur} min {real_label}",
                "startTime": cycle.get("startTime"), "flag": flag_map.get(flag, flag_map.get(-1, "No watering")), "icon": "mdi:sprinkler",
            }
        attrs.update(self._get_program_durations())
        return attrs


class RainMachineParserSensor(RainMachineBaseEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry, uid: int, description: str):
        super().__init__(coordinator, entry)
        self._uid = uid
        self._description = description
        self._attr_unique_id = f"{entry.entry_id}_parser_{uid}"
        self._attr_name = description
        suffix = re.sub(r"[^a-z0-9]+", "_", description.lower()).strip("_")
        self.entity_id = f"sensor.rainmachine_{suffix}_last_run"

    def _find_parser(self) -> dict | None:
        for parser in self.coordinator.data.get("parsers", []):
            if parser.get("uid") == self._uid:
                return parser
        return None

    @property
    def native_value(self):
        parser = self._find_parser()
        if not parser:
            return None
        last_run = parser.get("lastRun")
        if not last_run or last_run == "unknown":
            return None
        try:
            import homeassistant.util.dt as dt_util
            dt = datetime.strptime(last_run, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        except (ValueError, TypeError):
            try:
                return datetime.fromisoformat(last_run)
            except (ValueError, TypeError):
                return None

    @property
    def extra_state_attributes(self):
        parser = self._find_parser()
        active = parser is not None and parser.get("lastRun") not in (None, "unknown")
        return {"active": active}

    @property
    def icon(self):
        forecast = self.coordinator.data.get("forecast", {})
        try:
            daily = forecast["mixerData"][0]["dailyValues"]
            today_str = datetime.now().strftime("%Y-%m-%d")
            for d in daily:
                if d["day"].startswith(today_str):
                    code = d["condition"]
                    condition = WEATHER_CONDITIONS.get(code, "unknown")
                    return WEATHER_ICONS.get(condition, "mdi:weather-cloudy-alert")
        except (KeyError, IndexError, TypeError):
            pass
        return "mdi:weather-cloudy-alert"


class RainMachineForecastSensor(RainMachineBaseEntity, SensorEntity):
    def __init__(self, coordinator, entry, index: int):
        super().__init__(coordinator, entry)
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_forecast_{index}"
        self.entity_id = f"sensor.rainmachine_forecast_condition_{index}"

    def _get_forecast_day(self) -> tuple[dict | None, int]:
        forecast = self.coordinator.data.get("forecast", {})
        try:
            daily_values = forecast["mixerData"][0]["dailyValues"]
        except (KeyError, IndexError, TypeError):
            return None, 0
        today = datetime.today().date()
        yesterday = today - timedelta(days=1)
        selected = []
        for daily in daily_values:
            day_date = datetime.strptime(daily["day"], "%Y-%m-%d %H:%M:%S").date()
            if yesterday <= day_date <= yesterday + timedelta(days=6):
                selected.append((day_date, daily))
        selected.sort(key=lambda x: x[0])
        if self._index < len(selected):
            day_date, data = selected[self._index]
            delta = (day_date - today).days
            return data, delta
        return None, 0

    @property
    def name(self):
        _, delta = self._get_forecast_day()
        return _day_label(self._get_lang(), delta)

    @property
    def native_value(self):
        data, _ = self._get_forecast_day()
        if not data:
            return "unknown"
        code = data.get("condition", -1)
        return WEATHER_CONDITIONS.get(code, "unknown")

    @property
    def icon(self):
        condition = self.native_value
        return WEATHER_ICONS.get(condition, "mdi:weather-cloudy-alert")

    @property
    def extra_state_attributes(self):
        data, delta = self._get_forecast_day()
        if not data:
            return {}
        lang = self._get_lang()
        code = data.get("condition", -1)
        condition = WEATHER_CONDITIONS.get(code, "unknown")
        conditions_translated = WEATHER_CONDITIONS_TRANSLATED.get(lang, WEATHER_CONDITIONS_TRANSLATED["en"])
        state_translated = conditions_translated.get(condition, conditions_translated.get("unknown", "Unknown"))
        rain_labels = {
            "it": {"rain": "di pioggia", "forecast": "di pioggia prevista"},
            "de": {"rain": "Regen", "forecast": "Regen vorhergesagt"},
            "fr": {"rain": "de pluie", "forecast": "de pluie prévue"},
            "es": {"rain": "de lluvia", "forecast": "de lluvia prevista"},
            "en": {"rain": "rain", "forecast": "rain forecast"},
        }
        labels = rain_labels.get(lang, rain_labels["en"])
        return {
            "temperature": int(data.get("temperature", 0)), "temperature_unit": "°C",
            "temperature_display": f"{int(data.get('temperature', 0))}°",
            "min_temperature": int(data.get("minTemp", 0)), "min_temperature_unit": "°C",
            "min_temperature_display": f"{int(data.get('minTemp', 0))}° min",
            "max_temperature": int(data.get("maxTemp", 0)), "max_temperature_unit": "°C",
            "max_temperature_display": f"{int(data.get('maxTemp', 0))}° max",
            "rain": data.get("rain", 0), "rain_unit": "mm",
            "rain_display": f"{data.get('rain', 0)} mm {labels['rain']}",
            "precipitation_forecast": data.get("qpf", 0), "precipitation_forecast_unit": "mm",
            "precipitation_forecast_display": f"{data.get('qpf', 0)} mm {labels['forecast']}",
            "EvapoTranspiration": data.get("et0final", 0), "EvapoTranspiration_unit": "mm",
            "EvapoTranspiration_display": f"{data.get('et0final', 0)} mm",
            "day": data.get("day", "").split(" ")[0], "meteocode": code,
            "friendly_name": _day_label(lang, delta), "state_translated": state_translated,
            "icon": f"mdi:weather-{condition}",
        }


class RainMachineIrrigationForecastSensor(RainMachineBaseEntity, SensorEntity):
    """Sensor: per-program irrigation forecast for a specific day (from dailystats/details)."""

    _attr_icon = "mdi:sprinkler"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, pid: int, program_name: str, index: int) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._program_name = program_name
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_irrigation_forecast_{index}"
        suffix = re.sub(r"[^a-z0-9]+", "_", program_name.lower()).strip("_")
        self.entity_id = f"sensor.rainmachine_{suffix}_irrigation_forecast_{index}"

    def _get_day_data(self) -> tuple[dict | None, int]:
        details = self.coordinator.data.get("dailystats_details", [])
        if not details or self._index >= len(details):
            return None, 0
        day = details[self._index]
        try:
            day_date = datetime.strptime(day["day"], "%Y-%m-%d").date()
            delta = (day_date - datetime.today().date()).days
        except (KeyError, ValueError):
            delta = self._index
        return day, delta

    def _get_zones(self, day: dict) -> list:
        for prog in day.get("programs", []):
            if prog.get("id") == self._pid:
                return prog.get("zones", [])
        return []

    @property
    def name(self) -> str:
        _, delta = self._get_day_data()
        return f"{self._program_name} {_day_label(self._get_lang(), delta)}"

    @property
    def native_value(self) -> float | None:
        day, _ = self._get_day_data()
        if day is None:
            return None
        zones = self._get_zones(day)
        if not zones:
            return None
        total_sec = sum(z.get("scheduledWateringTime", 0) for z in zones)
        return round(total_sec / 60, 1)

    @property
    def extra_state_attributes(self) -> dict:
        day, delta = self._get_day_data()
        if day is None:
            return {}
        zones = self._get_zones(day)
        zones_cfg = self._entry.options.get(CONF_ZONES, {})
        attrs = {
            "day": day.get("day"),
            "scheduled_min": round(sum(z.get("scheduledWateringTime", 0) for z in zones) / 60, 1),
            "computed_min": round(sum(z.get("computedWateringTime", 0) for z in zones) / 60, 1),
        }
        for z in zones:
            zid = z.get("id")
            z_name = zones_cfg.get(str(zid), {}).get("name") or f"Zone {zid}"
            attrs[f"{z_name}_scheduled_min"] = round(z.get("scheduledWateringTime", 0) / 60, 1)
            attrs[f"{z_name}_computed_min"] = round(z.get("computedWateringTime", 0) / 60, 1)
            attrs[f"{z_name}_available_water"] = round(z.get("availableWater", 0), 2)
            attrs[f"{z_name}_percentage"] = z.get("percentage", 0)
            attrs[f"{z_name}_watering_flag"] = z.get("wateringFlag")
        return attrs


# ---------------------------------------------------------------------------
# Run countdown sensors (second-by-second)
# ---------------------------------------------------------------------------

class RainMachineZoneRunCountdown(RainMachineBaseEntity, SensorEntity):
    """Sensor: remaining time for current zone run in M:SS format, updated every second."""

    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, slow_coordinator, entry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator, entry)
        self._uid = uid
        self._slow_coordinator = slow_coordinator
        self._attr_name = f"{zone_name} run countdown"
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_run_countdown"
        self._end_time: datetime | None = None
        self._unsub_timer = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_tick, timedelta(seconds=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _async_tick(self, now) -> None:
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        new_end_time = None
        for item in self.coordinator.data.get("queue", []):
            if item.get("zid") == self._uid and item.get("running"):
                remaining = item.get("remaining", 0)
                if remaining > 0:
                    new_end_time = datetime.now().astimezone() + timedelta(seconds=remaining)
                break
        if new_end_time is None:
            self._end_time = None
        elif self._end_time is None:
            self._end_time = new_end_time
        else:
            local_rem = (self._end_time - datetime.now().astimezone()).total_seconds()
            device_rem = (new_end_time - datetime.now().astimezone()).total_seconds()
            if abs(local_rem - device_rem) > 2:
                self._end_time = new_end_time
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | None:
        if self._end_time is None:
            return None
        remaining = (self._end_time - datetime.now().astimezone()).total_seconds()
        if remaining <= 0:
            self._end_time = None
            return None
        return _seconds_to_mmss(int(remaining))

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}
        if self._end_time is not None:
            remaining = (self._end_time - datetime.now().astimezone()).total_seconds()
            attrs["remaining_seconds"] = max(0, int(remaining))
        try:
            details = self._slow_coordinator.data.get("details", {})
            for day in details.get("waterLog", {}).get("days", []):
                for prog in day.get("programs", []):
                    for zone in prog.get("zones", []):
                        if zone.get("uid") == self._uid:
                            cycle = zone.get("cycles", [{}])[0]
                            start = cycle.get("startTime")
                            real_dur = int(cycle.get("realDuration", 0))
                            if start:
                                attrs["last_run_start"] = start
                            if start and real_dur:
                                try:
                                    dt = datetime.fromisoformat(start)
                                    attrs["last_run_end"] = (dt + timedelta(seconds=real_dur)).isoformat()
                                except (ValueError, TypeError):
                                    pass
                            break
        except Exception:
            pass
        return attrs


class RainMachineProgramRunCountdown(RainMachineBaseEntity, SensorEntity):
    """Sensor: total remaining time for current program run in M:SS format, updated every second."""

    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, slow_coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._slow_coordinator = slow_coordinator
        self._attr_name = f"{program_name} run countdown"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_run_countdown"
        self._end_time: datetime | None = None
        self._unsub_timer = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_tick, timedelta(seconds=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _async_tick(self, now) -> None:
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        total_remaining = sum(
            item.get("remaining", 0)
            for item in self.coordinator.data.get("queue", [])
            if item.get("pid") == self._pid
        )
        if total_remaining <= 0:
            self._end_time = None
        elif self._end_time is None:
            self._end_time = datetime.now().astimezone() + timedelta(seconds=total_remaining)
        else:
            local_rem = (self._end_time - datetime.now().astimezone()).total_seconds()
            if abs(local_rem - total_remaining) > 2:
                self._end_time = datetime.now().astimezone() + timedelta(seconds=total_remaining)
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | None:
        if self._end_time is None:
            return None
        remaining = (self._end_time - datetime.now().astimezone()).total_seconds()
        if remaining <= 0:
            self._end_time = None
            return None
        return _seconds_to_mmss(int(remaining))

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}
        if self._end_time is not None:
            remaining = (self._end_time - datetime.now().astimezone()).total_seconds()
            attrs["remaining_seconds"] = max(0, int(remaining))
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


class RainMachinePauseCountdown(RainMachineBaseEntity, SensorEntity):
    """Sensor: remaining pause time in M:SS format, updated every second."""

    _attr_icon = "mdi:pause-circle-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, slow_coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._slow_coordinator = slow_coordinator
        self._attr_name = "Pause countdown"
        self._attr_unique_id = f"{entry.entry_id}_pause_countdown"
        self._end_time: datetime | None = None
        self._unsub_timer = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_tick, timedelta(seconds=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _async_tick(self, now) -> None:
        if self._end_time is None:
            stored = self.hass.data[DOMAIN].get(f"{self._entry.entry_id}_pause_end_time")
            if stored is not None:
                self._end_time = stored
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        stored = self.hass.data[DOMAIN].get(f"{self._entry.entry_id}_pause_end_time")
        if stored is None:
            self._end_time = None
        else:
            self._end_time = stored
        self.async_write_ha_state()

    @callback
    def _refresh_slow_after_pause(self, _now=None) -> None:
        self.hass.async_create_task(self._slow_coordinator.async_request_refresh())

    @property
    def native_value(self) -> str | None:
        if self._end_time is None:
            return None
        remaining = (self._end_time - datetime.now().astimezone()).total_seconds()
        if remaining <= 0:
            self._end_time = None
            self.hass.data[DOMAIN][f"{self._entry.entry_id}_pause_end_time"] = None
            self.hass.async_create_task(self.coordinator.async_request_refresh())
            self.hass.async_create_task(self._slow_coordinator.async_request_refresh())
            self.hass.async_call_later(5, self._refresh_slow_after_pause)
            return None
        return _seconds_to_mmss(int(remaining))

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}
        if self._end_time is not None:
            remaining = (self._end_time - datetime.now().astimezone()).total_seconds()
            attrs["remaining_seconds"] = max(0, int(remaining))
        return attrs
