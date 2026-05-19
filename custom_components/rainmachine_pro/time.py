"""Time platform for RainMachine Pro — program start times."""

import logging
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PROGRAMS
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up time entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})
    entities = []
    for program in coordinator.data.get("programs", []):
        pid = program["uid"]
        prog_cfg = enabled_programs.get(str(pid), {})
        if not prog_cfg.get("enabled", True):
            continue
        name = prog_cfg.get("name") or program.get("name", f"Program {pid}")
        entities.append(RainMachineProgramStartTime(coordinator, entry, pid, name))
    async_add_entities(entities)


class RainMachineProgramStartTime(RainMachineBaseEntity, TimeEntity):
    """Editable start time for a RainMachine program."""

    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator, entry, pid: int, program_name: str) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._attr_name = f"{program_name} start time"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_start_time"

    def _get_program(self) -> dict | None:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                return prog
        return None

    @property
    def native_value(self) -> dt_time | None:
        prog = self._get_program()
        if not prog:
            return None
        start_time = prog.get("startTime")
        if start_time is None:
            return None
        try:
            minutes = int(start_time)
            h, m = divmod(minutes, 60)
            return dt_time(h, m)
        except (ValueError, TypeError):
            return None

    async def async_set_value(self, value: dt_time) -> None:
        minutes = value.hour * 60 + value.minute
        await self.coordinator.client.action_set_program_start_time(self._pid, minutes)
        await self.coordinator.async_request_refresh()
