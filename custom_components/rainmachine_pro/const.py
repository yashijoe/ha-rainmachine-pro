"""Constants for RainMachine Pro integration."""

DOMAIN = "rainmachine_pro"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SCAN_INTERVAL_FAST = "scan_interval_fast"
CONF_TIMEOUT = "timeout"
CONF_ZONES = "zones"
CONF_PARSERS = "parsers"

DEFAULT_PORT = 8080
DEFAULT_SCAN_INTERVAL = 5       # minutes
DEFAULT_SCAN_INTERVAL_FAST = 10  # seconds
DEFAULT_TIMEOUT = 20             # seconds

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
    "en": {
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
        -1: "No watering today",
    },
    "it": {
        0: "Irrigazione normale",
        1: "Interrotto dall'utente",
        2: "Soglia di restrizione",
        3: "Protezione antigelo attiva",
        4: "Giorno soggetto a restrizione",
        5: "Fuori dai giorni consentiti",
        6: "Eccesso d'acqua",
        7: "Interrotto dal sensore pioggia",
        8: "Restrizione software per pioggia",
        9: "Restrizione mensile attiva",
        10: "Ritardo impostato dall'utente",
        11: "Restrizione pioggia del programma",
        12: "Saltato per frequenza adattiva",
        -1: "Nessuna irrigazione oggi",
    },
    "de": {
        0: "Normale Bewässerung",
        1: "Vom Benutzer unterbrochen",
        2: "Einschränkungsschwelle",
        3: "Frostschutz aktiv",
        4: "Eingeschränkter Tag",
        5: "Außerhalb erlaubter Tage",
        6: "Wasserüberschuss",
        7: "Vom Regensensor gestoppt",
        8: "Software-Regensensor-Einschränkung",
        9: "Monatliche Einschränkung aktiv",
        10: "Vom Benutzer gesetzte Verzögerung",
        11: "Programm-Regeneinschränkung",
        12: "Adaptive Frequenz übersprungen",
        -1: "Keine Bewässerung heute",
    },
    "fr": {
        0: "Arrosage normal",
        1: "Interrompu par l'utilisateur",
        2: "Seuil de restriction",
        3: "Protection antigel active",
        4: "Jour soumis à restriction",
        5: "Hors des jours autorisés",
        6: "Excès d'eau",
        7: "Arrêté par le capteur de pluie",
        8: "Restriction logicielle capteur de pluie",
        9: "Restriction mensuelle active",
        10: "Délai défini par l'utilisateur",
        11: "Restriction pluie du programme",
        12: "Saut fréquence adaptative",
        -1: "Pas d'arrosage aujourd'hui",
    },
    "es": {
        0: "Riego normal",
        1: "Interrumpido por el usuario",
        2: "Umbral de restricción",
        3: "Protección antihielo activa",
        4: "Día sujeto a restricción",
        5: "Fuera de los días permitidos",
        6: "Exceso de agua",
        7: "Detenido por sensor de lluvia",
        8: "Restricción software sensor de lluvia",
        9: "Restricción mensual activa",
        10: "Retraso establecido por el usuario",
        11: "Restricción de lluvia del programa",
        12: "Salto de frecuencia adaptativa",
        -1: "Sin riego hoy",
    },
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
    "en": {
        "sunny": "Sunny",
        "partly-cloudy": "Partly cloudy",
        "cloudy": "Cloudy",
        "rainy": "Rainy",
        "lightning-rainy": "Thunderstorm",
        "snowy": "Snowy",
        "partly-rainy": "Partly rainy",
        "pouring": "Heavy rain",
        "unknown": "Unknown",
    },
    "it": {
        "sunny": "Sereno",
        "partly-cloudy": "Parzialmente nuvoloso",
        "cloudy": "Nuvoloso",
        "rainy": "Piovoso",
        "lightning-rainy": "Temporale",
        "snowy": "Nevoso",
        "partly-rainy": "Parzialmente piovoso",
        "pouring": "Pioggia intensa",
        "unknown": "Sconosciuto",
    },
    "de": {
        "sunny": "Sonnig",
        "partly-cloudy": "Teilweise bewölkt",
        "cloudy": "Bewölkt",
        "rainy": "Regnerisch",
        "lightning-rainy": "Gewitter",
        "snowy": "Schnee",
        "partly-rainy": "Teilweise regnerisch",
        "pouring": "Starkregen",
        "unknown": "Unbekannt",
    },
    "fr": {
        "sunny": "Ensoleillé",
        "partly-cloudy": "Partiellement nuageux",
        "cloudy": "Nuageux",
        "rainy": "Pluvieux",
        "lightning-rainy": "Orage",
        "snowy": "Neigeux",
        "partly-rainy": "Partiellement pluvieux",
        "pouring": "Pluie intense",
        "unknown": "Inconnu",
    },
    "es": {
        "sunny": "Soleado",
        "partly-cloudy": "Parcialmente nublado",
        "cloudy": "Nublado",
        "rainy": "Lluvioso",
        "lightning-rainy": "Tormenta",
        "snowy": "Nevado",
        "partly-rainy": "Parcialmente lluvioso",
        "pouring": "Lluvia intensa",
        "unknown": "Desconocido",
    },
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
