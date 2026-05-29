"""Number platform for RainMachine Pro."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_PROGRAMS, CONF_ZONES
from .coordinator import RainMachineProCoordinator

_LOGGER = logging.getLogger(__name__)

_DAY_POS = [8, 7, 6, 5, 4, 3, 2]


def _param_to_days(param) -> list:
    s = str(param).zfill(10)
    return [s[pos] == '1' for pos in _DAY_POS]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})
    zones_config = entry.options.get(CONF_ZONES, {})

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

        entities.append(
            RainMachineProgramFrequencyInterval(fast_coordinator, entry, pid, name, freq_state)
        )

        for wt in program.get("wateringTimes", []):
            zid = wt["id"]
            zone_cfg = zones_config.get(str(zid), {})
            if not zone_cfg.get("enabled", False):
                continue
            zone_name = zone_cfg.get("name") or wt.get("name", f"Zone {zid}")
            entities.append(
                RainMachineProgramZonePercentageNumber(
                    fast_coordinator, entry, pid, name, zid, zone_name
                )
            )

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


class RainMachineProgramFrequencyInterval(CoordinatorEntity, NumberEntity):
    """Number entity for the interval (days) when frequency is 'Every N days'."""

    _attr_native_min_value = 1
    _attr_native_max_value = 14
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "days"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:calendar-range"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, pid: int, program_name: str, freq_state: dict) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._pid = pid
        self._freq_state = freq_state
        self._attr_name = f"{program_name} frequency interval"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_frequency_interval"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    def _get_program(self) -> dict | None:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                return prog
        return None

    @property
    def native_value(self) -> float:
        prog = self._get_program()
        if prog:
            freq = prog.get("frequency", {})
            if int(freq.get("type", -1)) == 1:
                try:
                    return float(int(freq.get("param", 2)))
                except (ValueError, TypeError):
                    pass
        return float(self._freq_state["interval"])

    async def async_set_native_value(self, value: float) -> None:
        self._freq_state["interval"] = int(value)
        self.async_write_ha_state()
        prog = self._get_program()
        if prog and int(prog.get("frequency", {}).get("type", -1)) == 1:
            try:
                await self.coordinator.client.action_set_program_frequency(
                    self._pid, {"type": 1, "param": str(int(value))}
                )
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.error("Failed to set frequency interval for program %s: %s", self._pid, err)


class RainMachineProgramZonePercentageNumber(CoordinatorEntity, NumberEntity):
    """Number entity: WaterSense userPercentage for a zone in a program."""

    _attr_has_entity_name = True
    _attr_native_min_value = 5
    _attr_native_max_value = 500
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:water-percent"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, entry, pid: int, prog_name: str, zid: int, zone_name: str
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._pid = pid
        self._zid = zid
        self._attr_name = f"{prog_name} {zone_name} watering percentage"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_zone_{zid}_watering_percentage"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    def _get_wt(self) -> dict | None:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                for wt in prog.get("wateringTimes", []):
                    if wt["id"] == self._zid:
                        return wt
        return None

    @property
    def native_value(self) -> float | None:
        wt = self._get_wt()
        if wt is None:
            return None
        return round(wt.get("userPercentage", 1.0) * 100, 1)

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.coordinator.client.action_set_zone_user_percentage(
                self._pid, self._zid, value / 100.0
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error(
                "Failed to set watering percentage for program %s zone %s: %s",
                self._pid, self._zid, err,
            )
