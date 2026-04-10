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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    zones = entry.options.get(CONF_ZONES, {})

    entities: list[SensorEntity] = []

    # Today watering summary
    entities.append(RainMachineTodayWateringSensor(coordinator, entry))

    # Rain delay
    entities.append(RainMachineRainDelaySensor(coordinator, entry))

    # Zone sensors — only enabled zones
    for uid_str, zone_data in zones.items():
        if zone_data.get("enabled", False):
            entities.append(
                RainMachineZoneSensor(
                    coordinator, entry, int(uid_str),
                    zone_data.get("name", f"Zone {uid_str}")
                )
            )

    # Parser sensors — build from stored dict; migrate old list format if needed
    parsers_config = entry.options.get(CONF_PARSERS, {})
    if isinstance(parsers_config, list):
        # Migration: old format was a list of string keys — enable all known parsers
        parsers_config = {
            str(p["uid"]): {"description": p.get("description", ""), "enabled": True}
            for p in coordinator.data.get("parsers", [])
            if p.get("uid") and p.get("description")
        }
    for uid_str, parser_cfg in parsers_config.items():
        if not isinstance(parser_cfg, dict) or not parser_cfg.get("enabled", True):
            continue
        entities.append(
            RainMachineParserSensor(
                coordinator, entry, int(uid_str), parser_cfg.get("description", f"Parser {uid_str}")
            )
        )

    # Forecast sensors (7 days: yesterday + today + 5 days)
    for i in range(7):
        entities.append(RainMachineForecastSensor(coordinator, entry, i))

    # Run completion time — use fast coordinator for real-time updates
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    enabled_zones_cfg = entry.options.get(CONF_ZONES, {})
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})

    for zone in fast_coordinator.data.get("zones", []):
        uid = zone["uid"]
        zone_cfg = enabled_zones_cfg.get(str(uid), {})
        if not zone_cfg.get("enabled", False):
            continue
        name = zone_cfg.get("name") or zone.get("name", f"Zone {uid}")
        entities.append(
            RainMachineZoneRunCompletionTime(
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
            RainMachineProgramRunCompletionTime(
                fast_coordinator, coordinator, entry, pid, name
            )
        )

    async_add_entities(entities)




class RainMachineTodayWateringSensor(RainMachineBaseEntity, SensorEntity):
    """Sensor for today's total watering duration."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:sprinkler"
    _attr_name = "Today watering"

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_today_watering"
        self.entity_id = "sensor.rainmachine_today_watering"

    @property
    def last_reset(self) -> datetime:
        """Return midnight of today (local time, UTC-aware)."""
        now = datetime.now().astimezone()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    @property
    def native_value(self):
        """Return state."""
        watering = self.coordinator.data.get("watering", {})
        days = watering.get("waterLog", {}).get("days", [])
        if not days:
            return 0
        today_str = datetime.now().strftime("%Y-%m-%d")
        for day in days:
            if day.get("date") == today_str:
                return int(day.get("realDuration", 0)) // 60
        return 0

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        watering = self.coordinator.data.get("watering", {})
        days = watering.get("waterLog", {}).get("days", [])
        today_str = datetime.now().strftime("%Y-%m-%d")
        user_duration = 0
        for day in days:
            if day.get("date") == today_str:
                user_duration = int(day.get("userDuration", 0))
                break
        mins = user_duration // 60
        secs = user_duration % 60
        return {
            "date": today_str,
            "userDuration": f"{mins}:{secs:02d}",
        }


class RainMachineRainDelaySensor(RainMachineBaseEntity, SensorEntity):
    """Sensor for rain delay status."""

    _attr_icon = "mdi:timer-sand"
    _attr_name = "Rain delay"

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_rain_delay"
        self.entity_id = "sensor.rainmachine_rain_delay"

    @property
    def native_value(self):
        """Return state as AppDaemon format."""
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
        """Return icon."""
        rd = self.coordinator.data.get("raindelay", {})
        delay_sec = int(rd.get("delayCounter", -1))
        return "mdi:timer-sand" if delay_sec > 0 else "mdi:timer-off"

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        rd = self.coordinator.data.get("raindelay", {})
        delay_sec = int(rd.get("delayCounter", -1))
        if delay_sec <= 0:
            return {
                "seconds_remaining": 0,
                "minutes_remaining": 0,
                "hours_remaining": 0,
                "days_remaining": 0,
                "ends_at": None,
            }
        days = delay_sec // 86400
        hours = (delay_sec % 86400) // 3600
        minutes = (delay_sec % 3600) // 60
        ends_at = (datetime.now() + timedelta(seconds=delay_sec)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return {
            "days_remaining": days,
            "hours_remaining": hours,
            "minutes_remaining": minutes,
            "seconds_remaining": delay_sec,
            "ends_at": ends_at,
        }


class RainMachineZoneSensor(RainMachineBaseEntity, SensorEntity):
    """Sensor for zone watering details."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sprinkler"

    def __init__(self, coordinator, entry, uid: int, zone_name: str):
        """Initialize."""
        super().__init__(coordinator, entry)
        self._uid = uid
        self._zone_name = zone_name
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}"
        self._attr_name = zone_name
        self.entity_id = f"sensor.rainmachine_uid{uid}_watering"

    def _get_zone_data(self) -> dict | None:
        """Get zone data from coordinator, searching across all programs."""
        details = self.coordinator.data.get("details", {})
        all_days = details.get("waterLog", {}).get("days", [])
        if not all_days:
            return None
        for program in all_days[0].get("programs", []):
            for zone in program.get("zones", []):
                if zone.get("uid") == self._uid:
                    return zone
        return None

    @property
    def native_value(self):
        """Return state."""
        zone = self._get_zone_data()
        if not zone:
            return 0
        cycle = zone.get("cycles", [{}])[0]
        return int(cycle.get("realDuration", 0)) // 60

    @property
    def extra_state_attributes(self):
        """Return extra attributes matching AppDaemon format."""
        lang = self._get_lang()
        flag_map = FLAG_MAP.get(lang, FLAG_MAP["en"])
        zone = self._get_zone_data()
        if not zone:
            return {
                "userDuration": 0,
                "userDuration_unit": "min",
                "realDuration": 0,
                "realDuration_unit": "min",
                "userDuration_display": "0 min previsti" if lang == "it" else "0 min scheduled",
                "realDuration_display": "0 min effettivi" if lang == "it" else "0 min actual",
                "startTime": None,
                "flag": flag_map.get(-1, "No watering today"),
                "icon": "mdi:sprinkler",
            }
        cycle = zone.get("cycles", [{}])[0]
        real_dur = int(cycle.get("realDuration", 0)) // 60
        user_dur = int(cycle.get("userDuration", 0)) // 60
        flag = zone.get("flag", -1)

        if lang == "it":
            user_label = "previsti"
            real_label = "effettivi"
        elif lang == "de":
            user_label = "geplant"
            real_label = "tatsächlich"
        elif lang == "fr":
            user_label = "prévus"
            real_label = "effectifs"
        elif lang == "es":
            user_label = "previstos"
            real_label = "efectivos"
        else:
            user_label = "scheduled"
            real_label = "actual"

        return {
            "userDuration": user_dur,
            "userDuration_unit": "min",
            "realDuration": real_dur,
            "realDuration_unit": "min",
            "userDuration_display": f"{user_dur} min {user_label}",
            "realDuration_display": f"{real_dur} min {real_label}",
            "startTime": cycle.get("startTime"),
            "flag": flag_map.get(flag, flag_map.get(-1, "No watering today")),
            "icon": "mdi:sprinkler",
        }


class RainMachineParserSensor(RainMachineBaseEntity, SensorEntity):
    """Sensor for weather parser last run."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry, uid: int, description: str):
        """Initialize."""
        super().__init__(coordinator, entry)
        self._uid = uid
        self._description = description
        self._attr_unique_id = f"{entry.entry_id}_parser_{uid}"
        self._attr_name = description
        suffix = re.sub(r"[^a-z0-9]+", "_", description.lower()).strip("_")
        self.entity_id = f"sensor.rainmachine_{suffix}_last_run"

    def _find_parser(self) -> dict | None:
        """Find matching parser data by UID."""
        for parser in self.coordinator.data.get("parsers", []):
            if parser.get("uid") == self._uid:
                return parser
        return None

    @property
    def native_value(self):
        """Return state."""
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
        """Return extra attributes."""
        parser = self._find_parser()
        active = parser is not None and parser.get("lastRun") not in (None, "unknown")
        return {"active": active}

    @property
    def icon(self):
        """Return icon based on forecast condition."""
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
    """Sensor for daily forecast conditions."""

    def __init__(self, coordinator, entry, index: int):
        """Initialize."""
        super().__init__(coordinator, entry)
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_forecast_{index}"
        self.entity_id = f"sensor.rainmachine_forecast_condition_{index}"

    def _get_forecast_day(self) -> tuple[dict | None, int]:
        """Get forecast data for this index."""
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

    def _get_day_label(self, delta: int) -> str:
        """Get translated day label."""
        lang = self._get_lang()

        day_names_map = {
            "it": {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"},
            "de": {0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag", 4: "Freitag", 5: "Samstag", 6: "Sonntag"},
            "fr": {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"},
            "es": {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"},
            "en": {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"},
        }
        relative_map = {
            "it": {-1: "Ieri", 0: "Oggi", 1: "Domani"},
            "de": {-1: "Gestern", 0: "Heute", 1: "Morgen"},
            "fr": {-1: "Hier", 0: "Aujourd'hui", 1: "Demain"},
            "es": {-1: "Ayer", 0: "Hoy", 1: "Mañana"},
            "en": {-1: "Yesterday", 0: "Today", 1: "Tomorrow"},
        }

        relatives = relative_map.get(lang, relative_map["en"])
        if delta in relatives:
            return relatives[delta]

        day_names = day_names_map.get(lang, day_names_map["en"])
        target = datetime.today().date() + timedelta(days=delta)
        return day_names.get(target.weekday(), str(target))

    @property
    def name(self):
        """Return dynamic name based on day offset."""
        _, delta = self._get_forecast_day()
        return self._get_day_label(delta)

    @property
    def native_value(self):
        """Return state."""
        data, _ = self._get_forecast_day()
        if not data:
            return "unknown"
        code = data.get("condition", -1)
        return WEATHER_CONDITIONS.get(code, "unknown")

    @property
    def icon(self):
        """Return icon."""
        condition = self.native_value
        return WEATHER_ICONS.get(condition, "mdi:weather-cloudy-alert")

    @property
    def extra_state_attributes(self):
        """Return extra attributes matching AppDaemon format."""
        data, delta = self._get_forecast_day()
        if not data:
            return {}
        lang = self._get_lang()
        code = data.get("condition", -1)
        condition = WEATHER_CONDITIONS.get(code, "unknown")
        conditions_translated = WEATHER_CONDITIONS_TRANSLATED.get(lang, WEATHER_CONDITIONS_TRANSLATED["en"])
        state_translated = conditions_translated.get(condition, conditions_translated.get("unknown", "Unknown"))

        # Translated labels for rain
        rain_labels = {
            "it": {"rain": "di pioggia", "forecast": "di pioggia prevista"},
            "de": {"rain": "Regen", "forecast": "Regen vorhergesagt"},
            "fr": {"rain": "de pluie", "forecast": "de pluie prévue"},
            "es": {"rain": "de lluvia", "forecast": "de lluvia prevista"},
            "en": {"rain": "rain", "forecast": "rain forecast"},
        }
        labels = rain_labels.get(lang, rain_labels["en"])

        return {
            "temperature": int(data.get("temperature", 0)),
            "temperature_unit": "°C",
            "temperature_display": f"{int(data.get('temperature', 0))}°",
            "min_temperature": int(data.get("minTemp", 0)),
            "min_temperature_unit": "°C",
            "min_temperature_display": f"{int(data.get('minTemp', 0))}° min",
            "max_temperature": int(data.get("maxTemp", 0)),
            "max_temperature_unit": "°C",
            "max_temperature_display": f"{int(data.get('maxTemp', 0))}° max",
            "rain": data.get("rain", 0),
            "rain_unit": "mm",
            "rain_display": f"{data.get('rain', 0)} mm {labels['rain']}",
            "precipitation_forecast": data.get("qpf", 0),
            "precipitation_forecast_unit": "mm",
            "precipitation_forecast_display": f"{data.get('qpf', 0)} mm {labels['forecast']}",
            "EvapoTranspiration": data.get("et0final", 0),
            "EvapoTranspiration_unit": "mm",
            "EvapoTranspiration_display": f"{data.get('et0final', 0)} mm",
            "day": data.get("day", "").split(" ")[0],
            "meteocode": code,
            "friendly_name": self._get_day_label(delta),
            "state_translated": state_translated,
            "icon": f"mdi:weather-{condition}",
        }


# ---------------------------------------------------------------------------
# Run completion time sensors
# ---------------------------------------------------------------------------

class RainMachineZoneRunCompletionTime(RainMachineBaseEntity, SensorEntity):
    """Sensor: when the current zone run will finish."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, slow_coordinator, entry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator, entry)
        self._uid = uid
        self._slow_coordinator = slow_coordinator
        self._attr_name = f"{zone_name} run completion time"
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_run_completion"

    @property
    def native_value(self) -> datetime | None:
        """Return estimated completion time or None if not running."""
        for item in self.coordinator.data.get("queue", []):
            if item.get("zid") == self._uid and item.get("running"):
                remaining = item.get("remaining", 0)
                if remaining > 0:
                    return datetime.now().astimezone() + timedelta(seconds=remaining)
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return last_run and next_run attributes."""
        attrs = {}
        # next_run: scheduled (not yet running) queue item for this zone
        for item in self.coordinator.data.get("queue", []):
            if item.get("zid") == self._uid and not item.get("running"):
                val = item.get("startTime") or item.get("eta")
                if val:
                    attrs["next_run"] = val
                break
        # last_run: from slow coordinator watering details
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
                                    attrs["last_run_end"] = (
                                        dt + timedelta(seconds=real_dur)
                                    ).isoformat()
                                except (ValueError, TypeError):
                                    pass
                            break
        except Exception:
            pass
        return attrs


class RainMachineProgramRunCompletionTime(RainMachineBaseEntity, SensorEntity):
    """Sensor: when the current program run will finish."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, slow_coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._slow_coordinator = slow_coordinator
        self._attr_name = f"{program_name} run completion time"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_run_completion"

    @property
    def native_value(self) -> datetime | None:
        """Return estimated completion time or None if not running."""
        for item in self.coordinator.data.get("queue", []):
            if item.get("pid") == self._pid and item.get("running"):
                remaining = item.get("remaining", 0)
                if remaining > 0:
                    return datetime.now().astimezone() + timedelta(seconds=remaining)
        return None

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
