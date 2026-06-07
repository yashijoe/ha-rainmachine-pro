"""Select platform for RainMachine Pro."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PROGRAMS, CONF_ZONES
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)

_FREEZE_TEMPS = [str(t) for t in range(-7, 5)]
_FREQ_OPTIONS = ["daily", "every_n_days", "odd_days", "even_days", "selected_days"]
_DURATION_TYPE_OPTIONS = ["suggested", "custom", "not_set"]
_CYCLE_SOAK_OPTIONS = ["off", "auto", "custom"]

_DAY_POS = [8, 7, 6, 5, 4, 3, 2]  # Mon(0)..Sun(6) → string position


def _param_to_days(param) -> list:
    s = str(param).zfill(10)
    return [s[pos] == '1' for pos in _DAY_POS]


def _days_to_param(days: list) -> str:
    chars = ['0'] * 10
    for i, active in enumerate(days):
        chars[_DAY_POS[i]] = '1' if active else '0'
    return ''.join(chars)


def _freq_type_to_option(freq: dict) -> str:
    ftype = int(freq.get("type", 0))
    if ftype == 1:
        return "every_n_days"
    if ftype == 4:
        return "odd_days" if str(freq.get("param", "0")) == "1" else "even_days"
    if ftype == 2:
        return "selected_days"
    return "daily"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})
    zones_config = entry.options.get(CONF_ZONES, {})

    entities = [RainMachineFreezeProtectionTemp(coordinator, entry)]

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
            RainMachineProgramFrequencySelect(fast_coordinator, entry, pid, name, freq_state)
        )

        # Init cycle & soak pending state
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

        entities.append(RainMachineProgramCycleSoakSelect(fast_coordinator, entry, pid, name))

        for wt in program.get("wateringTimes", []):
            zid = wt["id"]
            zone_cfg = zones_config.get(str(zid), {})
            if not zone_cfg.get("enabled", False):
                continue
            zone_name = zone_cfg.get("name") or wt.get("name", f"Zone {zid}")
            entities.append(
                RainMachineProgramZoneDurationTypeSelect(
                    fast_coordinator, coordinator, entry, pid, name, zid, zone_name
                )
            )

    async_add_entities(entities)


class RainMachineFreezeProtectionTemp(RainMachineBaseEntity, SelectEntity):
    """Select entity for freeze protection temperature."""

    _attr_name = "Freeze protection temperature"
    _attr_icon = "mdi:thermometer-snowflake"
    _attr_options = _FREEZE_TEMPS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_freeze_protection_temperature"

    @property
    def current_option(self) -> str | None:
        temp = self.coordinator.data.get("restrictions_global", {}).get("freezeProtectTemp")
        if temp is None:
            return None
        val = str(int(temp))
        return val if val in _FREEZE_TEMPS else None

    async def async_select_option(self, option: str) -> None:
        try:
            await self.coordinator.client.action_set_global_restriction(
                {"freezeProtectTemp": int(option)}
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set freeze protection temperature: %s", err)


class RainMachineProgramFrequencySelect(RainMachineBaseEntity, SelectEntity):
    """Select entity to choose irrigation frequency type for a program."""

    _attr_icon = "mdi:calendar-sync"
    _attr_options = _FREQ_OPTIONS
    _attr_translation_key = "program_frequency"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, pid: int, program_name: str, freq_state: dict) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._freq_state = freq_state
        self._attr_name = f"{program_name} frequency"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_frequency"

    def _get_program(self) -> dict | None:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                return prog
        return None

    @property
    def current_option(self) -> str | None:
        prog = self._get_program()
        if not prog:
            return None
        return _freq_type_to_option(prog.get("frequency", {}))

    async def async_select_option(self, option: str) -> None:
        prog = self._get_program()
        current_freq = prog.get("frequency", {}) if prog else {}

        if option == "daily":
            freq = {"type": 0, "param": "0"}
        elif option == "every_n_days":
            if int(current_freq.get("type", -1)) == 1:
                param = str(current_freq.get("param", "2"))
            else:
                param = str(self._freq_state["interval"])
            freq = {"type": 1, "param": param}
        elif option == "odd_days":
            freq = {"type": 4, "param": "1"}
        elif option == "even_days":
            freq = {"type": 4, "param": "0"}
        elif option == "selected_days":
            if int(current_freq.get("type", -1)) == 2:
                param = str(current_freq.get("param", _days_to_param([True] * 7)))
            else:
                param = _days_to_param(self._freq_state["days"])
            freq = {"type": 2, "param": param}
        else:
            return

        try:
            await self.coordinator.client.action_set_program_frequency(self._pid, freq)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set frequency for program %s: %s", self._pid, err)


class RainMachineProgramCycleSoakSelect(RainMachineBaseEntity, SelectEntity):
    """Select entity for cycle & soak mode: off / auto / custom."""

    _attr_icon = "mdi:repeat-variant"
    _attr_options = _CYCLE_SOAK_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._attr_name = f"{program_name} cycle soak mode"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_cycle_soak_mode"

    def _get_program(self) -> dict | None:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                return prog
        return None

    @property
    def current_option(self) -> str | None:
        prog = self._get_program()
        if prog is None:
            return None
        if not prog.get("cs_on", False):
            return "off"
        return "custom" if int(prog.get("cycles", -1)) > 0 else "auto"

    async def async_select_option(self, option: str) -> None:
        try:
            if option == "off":
                await self.coordinator.client.action_set_cycle_soak(self._pid, False)
            elif option == "auto":
                await self.coordinator.client.action_set_cycle_soak(self._pid, True, -1, 0)
            elif option == "custom":
                cycles = int(self.hass.data[DOMAIN].get(
                    f"{self._entry.entry_id}_prog_{self._pid}_cs_cycles", 2
                ))
                soak_min = int(self.hass.data[DOMAIN].get(
                    f"{self._entry.entry_id}_prog_{self._pid}_cs_min", 0
                ))
                await self.coordinator.client.action_set_cycle_soak(
                    self._pid, True, cycles, soak_min * 60
                )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set cycle soak mode for program %s: %s", self._pid, err)


class RainMachineProgramZoneDurationTypeSelect(RainMachineBaseEntity, SelectEntity):
    """Select entity to set duration type for a zone in a program."""

    _attr_options = _DURATION_TYPE_OPTIONS
    _attr_translation_key = "zone_duration_type"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:timer-edit-outline"

    def __init__(
        self, coordinator, slow_coordinator, entry,
        pid: int, program_name: str, zid: int, zone_name: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._zid = zid
        self._slow_coordinator = slow_coordinator
        self._attr_name = f"{program_name} {zone_name} duration type"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_zone_{zid}_duration_type"

    def _get_wt(self) -> dict | None:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                for wt in prog.get("wateringTimes", []):
                    if wt["id"] == self._zid:
                        return wt
        return None

    @property
    def current_option(self) -> str | None:
        wt = self._get_wt()
        if wt is None:
            return None
        if not wt.get("active", False):
            return "not_set"
        if wt.get("duration", 0) > 0:
            return "custom"
        return "suggested"

    async def async_select_option(self, option: str) -> None:
        wt = self._get_wt()
        if wt is None:
            return

        try:
            if option == "suggested":
                await self.coordinator.client.action_set_zone_duration_type(
                    self._pid, self._zid, active=True, duration=0
                )
            elif option == "custom":
                current_duration = wt.get("duration", 0)
                if current_duration > 0:
                    await self.coordinator.client.action_set_zone_duration_type(
                        self._pid, self._zid, active=True
                    )
                else:
                    zprops = self._slow_coordinator.data.get("zone_properties", {}).get(self._zid, {})
                    ref_time = zprops.get("waterSense", {}).get("referenceTime", 0)
                    fallback = max(60, int(ref_time)) if ref_time > 0 else 600
                    await self.coordinator.client.action_set_zone_duration_type(
                        self._pid, self._zid, active=True, duration=fallback
                    )
            elif option == "not_set":
                await self.coordinator.client.action_set_zone_duration_type(
                    self._pid, self._zid, active=False
                )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error(
                "Failed to set duration type for program %s zone %s: %s",
                self._pid, self._zid, err,
            )
