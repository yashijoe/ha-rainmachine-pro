"""Binary sensor platform for RainMachine Pro."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RainMachineProCoordinator
from .entity import RainMachineBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    fast_coordinator = hass.data[DOMAIN][f"{entry.entry_id}_fast"]

    async_add_entities([
        RainMachineWateringActiveBinary(fast_coordinator, entry),
        RainMachineFlowSensorBinary(coordinator, entry),
        RainMachineFreezeRestriction(coordinator, entry),
        RainMachineHourlyRestriction(coordinator, entry),
        RainMachineMonthRestriction(coordinator, entry),
        RainMachineRainDelayRestriction(coordinator, entry),
        RainMachineWeekdayRestriction(coordinator, entry),
        RainMachineRainSensorBinary(coordinator, entry),
    ])


class _RainMachineBinaryBase(RainMachineBaseEntity, BinarySensorEntity):
    """Base binary sensor."""

    def __init__(self, coordinator, entry, unique_suffix: str) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"


class RainMachineWateringActiveBinary(_RainMachineBinaryBase):
    """Binary sensor: ON while any zone is watering (manual, program or single zone).

    Rides the fast coordinator so it tracks the same queue data (and the same
    latency) as the zone run switches.
    """

    _attr_name = "Watering active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:sprinkler-variant"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "watering_active")

    def _running_items(self) -> list:
        return [
            item
            for item in self.coordinator.data.get("queue", [])
            if item.get("running")
        ]

    @property
    def is_on(self) -> bool:
        return bool(self._running_items())

    @property
    def extra_state_attributes(self) -> dict:
        running = self._running_items()
        zone_names = {
            z.get("uid"): z.get("name")
            for z in self.coordinator.data.get("zones", [])
        }
        program_names = {
            p.get("uid"): p.get("name")
            for p in self.coordinator.data.get("programs", [])
        }
        attrs = {
            "zones": [zone_names.get(item.get("zid"), item.get("zid")) for item in running],
        }
        if running:
            pid = running[0].get("pid")
            attrs["program"] = program_names.get(pid, "manual") if pid else "manual"
            attrs["remaining"] = max((item.get("remaining", 0) for item in running), default=0)
        return attrs


class RainMachineFlowSensorBinary(_RainMachineBinaryBase):
    """Binary sensor: flow sensor enabled."""

    _attr_name = "Flow sensor"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:water-pump"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "flow_sensor")

    @property
    def is_on(self) -> bool:
        provision = self.coordinator.data.get("provision", {})
        return provision.get("system", {}).get("useFlowSensor", False)


class RainMachineFreezeRestriction(_RainMachineBinaryBase):
    """Binary sensor: freeze restriction active."""

    _attr_name = "Freeze restrictions"
    _attr_device_class = BinarySensorDeviceClass.COLD
    _attr_icon = "mdi:snowflake-alert"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "freeze_restrictions")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("restrictions_currently", {}).get("freeze", False)


class RainMachineHourlyRestriction(_RainMachineBinaryBase):
    """Binary sensor: hourly restriction active."""

    _attr_name = "Hourly restrictions"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:clock-alert-outline"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "hourly_restrictions")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("restrictions_currently", {}).get("hourly", False)


class RainMachineMonthRestriction(_RainMachineBinaryBase):
    """Binary sensor: monthly restriction active."""

    _attr_name = "Month restrictions"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:calendar-remove"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "month_restrictions")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("restrictions_currently", {}).get("month", False)


class RainMachineRainDelayRestriction(_RainMachineBinaryBase):
    """Binary sensor: rain delay restriction active."""

    _attr_name = "Rain delay restrictions"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:weather-rainy"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "rain_delay_restrictions")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("restrictions_currently", {}).get("rainDelay", False)


class RainMachineWeekdayRestriction(_RainMachineBinaryBase):
    """Binary sensor: weekday restriction active."""

    _attr_name = "Weekday restrictions"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:calendar-week"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "weekday_restrictions")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("restrictions_currently", {}).get("weekDay", False)


class RainMachineRainSensorBinary(_RainMachineBinaryBase):
    """Binary sensor: physical rain sensor active."""

    _attr_name = "Rain sensor"
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_icon = "mdi:weather-pouring"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "rain_sensor")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("restrictions_currently", {}).get("rainSensor", False)
