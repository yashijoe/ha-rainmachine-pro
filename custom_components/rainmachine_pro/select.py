"""Select platform for RainMachine Pro."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PROGRAMS
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)

_FREEZE_TEMPS = [str(t) for t in range(-7, 5)]

# Internal keys — translated via entity.select.program_frequency.state in translations/
_FREQ_OPTIONS = ["daily", "every_n_days", "odd_days", "even_days", "selected_days"]

# Bit values for Mon(0)..Sun(6) per API doc "SSFTWTM0" bitmask
_DAY_BITS = [2, 4, 8, 16, 32, 64, 128]


def _param_to_days(param) -> list:
    p = int(param)
    return [(p & bit) != 0 for bit in _DAY_BITS]


def _days_to_param(days: list) -> int:
    return sum(bit for bit, active in zip(_DAY_BITS, days) if active)


def _freq_type_to_option(freq: dict) -> str:
    ftype = int(freq.get("type", 0))
    if ftype == 1:
        return "every_n_days"
    if ftype == 4:
        return "odd_days" if int(freq.get("param", 0)) == 1 else "even_days"
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
                freq_state["days"] = _param_to_days(freq.get("param", 0))
            hass.data[DOMAIN][freq_key] = freq_state
        else:
            freq_state = hass.data[DOMAIN][freq_key]

        entities.append(
            RainMachineProgramFrequencySelect(fast_coordinator, entry, pid, name, freq_state)
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
            freq = {"type": 0, "param": 0}
        elif option == "every_n_days":
            if int(current_freq.get("type", -1)) == 1:
                param = int(current_freq.get("param", 2))
            else:
                param = self._freq_state["interval"]
            freq = {"type": 1, "param": param}
        elif option == "odd_days":
            freq = {"type": 4, "param": 1}
        elif option == "even_days":
            freq = {"type": 4, "param": 0}
        elif option == "selected_days":
            if int(current_freq.get("type", -1)) == 2:
                param = int(current_freq.get("param", 0))
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
