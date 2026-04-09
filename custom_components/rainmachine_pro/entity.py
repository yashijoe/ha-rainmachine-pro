"""Base entity for RainMachine Pro."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RainMachineProCoordinator


class RainMachineBaseEntity(CoordinatorEntity):
    """Base entity for RainMachine Pro."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainMachineProCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self._entry = entry

    def _get_lang(self) -> str:
        """Return HA language prefix (it, en, de, fr, es)."""
        try:
            lang = self.hass.config.language or "en"
        except Exception:
            lang = "en"
        prefix = lang[:2].lower()
        return prefix if prefix in ("it", "en", "de", "fr", "es") else "en"

    @property
    def device_info(self) -> dict:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "RainMachine",
            "manufacturer": "RainMachine",
            "model": "Pro",
            "configuration_url": (
                f"https://{self._entry.data.get('host', '')}:"
                f"{self._entry.data.get('port', 8080)}"
            ),
        }
