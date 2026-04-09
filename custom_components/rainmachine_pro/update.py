"""Update platform for RainMachine Pro."""

import logging

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
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
    """Set up update entity from a config entry."""
    coordinator: RainMachineProCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RainMachineFirmwareUpdate(coordinator, entry)])


class RainMachineFirmwareUpdate(RainMachineBaseEntity, UpdateEntity):
    """Firmware update entity for RainMachine."""

    _attr_name = "Firmware"
    _attr_icon = "mdi:package-up"
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, coordinator: RainMachineProCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_firmware_update"

    @property
    def _update_data(self) -> dict:
        return self.coordinator.data.get("machine_update", {})

    @property
    def installed_version(self) -> str | None:
        """Return installed firmware version (hardware version as proxy)."""
        hw = self.coordinator.data.get("provision", {}).get("system", {}).get(
            "hardwareVersion"
        )
        if hw is not None:
            return f"hw{hw}"
        return "unknown"

    @property
    def latest_version(self) -> str | None:
        """Return latest version: same as installed if no update available."""
        if self._update_data.get("update", False):
            return "update_available"
        return self.installed_version

    @property
    def release_summary(self) -> str | None:
        """Return last update check timestamp."""
        return self._update_data.get("lastUpdateCheck")

    async def async_install(self, version: str | None, backup: bool, **kwargs) -> None:
        """Trigger firmware update."""
        try:
            await self.coordinator.client.action_start_update()
            _LOGGER.info("RainMachine firmware update started")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to start firmware update: %s", err)
