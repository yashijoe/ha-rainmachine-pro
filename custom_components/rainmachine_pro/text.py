"""Text platform for RainMachine Pro — zone custom durations in MM:SS format."""

import logging
import re

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_PROGRAMS, CONF_ZONES
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)

_PATTERN = re.compile(r'^(\d{1,3}):([0-5]\d)$')


def _seconds_to_mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _mmss_to_seconds(value: str) -> int | None:
    m = _PATTERN.match(value.strip())
    if not m:
        return None
    total = int(m.group(1)) * 60 + int(m.group(2))
    if total < 1 or total > 17999:
        return None
    return total


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]
    enabled_programs = entry.options.get(CONF_PROGRAMS, {})
    zones_config = entry.options.get(CONF_ZONES, {})
    entities = []

    for program in fast_coordinator.data.get("programs", []):
        pid = program["uid"]
        prog_cfg = enabled_programs.get(str(pid), {})
        if not prog_cfg.get("enabled", True):
            continue
        name = prog_cfg.get("name") or program.get("name", f"Program {pid}")

        for wt in program.get("wateringTimes", []):
            zid = wt["id"]
            zone_cfg = zones_config.get(str(zid), {})
            if not zone_cfg.get("enabled", False):
                continue
            zone_name = zone_cfg.get("name") or wt.get("name", f"Zone {zid}")
            entities.append(
                RainMachineProgramZoneDurationText(
                    fast_coordinator, entry, pid, name, zid, zone_name
                )
            )

    async_add_entities(entities)


class RainMachineProgramZoneDurationText(RainMachineBaseEntity, TextEntity):
    """Text entity: custom duration (MM:SS) for a zone in a program."""

    _attr_icon = "mdi:timer-edit-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min = 4
    _attr_native_max = 6
    _attr_pattern = r'^\d{1,3}:[0-5]\d$'

    def __init__(
        self, coordinator, entry, pid: int, prog_name: str, zid: int, zone_name: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._pid = pid
        self._zid = zid
        self._attr_name = f"{prog_name} {zone_name} custom duration"
        self._attr_unique_id = f"{entry.entry_id}_program_{pid}_zone_{zid}_custom_duration"

    def _get_duration(self) -> int:
        for prog in self.coordinator.data.get("programs", []):
            if prog["uid"] == self._pid:
                for wt in prog.get("wateringTimes", []):
                    if wt["id"] == self._zid:
                        return wt.get("duration", 0)
        return 0

    @property
    def native_value(self) -> str:
        return _seconds_to_mmss(self._get_duration())

    async def async_set_value(self, value: str) -> None:
        total = _mmss_to_seconds(value)
        if total is None:
            _LOGGER.error(
                "Invalid duration '%s' for program %s zone %s — expected M:SS..MMM:SS, range 0:01-299:59",
                value, self._pid, self._zid,
            )
            return
        try:
            await self.coordinator.client.action_set_zone_duration_type(
                self._pid, self._zid, active=True, duration=total
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error(
                "Failed to set custom duration for program %s zone %s: %s",
                self._pid, self._zid, err,
            )
