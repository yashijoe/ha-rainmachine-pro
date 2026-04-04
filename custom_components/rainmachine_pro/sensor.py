"""Sensor platform for RainMachine Pro."""

import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_ZONES,
    CONF_PARSERS,
    AVAILABLE_PARSERS,
    FLAG_MAP,
    WEATHER_CONDITIONS,
    WEATHER_CONDITIONS_TRANSLATED,
    WEATHER_ICONS,
)
from .coordinator import RainMachineProCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    zones = entry.options.get(CONF_ZONES, {})
    enabled_parsers = entry.options.get(CONF_PARSERS, list(AVAILABLE_PARSERS.keys()))

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

    # Parser sensors
    for parser_key in enabled_parsers:
        if parser_key in AVAILABLE_PARSERS:
            parser_info = AVAILABLE_PARSERS[parser_key]
            entities.append(
                RainMachineParserSensor(
                    coordinator, entry, parser_key, parser_info
                )
            )

    # Forecast sensors (7 days: yesterday + today + 5 days)
    for i in range(7):
        entities.append(RainMachineForecastSensor(coordinator, entry, i))

    async_add_entities(entities)


class RainMachineBaseEntity(CoordinatorEntity):
    """Base entity for RainMachine Pro."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainMachineProCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "RainMachine",
            "manufacturer": "RainMachine",
            "model": "Pro",
            "configuration_url": f"https://{self._entry.data.get('host', '')}:{self._entry.data.get('port', 8080)}",
        }


class RainMachineTodayWateringSensor(RainMachineBaseEntity, SensorEntity):
    """Sensor for today's total watering duration."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sprinkler"
    _attr_name = "Today watering"

    def __init__(self, coordinator, entry):
        """Initialize."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_today_watering"
        self.entity_id = "sensor.rainmachine_today_watering"

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
        """Get zone data from coordinator."""
        details = self.coordinator.data.get("details", {})
        all_days = details.get("waterLog", {}).get("days", [])
        if not all_days:
            return None
        programs = all_days[0].get("programs", [])
        if not programs:
            return None
        for zone in programs[0].get("zones", []):
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
        zone = self._get_zone_data()
        if not zone:
            return {
                "userDuration": 0,
                "userDuration_unit": "min",
                "realDuration": 0,
                "realDuration_unit": "min",
                "userDuration_display": "0 min previsti",
                "realDuration_display": "0 min effettivi",
                "startTime": None,
                "flag": "Nessuna irrigazione oggi",
                "icon": "mdi:sprinkler",
            }
        cycle = zone.get("cycles", [{}])[0]
        real_dur = int(cycle.get("realDuration", 0)) // 60
        user_dur = int(cycle.get("userDuration", 0)) // 60
        flag = zone.get("flag", -1)
        return {
            "userDuration": user_dur,
            "userDuration_unit": "min",
            "realDuration": real_dur,
            "realDuration_unit": "min",
            "userDuration_display": f"{user_dur} min previsti",
            "realDuration_display": f"{real_dur} min effettivi",
            "startTime": cycle.get("startTime"),
            "flag": FLAG_MAP.get(flag, "Nessuna irrigazione oggi"),
            "icon": "mdi:sprinkler",
        }


class RainMachineParserSensor(RainMachineBaseEntity, SensorEntity):
    """Sensor for weather parser last run."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, entry, parser_key: str, parser_info: dict):
        """Initialize."""
        super().__init__(coordinator, entry)
        self._parser_key = parser_key
        self._search_string = parser_info["search"]
        self._attr_unique_id = f"{entry.entry_id}_parser_{parser_key}"
        self._attr_name = parser_info["friendly_name"]
        self.entity_id = f"sensor.rainmachine_{parser_info['entity_suffix']}"

    def _find_parser(self) -> dict | None:
        """Find matching parser data."""
        parsers = self.coordinator.data.get("parsers", [])
        for parser in parsers:
            desc = parser.get("description", "")
            if self._search_string in desc:
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
        try:
            from homeassistant.core import HomeAssistant
            lang = self.hass.config.language if self.hass else "en"
        except Exception:
            lang = "en"

        if lang.startswith("it"):
            day_names = {
                0: "Lunedì", 1: "Martedì", 2: "Mercoledì",
                3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica",
            }
            if delta == -1:
                return "Ieri"
            if delta == 0:
                return "Oggi"
            if delta == 1:
                return "Domani"
        elif lang.startswith("de"):
            day_names = {
                0: "Montag", 1: "Dienstag", 2: "Mittwoch",
                3: "Donnerstag", 4: "Freitag", 5: "Samstag", 6: "Sonntag",
            }
            if delta == -1:
                return "Gestern"
            if delta == 0:
                return "Heute"
            if delta == 1:
                return "Morgen"
        elif lang.startswith("fr"):
            day_names = {
                0: "Lundi", 1: "Mardi", 2: "Mercredi",
                3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche",
            }
            if delta == -1:
                return "Hier"
            if delta == 0:
                return "Aujourd'hui"
            if delta == 1:
                return "Demain"
        elif lang.startswith("es"):
            day_names = {
                0: "Lunes", 1: "Martes", 2: "Miércoles",
                3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo",
            }
            if delta == -1:
                return "Ayer"
            if delta == 0:
                return "Hoy"
            if delta == 1:
                return "Mañana"
        else:
            day_names = {
                0: "Monday", 1: "Tuesday", 2: "Wednesday",
                3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday",
            }
            if delta == -1:
                return "Yesterday"
            if delta == 0:
                return "Today"
            if delta == 1:
                return "Tomorrow"

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
        code = data.get("condition", -1)
        condition = WEATHER_CONDITIONS.get(code, "unknown")
        state_translated = WEATHER_CONDITIONS_TRANSLATED.get(condition, "Sconosciuto")

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
            "rain_display": f"{data.get('rain', 0)} mm di pioggia",
            "precipitation_forecast": data.get("qpf", 0),
            "precipitation_forecast_unit": "mm",
            "precipitation_forecast_display": f"{data.get('qpf', 0)} mm di pioggia prevista",
            "EvapoTranspiration": data.get("et0final", 0),
            "EvapoTranspiration_unit": "mm",
            "EvapoTranspiration_display": f"{data.get('et0final', 0)} mm",
            "day": data.get("day", "").split(" ")[0],
            "meteocode": code,
            "friendly_name": self._get_day_label(delta),
            "state_translated": state_translated,
            "icon": f"mdi:weather-{condition}",
        }
