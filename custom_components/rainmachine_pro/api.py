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
                ssl=self._ssl_context, timeout=self._timeout,
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
                url, ssl=self._ssl_context, timeout=self._timeout,
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
                ssl=self._ssl_context, timeout=self._timeout,
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                return _parse_pre_json(text)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise RainMachineConnectionError(f"POST {path} failed: {err}") from err

    # -------------------------------------------------------------------------
    # Data fetch methods (used by coordinator with shared session)
    # -------------------------------------------------------------------------

    async def get_parsers(self, session: aiohttp.ClientSession) -> list:
        data = await self._get(session, "parser")
        return data.get("parsers", [])

    async def get_watering_today(self, session: aiohttp.ClientSession) -> dict:
        return await self._get(session, "watering/log")

    async def get_watering_details(self, session: aiohttp.ClientSession) -> dict:
        return await self._get(session, "watering/log/details")

    async def get_forecast(self, session: aiohttp.ClientSession) -> dict:
        return await self._get(session, "mixer", query="format=json")

    async def get_rain_delay(self, session: aiohttp.ClientSession) -> dict:
        return await self._get(session, "restrictions/raindelay")

    async def get_zones(self, session: aiohttp.ClientSession) -> list:
        data = await self._get(session, "zone")
        return data.get("zones", [])

    async def get_programs(self, session: aiohttp.ClientSession) -> list:
        data = await self._get(session, "program")
        return data.get("programs", [])

    async def get_restrictions_currently(self, session: aiohttp.ClientSession) -> dict:
        return await self._get(session, "restrictions/currently")

    async def get_restrictions_global(self, session: aiohttp.ClientSession) -> dict:
        return await self._get(session, "restrictions/global")

    async def get_watering_queue(self, session: aiohttp.ClientSession) -> list:
        data = await self._get(session, "watering/queue")
        return data.get("queue", [])

    async def get_provision(self, session: aiohttp.ClientSession) -> dict:
        return await self._get(session, "provision")

    async def get_machine_update(self, session: aiohttp.ClientSession) -> dict:
        return await self._get(session, "machine/update")

    # -------------------------------------------------------------------------
    # Action methods (each opens its own session)
    # -------------------------------------------------------------------------

    async def _action(self, path: str, payload: dict) -> dict:
        """Execute a POST action with its own authenticated session."""
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            return await self._post(session, path, payload)

    async def set_rain_delay(self, session: aiohttp.ClientSession, days: int) -> dict:
        return await self._post(session, "restrictions/raindelay", {"rainDelay": days})

    async def action_start_zone(self, zid: int, duration: int = 600) -> dict:
        """Start a zone for `duration` seconds (default 10 min)."""
        return await self._action(f"zone/{zid}/start", {"time": duration})

    async def action_stop_zone(self, zid: int) -> dict:
        return await self._action(f"zone/{zid}/stop", {"zid": zid})

    async def action_set_zone_active(self, zid: int, active: bool) -> dict:
        return await self._action(f"zone/{zid}/properties", {"active": active})

    async def action_start_program(self, pid: int) -> dict:
        return await self._action(f"program/{pid}/start", {"pid": pid})

    async def action_stop_program(self, pid: int) -> dict:
        return await self._action(f"program/{pid}/stop", {"pid": pid})

    async def action_set_program_active(self, pid: int, active: bool) -> dict:
        return await self._action(f"program/{pid}", {"active": active})

    async def action_set_global_restriction(self, payload: dict) -> dict:
        return await self._action("restrictions/global", payload)

    async def action_reboot(self) -> dict:
        return await self._action("machine/reboot", {})

    async def action_start_update(self) -> dict:
        return await self._action("machine/update", {})

    # -------------------------------------------------------------------------
    # Setup helpers
    # -------------------------------------------------------------------------

    async def test_connection(self) -> bool:
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            return True

    async def fetch_zones(self) -> list:
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            return await self.get_zones(session)

    async def fetch_programs(self) -> list:
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            return await self.get_programs(session)

    async def fetch_parsers(self) -> list:
        """Fetch parser list for setup/options flow."""
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            return await self.get_parsers(session)

    async def fetch_fast_data(self) -> dict:
        """Fetch only zones, programs and queue (for fast polling)."""
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            data = {}
            for key, coro in [
                ("zones",    self.get_zones(session)),
                ("programs", self.get_programs(session)),
                ("queue",    self.get_watering_queue(session)),
            ]:
                try:
                    data[key] = await coro
                except RainMachineApiError as err:
                    _LOGGER.warning("Fast fetch %s failed: %s", key, err)
                    data[key] = []
            return data

    async def fetch_all_data(self) -> dict:
        """Fetch all data in one authenticated session."""
        async with aiohttp.ClientSession() as session:
            await self.authenticate(session)
            data = {}

            for key, coro in [
                ("parsers",                  self.get_parsers(session)),
                ("watering",                 self.get_watering_today(session)),
                ("details",                  self.get_watering_details(session)),
                ("forecast",                 self.get_forecast(session)),
                ("raindelay",                self.get_rain_delay(session)),
                ("zones",                    self.get_zones(session)),
                ("programs",                 self.get_programs(session)),
                ("restrictions_currently",   self.get_restrictions_currently(session)),
                ("restrictions_global",      self.get_restrictions_global(session)),
                ("queue",                    self.get_watering_queue(session)),
                ("provision",                self.get_provision(session)),
                ("machine_update",           self.get_machine_update(session)),
            ]:
                try:
                    data[key] = await coro
                except RainMachineApiError as err:
                    _LOGGER.warning("Failed to fetch %s: %s", key, err)
                    data[key] = {} if key not in ("parsers", "zones", "programs", "queue") else []

            return data
