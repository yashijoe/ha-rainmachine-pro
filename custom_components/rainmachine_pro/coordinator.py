"""Data update coordinator for RainMachine Pro."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RainMachineClient, RainMachineApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RainMachineProCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from RainMachine."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RainMachineClient,
        scan_interval: int,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        """Fetch data from RainMachine."""
        try:
            return await self.client.fetch_all_data()
        except RainMachineApiError as err:
            raise UpdateFailed(f"Error fetching RainMachine data: {err}") from err


class RainMachineProFastCoordinator(DataUpdateCoordinator):
    """Fast coordinator — polls only queue, zones and programs every N seconds."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RainMachineClient,
        scan_interval_fast: int,
    ) -> None:
        """Initialize fast coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_fast",
            update_interval=timedelta(seconds=scan_interval_fast),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        """Fetch fast data from RainMachine."""
        try:
            return await self.client.fetch_fast_data()
        except RainMachineApiError as err:
            raise UpdateFailed(f"Fast update failed: {err}") from err
