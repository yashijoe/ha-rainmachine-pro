"""API client for RainMachine Pro."""

import asyncio
import json
import logging
import ssl

import aiohttp

_LOGGER = logging.getLogger(__name__)


class RainMachineApiError(Exception):
    """Base exception for API errors."""


class RainMachineAuthError(RainMachineApiError):
    """Authentication error."""


class RainMachineConnectionError(RainMachineApiError):
    """Connection error."""


def _parse_pre_json(text: str) -> dict:
    """Parse JSON that may be wrapped in <pre> tags."""
    text = text.strip()
    if text.startswith("<pre>") and text.endswith("</pre>"):
        text = text[5:-6].strip()
    return json.loads(text)


class RainMachineClient:
    """Client to interact with RainMachine local API."""

    def __init__(self, host: str, port: int, password: str, timeout: int = 20) -> None:
        """Initialize the client."""
        self._host = host
        self._port = port
        self._password = password
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._base_url = f"https://{host}:{port}/api/4"
        self._token: str | None = None
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _url(self, path: str, query: str = "format") -> str:
        """Build URL with token."""
        sep = "&" if "?" in path else "?"
        base = f"{self._base_url}/{path}"
        if query:
            base = f"{base}?{query}"
        if self._token:
            sep = "&" if "?" in base else "?"
            base = f"{base}{sep}access_token={self._token}"
        return base

    async def authenticate(self, session: aiohttp.ClientSession) -> bool:
        """Authenticate and get token."""
        url = f"{self._base_url}/auth/login"
        payload = json.dumps({"pwd": self._password, "remember": 1})
        headers = {"Content-Type": "application/json"}

        try:
            async with session.post(
                url, data=payload, headers=headers,
                ssl=self._ssl_context, timeout=self._timeout
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                data = _parse_pre_json(text)
                self._token = data.get("access_token")
                if not self._token:
                    raise RainMachineAuthError("No access token received")
                return True
        except aiohttp.ClientResponseError as err:
            raise RainMachineAuthError(f"Auth failed: {err.status}") from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise RainMachineConnectionError(f"Connection failed: {err}") from err

    async def _get(self, session: aiohttp.ClientSession, path: str, query: str = "format") -> dict:
        """Make GET request."""
        url = self._url(path, query)
        try:
            async with session.get(
                url, ssl=self._ssl_context, timeout=self._timeout
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                return _parse_pre_json(text)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise RainMachineConnectionError(f"GET {path} failed: {err}") from err

    async def _post(self, session: aiohttp.ClientSession, path: str, payload: dict) -> dict:
        """Make POST request."""
        url = self._url(path, query="")
        headers = {"Content-Type": "application/json"}
        try:
            async with session.post(
                url, data=json.dumps(payload), headers=headers,
                ssl=self._ssl_context, timeout=self._timeout
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                return _parse_pre_json(text)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise RainMachineConnectionError(f"POST {path} failed: {err}") from err

    async def get_parsers(self, session: aiohttp.ClientSession) -> list:
        """Get parser data."""
        data = await self._get(session, "parser")
        return data.get("parsers", [])

    async def get_watering_today(self, session: aiohttp.ClientSession) -> dict:
        """Get today watering summary."""
        data = await self._get(session, "watering/log")
        return data

    async def get_watering_details(self, session: aiohttp.ClientSession) -> dict:
        """Get watering details by zone."""
        data = await self._get(session, "watering/log/details")
        return data

    async def get_forecast(self, session: aiohttp.ClientSession) -> dict:
        """Get forecast conditions."""
        data = await self._get(session, "mixer", query="format=json")
        return data

    async def get_rain_delay(self, session: aiohttp.ClientSession) -> dict:
        """Get rain delay status."""
        data = await self._get(session, "restrictions/raindelay")
        return data

    async def get_zones(self, session: aiohttp.ClientSession) -> list:
        """Get zone configuration."""
        data = await self._get(session, "zone")
        return data.get("zones", [])

    async def set_rain_delay(self, session: aiohttp.ClientSession, days: int) -> dict:
        """Set rain delay in days."""
        return await self._post(
            session, "restrictions/raindelay", {"rainDelay": days}
        )

    async def test_connection(self) -> bool:
        """Test if connection works."""
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            return True

    async def fetch_zones(self) -> list:
        """Fetch zone list (used during setup)."""
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            return await self.get_zones(session)

    async def fetch_all_data(self) -> dict:
        """Fetch all data in one call."""
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)

            data = {}
            try:
                data["parsers"] = await self.get_parsers(session)
            except RainMachineApiError as err:
                _LOGGER.warning("Failed to get parsers: %s", err)
                data["parsers"] = []

            try:
                data["watering"] = await self.get_watering_today(session)
            except RainMachineApiError as err:
                _LOGGER.warning("Failed to get watering: %s", err)
                data["watering"] = {}

            try:
                data["details"] = await self.get_watering_details(session)
            except RainMachineApiError as err:
                _LOGGER.warning("Failed to get zone details: %s", err)
                data["details"] = {}

            try:
                data["forecast"] = await self.get_forecast(session)
            except RainMachineApiError as err:
                _LOGGER.warning("Failed to get forecast: %s", err)
                data["forecast"] = {}

            try:
                data["raindelay"] = await self.get_rain_delay(session)
            except RainMachineApiError as err:
                _LOGGER.warning("Failed to get rain delay: %s", err)
                data["raindelay"] = {}

            return data
