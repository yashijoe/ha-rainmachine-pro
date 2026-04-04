"""Constants for RainMachine Pro integration."""

DOMAIN = "rainmachine_pro"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_ZONES = "zones"
CONF_PARSERS = "parsers"

DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = 5  # minutes
DEFAULT_TIMEOUT = 20  # seconds

# Parser key -> (search string in RM description, entity suffix, friendly name)
AVAILABLE_PARSERS = {
    "metno": {
        "search": "met.no",
        "entity_suffix": "metno_last_run",
        "friendly_name": "MET.NO",
    },
    "openweathermap": {
        "search": "openweathermap.org",
        "entity_suffix": "openweathermap_last_run",
        "friendly_name": "OpenWeather",
    },
    "wh2550a": {
        "search": "WH2550A",
        "entity_suffix": "wh2550a_last_run",
        "friendly_name": "WH2550A personal station",
    },
    "wunderground": {
        "search": "Weather Underground",
        "entity_suffix": "wunderground_last_run",
        "friendly_name": "WUnderground",
    },
}

FLAG_MAP = {
    0: "Normal watering",
    1: "Interrupted by user",
    2: "Restriction threshold",
    3: "Freeze protect",
    4: "Restriction day",
    5: "Out of allowed days",
    6: "Water surplus",
    7: "Stopped by rain sensor",
    8: "Software rain sensor restriction",
    9: "Month restricted",
    10: "Delay set by user",
    11: "Program rain restriction",
    12: "Adaptive frequency skip",
}

WEATHER_CONDITIONS = {
    0: "cloudy", 1: "sunny", 2: "partly-cloudy", 3: "partly-cloudy",
    4: "partly-cloudy", 5: "rainy", 6: "sunny", 7: "snowy",
    8: "snowy", 9: "sunny", 10: "snowy", 11: "partly-rainy",
    12: "lightning-rainy", 13: "partly-cloudy", 14: "cloudy",
    15: "sunny", 16: "sunny", 17: "lightning-rainy", 18: "partly-rainy",
    19: "pouring", 20: "partly-cloudy", 21: "cloudy",
}

WEATHER_CONDITIONS_TRANSLATED = {
    "sunny": "Sereno",
    "partly-cloudy": "Parzialmente nuvoloso",
    "cloudy": "Nuvoloso",
    "rainy": "Piovoso",
    "lightning-rainy": "Temporale",
    "snowy": "Nevoso",
    "partly-rainy": "Parzialmente piovoso",
    "pouring": "Pioggia intensa",
    "unknown": "Sconosciuto",
}

WEATHER_ICONS = {
    "sunny": "mdi:weather-sunny",
    "partly-cloudy": "mdi:weather-partly-cloudy",
    "cloudy": "mdi:weather-cloudy",
    "rainy": "mdi:weather-rainy",
    "snowy": "mdi:weather-snowy",
    "partly-rainy": "mdi:weather-partly-rainy",
    "pouring": "mdi:weather-pouring",
    "lightning-rainy": "mdi:weather-lightning-rainy",
    "unknown": "mdi:weather-cloudy-alert",
}
