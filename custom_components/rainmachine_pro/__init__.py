"""RainMachine Pro integration for Home Assistant."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import RainMachineClient
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST,
    CONF_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_FAST,
    DEFAULT_TIMEOUT,
)
from .coordinator import RainMachineProCoordinator, RainMachineProFastCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "binary_sensor", "button", "switch", "select", "update"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RainMachine Pro from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    password = entry.data[CONF_PASSWORD]
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval_fast = entry.options.get(CONF_SCAN_INTERVAL_FAST, DEFAULT_SCAN_INTERVAL_FAST)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    client = RainMachineClient(host, port, password, timeout)
    coordinator = RainMachineProCoordinator(hass, client, scan_interval)
    fast_coordinator = RainMachineProFastCoordinator(hass, client, scan_interval_fast)

    await coordinator.async_config_entry_first_refresh()
    await fast_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN][f"{entry.entry_id}_fast"] = fast_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_fast", None)
    return unload_ok
