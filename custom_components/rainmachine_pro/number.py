"""Number platform for RainMachine Pro."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
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

    hass.data[DOMAIN].setdefault(f"{entry.entry_id}_pause_duration_min", 0.0)

    entities = [
        RainMachineRainDelayNumber(coordinator, entry),
        RainMachinePauseDurationNumber(coordinator, entry),
    ]

    # Per-zone: manual duration + ET coefficient
    for uid_str, zone_cfg in zones_config.items():
        if not zone_cfg.get("enabled", False):
            continue
        uid = int(uid_str)
        zone_name = zone_cfg.get("name") or f"Zone {uid}"
        hass.data[DOMAIN].setdefault(f"{entry.entry_id}_zone_{uid}_manual_duration", 10.0)
        entities.append(RainMachineZoneManualDurationNumber(coordinator, entry, uid, zone_name))
        entities.append(RainMachineZoneETCoefNumber(coordinator, entry, uid, zone_name))

    for program in fast_coordinator.data.get("programs", []):
        pid = program["uid"]
        prog_cfg = enabled_programs.get(str(pid), {})
        if not prog_cfg.get("enabled", True):
            continue
        name = prog_cfg.get("name") or program.get("name", f"Program {pid}")

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

        cs_cycles_key = f"{entry.entry_id}_prog_{pid}_cs_cycles"
        cs_min_key = f"{entry.entry_id}_prog_{pid}_cs_min"
        hass.data[DOMAIN].setdefault(cs_cycles_key, 2)
        hass.data[DOMAIN].setdefault(cs_min_key, 0)
        cs_on = program.get("cs_on", False)
        cycles_val = int(program.get("cycles", -1))
        soak_val = int(program.get("soak", 0))
        if cs_on and cycles_val > 0:
            hass.data[DOMAIN][cs_cycles_key] = cycles_val
            hass.data[DOMAIN][cs_min_key] = soak_val // 60

        entities.append(RainMachineProgramCycleSoakCyclesNumber(fast_coordinator, entry, pid, name))
        entities.append(RainMachineProgramCycleSoakMinNumber(fast_coordinator, entry, pid, name))

        for wt in program.get("wateringTimes", []):
            zid = wt["id"]
            zone_cfg = zones_config.get(str(zid), {})
            if not zone_cfg.get("enabled", False):
                continue
            zone_name = zone_cfg.get("name") or wt.get("name", f"Zone {zid}")
            entities.append(
                RainMachineProgramZoneDurationNumber(
                    fast_coordinator, entry, pid, name, zid, zone_name
                )
            )
            entities.append(
                RainMachineProgramZonePercentageNumber(
                    fast_coordinator, entry, pid, name, zid, zone_name
                )
            )

    async_add_entities(entities)


class RainMachineRainDelayNumber(CoordinatorEntity, NumberEntity):
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


class RainMachinePauseDurationNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_name = "Pause duration"
    _attr_icon = "mdi:pause-circle-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 720
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._value: float = 0.0
        self._attr_unique_id = f"{entry.entry_id}_pause_duration"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def native_value(self) -> float:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        self.hass.data[DOMAIN][f"{self._entry.entry_id}_pause_duration_min"] = value
        self.async_write_ha_state()


class RainMachineZoneManualDurationNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_native_min_value = 0.5
    _attr_native_max_value = 300
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, entry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._uid = uid
        self._value: float = 10.0
        self._attr_name = f"{zone_name} manual duration"
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_manual_duration"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    @property
    def native_value(self) -> float:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        self.hass.data[DOMAIN][f"{self._entry.entry_id}_zone_{self._uid}_manual_duration"] = value
        self.async_write_ha_state()


class RainMachineZoneETCoefNumber(CoordinatorEntity, NumberEntity):
    """Number entity for zone ET coefficient (ETcoef). Reads from device every 5 min.
    User changes are stored as pending and applied via the apply button."""

    _attr_native_min_value = 0.01
    _attr_native_max_value = 2.0
    _attr_native_step = 0.01
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:leaf"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry, uid: int, zone_name: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._uid = uid
        self._attr_name = f"{zone_name} ET coefficient"
        self._attr_unique_id = f"{entry.entry_id}_zone_{uid}_et_coef"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    def _pending_key(self) -> str:
        return f"{self._entry.entry_id}_zone_{self._uid}_et_coef_pending"

    @property
    def native_value(self) -> float | None:
        pending = self.hass.data[DOMAIN].get(self._pending_key())
        if pending is not None:
            return pending
        props = self.coordinator.data.get("zone_properties", {}).get(self._uid, {})
        val = props.get("ETcoef")
        return round(float(val), 2) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        self.hass.data[DOMAIN][self._pending_key()] = round(value, 2)
        self.async_write_ha_state()


class RainMachineProgramFrequencyInterval(CoordinatorEntity, NumberEntity):
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


class RainMachineProgramCycleSoakCyclesNumber(CoordinatorEntity, NumberEntity):
    _attr_native_min_value = 2
    _attr_native_max_value = 50
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:repeat"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._pid = pid
        self._attr_name = f"{program_name} cycle soak cycles"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_cycle_soak_cycles"

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
        if prog and prog.get("cs_on", False) and int(prog.get("cycles", -1)) > 0:
            val = int(prog["cycles"])
            self.hass.data[DOMAIN][f"{self._entry.entry_id}_prog_{self._pid}_cs_cycles"] = val
            return float(val)
        return float(self.hass.data[DOMAIN].get(
            f"{self._entry.entry_id}_prog_{self._pid}_cs_cycles", 2
        ))

    async def async_set_native_value(self, value: float) -> None:
        cycles = int(value)
        self.hass.data[DOMAIN][f"{self._entry.entry_id}_prog_{self._pid}_cs_cycles"] = cycles
        self.async_write_ha_state()
        prog = self._get_program()
        if prog and prog.get("cs_on", False) and int(prog.get("cycles", -1)) > 0:
            soak_min = int(self.hass.data[DOMAIN].get(
                f"{self._entry.entry_id}_prog_{self._pid}_cs_min", 0
            ))
            try:
                await self.coordinator.client.action_set_cycle_soak(
                    self._pid, True, cycles, soak_min * 60
                )
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.error("Failed to set cycle soak cycles for program %s: %s", self._pid, err)


class RainMachineProgramCycleSoakMinNumber(CoordinatorEntity, NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer-sand"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._pid = pid
        self._attr_name = f"{program_name} cycle soak min"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_cycle_soak_min"

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
        if prog and prog.get("cs_on", False) and int(prog.get("cycles", -1)) > 0:
            val = int(prog.get("soak", 0)) // 60
            self.hass.data[DOMAIN][f"{self._entry.entry_id}_prog_{self._pid}_cs_min"] = val
            return float(val)
        return float(self.hass.data[DOMAIN].get(
            f"{self._entry.entry_id}_prog_{self._pid}_cs_min", 0
        ))

    async def async_set_native_value(self, value: float) -> None:
        soak_min = int(value)
        self.hass.data[DOMAIN][f"{self._entry.entry_id}_prog_{self._pid}_cs_min"] = soak_min
        self.async_write_ha_state()
        prog = self._get_program()
        if prog and prog.get("cs_on", False) and int(prog.get("cycles", -1)) > 0:
            cycles = int(self.hass.data[DOMAIN].get(
                f"{self._entry.entry_id}_prog_{self._pid}_cs_cycles", 2
            ))
            try:
                await self.coordinator.client.action_set_cycle_soak(
                    self._pid, True, cycles, soak_min * 60
                )
                await self.coordinator.async_request_refresh()
            except Exception as err:
                _LOGGER.error("Failed to set cycle soak soak_min for program %s: %s", self._pid, err)


class RainMachineProgramZoneDurationNumber(CoordinatorEntity, NumberEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_native_min_value = 0.5
    _attr_native_max_value = 299.5
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, entry, pid: int, prog_name: str, zid: int, zone_name: str
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._pid = pid
        self._zid = zid
        self._cached: float = 1.0
        self._attr_name = f"{prog_name} {zone_name} custom duration"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_zone_{zid}_custom_duration"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._entry.entry_id)}}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._cached = float(last_state.state)
            except (ValueError, TypeError):
                pass
        duration = self._get_duration()
        if duration > 0:
            self._cached = round(duration / 60.0, 1)

    def _get_duration(self) -> int:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                for wt in prog.get("wateringTimes", []):
                    if wt["id"] == self._zid:
                        return wt.get("duration", 0)
        return 0

    @property
    def native_value(self) -> float:
        duration = self._get_duration()
        if duration > 0:
            self._cached = round(duration / 60.0, 1)
        return self._cached

    async def async_set_native_value(self, value: float) -> None:
        self._cached = value
        total_seconds = int(round(value * 60))
        try:
            await self.coordinator.client.action_set_zone_duration_type(
                self._pid, self._zid, active=True, duration=total_seconds
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error(
                "Failed to set custom duration for program %s zone %s: %s",
                self._pid, self._zid, err,
            )


class RainMachineProgramZonePercentageNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_native_min_value = 10
    _attr_native_max_value = 200
    _attr_native_step = 5
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
