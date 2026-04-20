"""Number platform for RainMachine Pro."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_PROGRAMS
from .coordinator import RainMachineProCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})

    entities = [RainMachineRainDelayNumber(coordinator, entry)]

    for program in fast_coordinator.data.get("programs", []):
        pid = program["uid"]
        prog_cfg = enabled_programs.get(str(pid), {})
        if not prog_cfg.get("enabled", True):
            continue
        name = prog_cfg.get("name") or program.get("name", f"Program {pid}")
        step_key = f"{entry.entry_id}_prog_step_{pid}"
        hass.data[DOMAIN].setdefault(step_key, {"value": 10})
        step_state = hass.data[DOMAIN][step_key]
        entities.append(RainMachineProgramAdjustStep(coordinator, entry, pid, name, step_state))

    async_add_entities(entities)


class RainMachineRainDelayNumber(CoordinatorEntity, NumberEntity):
    """Number entity for setting rain delay days."""

    _attr_has_entity_name = True
    _attr_name = "Rain delay days"
    _attr_icon = "mdi:weather-rainy"
    _attr_native_min_value = 0
    _attr_native_max_value = 14
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "days"

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_rain_delay_days"
        self._value = 0

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        days = int(value)
        self._value = days
        self.async_write_ha_state()
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                await self.coordinator.client.authenticate(session)
                await self.coordinator.client.set_rain_delay(session, days)
            _LOGGER.info("Rain delay set to %d days", days)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set rain delay: %s", err)


class RainMachineProgramAdjustStep(CoordinatorEntity, NumberEntity):
    """Number entity: duration adjustment step for a program (5-20%)."""

    _attr_native_min_value = 5
    _attr_native_max_value = 20
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:percent-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, pid: int, program_name: str, step_state: dict) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._pid = pid
        self._step_state = step_state
        self._attr_name = f"{program_name} adjustment step"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_adjust_step"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def native_value(self) -> float:
        return float(self._step_state["value"])

    async def async_set_native_value(self, value: float) -> None:
        self._step_state["value"] = int(value)
        self.async_write_ha_state()
