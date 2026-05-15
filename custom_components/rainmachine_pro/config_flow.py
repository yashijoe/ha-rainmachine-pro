"""Config flow for RainMachine Pro integration."""

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import RainMachineClient, RainMachineAuthError, RainMachineConnectionError
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST,
    CONF_TIMEOUT,
    CONF_ZONES,
    CONF_PROGRAMS,
    CONF_PARSERS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_FAST,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


def _parser_schema_key(description: str) -> str:
    """Convert a parser description to a readable schema key prefix."""
    return re.sub(r"[^a-z0-9]+", "_", description.lower()).strip("_") or "parser"


def _parser_display_name(parser: dict) -> str:
    """Return parser name with trailing 'Parser' word stripped."""
    name = parser.get("name", "")
    stripped = re.sub(r"[\s_-]*[Pp]arser\s*$", "", name).strip()
    return stripped or name


class RainMachineProConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RainMachine Pro."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._user_input: dict[str, Any] = {}
        self._available_zones: list[dict] = []
        self._available_programs: list[dict] = []
        self._available_parsers: list[dict] = []
        self._zone_config: dict = {}
        self._program_config: dict = {}
        self._parser_key_map: dict[str, str] = {}  # uid_str -> schema key prefix

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - connection details."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            password = user_input[CONF_PASSWORD]
            timeout = user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

            client = RainMachineClient(host, port, password, timeout)
            try:
                await client.test_connection()
                self._available_zones = await client.fetch_zones()
                self._available_programs = await client.fetch_programs()
                self._available_parsers = await client.fetch_parsers()
            except RainMachineAuthError:
                errors["base"] = "invalid_auth"
            except RainMachineConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._user_input = user_input
                return await self.async_step_zones()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(int, vol.Range(min=1, max=60)),
                    vol.Optional(
                        CONF_SCAN_INTERVAL_FAST, default=DEFAULT_SCAN_INTERVAL_FAST
                    ): vol.All(int, vol.Range(min=5, max=60)),
                    vol.Optional(
                        CONF_TIMEOUT, default=DEFAULT_TIMEOUT
                    ): vol.All(int, vol.Range(min=5, max=120)),
                }
            ),
            errors=errors,
        )

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle zone selection step."""
        if user_input is not None:
            zones = {}
            for zone in self._available_zones:
                uid = str(zone["uid"])
                rm_name = zone.get("name", f"Zone {uid}")
                enabled = user_input.get(f"zone_{uid}_enabled", False)
                custom_name = user_input.get(f"zone_{uid}_name", rm_name)
                zones[uid] = {
                    "name": custom_name,
                    "rm_name": rm_name,
                    "enabled": enabled,
                }
            self._zone_config = zones
            return await self.async_step_programs()

        schema_dict = {}
        for zone in self._available_zones:
            uid = zone["uid"]
            rm_name = zone.get("name", f"Zone {uid}")
            active = zone.get("active", False)
            schema_dict[vol.Optional(f"zone_{uid}_enabled", default=active)] = bool
            schema_dict[vol.Optional(f"zone_{uid}_name", default=rm_name)] = str

        return self.async_show_form(
            step_id="zones",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"zone_count": str(len(self._available_zones))},
        )

    async def async_step_programs(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle program selection step."""
        if user_input is not None:
            programs = {}
            for program in self._available_programs:
                pid = str(program["uid"])
                rm_name = program.get("name", f"Program {pid}")
                enabled = user_input.get(f"program_{pid}_enabled", True)
                name = user_input.get(f"program_{pid}_name", rm_name)
                programs[pid] = {"name": name, "rm_name": rm_name, "enabled": enabled}
            self._program_config = programs
            return await self.async_step_parsers()

        schema_dict = {}
        for program in self._available_programs:
            pid = program["uid"]
            rm_name = program.get("name", f"Program {pid}")
            schema_dict[vol.Optional(f"program_{pid}_name", default=rm_name)] = str
            schema_dict[vol.Optional(f"program_{pid}_enabled", default=True)] = bool

        return self.async_show_form(
            step_id="programs",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"program_count": str(len(self._available_programs))},
        )

    async def async_step_parsers(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle parser selection step."""
        if user_input is not None or not self._available_parsers:
            parsers = {}
            for parser in self._available_parsers:
                uid = str(parser.get("uid", ""))
                if not uid:
                    continue
                desc = parser.get("description", f"Parser {uid}")
                display = _parser_display_name(parser)
                key = self._parser_key_map.get(uid, _parser_schema_key(display))
                has_run = parser.get("lastRun") not in (None, "unknown", "")
                enabled = (user_input or {}).get(f"{key}_enabled", has_run)
                name = (user_input or {}).get(f"{key}_name", display)
                parsers[uid] = {"description": desc, "name": name, "enabled": bool(enabled)}

            host = self._user_input[CONF_HOST]
            await self.async_set_unique_id(f"rainmachine_pro_{host}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"RainMachine ({host})",
                data={
                    CONF_HOST: host,
                    CONF_PORT: self._user_input[CONF_PORT],
                    CONF_PASSWORD: self._user_input[CONF_PASSWORD],
                },
                options={
                    CONF_SCAN_INTERVAL: self._user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                    CONF_SCAN_INTERVAL_FAST: self._user_input.get(
                        CONF_SCAN_INTERVAL_FAST, DEFAULT_SCAN_INTERVAL_FAST
                    ),
                    CONF_TIMEOUT: self._user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    CONF_ZONES: self._zone_config,
                    CONF_PROGRAMS: self._program_config,
                    CONF_PARSERS: parsers,
                },
            )

        # Build schema with name-based keys so HA renders readable labels
        schema_dict = {}
        used_keys: set[str] = set()
        self._parser_key_map = {}
        for parser in self._available_parsers:
            uid = str(parser.get("uid", ""))
            if not uid:
                continue
            display = _parser_display_name(parser)
            key = _parser_schema_key(display)
            if key in used_keys:
                key = f"{key}_{uid}"
            used_keys.add(key)
            self._parser_key_map[uid] = key
            has_run = parser.get("lastRun") not in (None, "unknown", "")
            schema_dict[vol.Optional(f"{key}_name", default=display)] = str
            schema_dict[vol.Optional(f"{key}_enabled", default=has_run)] = bool

        return self.async_show_form(
            step_id="parsers",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"parser_count": str(len(self._available_parsers))},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return RainMachineProOptionsFlow(config_entry)


class RainMachineProOptionsFlow(OptionsFlow):
    """Handle options flow for RainMachine Pro."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._general_options: dict[str, Any] = {}
        self._zone_options: dict[str, Any] = {}
        self._program_options: dict[str, Any] = {}
        self._fresh_parsers_map: dict[str, dict] = {}
        self._parser_key_map: dict[str, str] = {}  # uid_str -> schema key prefix

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the main options."""
        if user_input is not None:
            self._general_options = user_input
            return await self.async_step_zones()

        current = self._config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=1, max=60)),
                    vol.Optional(
                        CONF_SCAN_INTERVAL_FAST,
                        default=current.get(CONF_SCAN_INTERVAL_FAST, DEFAULT_SCAN_INTERVAL_FAST),
                    ): vol.All(int, vol.Range(min=5, max=60)),
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=current.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ): vol.All(int, vol.Range(min=5, max=120)),
                }
            ),
        )

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage zone selection and names."""
        if user_input is not None:
            current_zones = self._config_entry.options.get(CONF_ZONES, {})
            zones = {}
            for uid, zone_data in current_zones.items():
                enabled = user_input.get(f"zone_{uid}_enabled", zone_data.get("enabled", False))
                custom_name = user_input.get(f"zone_{uid}_name", zone_data.get("name", f"Zone {uid}"))
                zones[uid] = {
                    "name": custom_name,
                    "rm_name": zone_data.get("rm_name", f"Zone {uid}"),
                    "enabled": enabled,
                }
            self._zone_options = zones
            return await self.async_step_programs_options()

        current_zones = self._config_entry.options.get(CONF_ZONES, {})

        # If no zones stored yet, try to fetch from device
        if not current_zones:
            try:
                host = self._config_entry.data[CONF_HOST]
                port = self._config_entry.data[CONF_PORT]
                password = self._config_entry.data[CONF_PASSWORD]
                timeout = self._config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
                client = RainMachineClient(host, port, password, timeout)
                rm_zones = await client.fetch_zones()
                for zone in rm_zones:
                    uid = str(zone["uid"])
                    current_zones[uid] = {
                        "name": zone.get("name", f"Zone {uid}"),
                        "rm_name": zone.get("name", f"Zone {uid}"),
                        "enabled": zone.get("active", False),
                    }
            except Exception:
                _LOGGER.warning("Could not fetch zones from RainMachine")

        schema_dict = {}
        for uid in sorted(current_zones.keys(), key=int):
            zone_data = current_zones[uid]
            schema_dict[
                vol.Optional(
                    f"zone_{uid}_enabled",
                    default=zone_data.get("enabled", False),
                )
            ] = bool
            schema_dict[
                vol.Optional(
                    f"zone_{uid}_name",
                    default=zone_data.get("name", f"Zone {uid}"),
                )
            ] = str

        return self.async_show_form(
            step_id="zones",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_programs_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage program selection."""
        if user_input is not None:
            current_programs = self._config_entry.options.get(CONF_PROGRAMS, {})
            programs = {}
            for pid, prog_data in current_programs.items():
                rm_name = prog_data.get("rm_name", prog_data.get("name", f"Program {pid}"))
                enabled = user_input.get(f"program_{pid}_enabled", prog_data.get("enabled", True))
                name = user_input.get(f"program_{pid}_name", prog_data.get("name", rm_name))
                programs[pid] = {"name": name, "rm_name": rm_name, "enabled": enabled}
            self._program_options = programs
            return await self.async_step_parsers_options()

        current_programs = self._config_entry.options.get(CONF_PROGRAMS, {})

        if not current_programs:
            try:
                host = self._config_entry.data[CONF_HOST]
                port = self._config_entry.data[CONF_PORT]
                password = self._config_entry.data[CONF_PASSWORD]
                timeout = self._config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
                client = RainMachineClient(host, port, password, timeout)
                rm_programs = await client.fetch_programs()
                for prog in rm_programs:
                    pid = str(prog["uid"])
                    rm_name = prog.get("name", f"Program {pid}")
                    current_programs[pid] = {
                        "name": rm_name,
                        "rm_name": rm_name,
                        "enabled": True,
                    }
            except Exception:
                _LOGGER.warning("Could not fetch programs from RainMachine")

        schema_dict = {}
        for pid in sorted(current_programs.keys(), key=int):
            prog_data = current_programs[pid]
            rm_name = prog_data.get("rm_name", prog_data.get("name", f"Program {pid}"))
            schema_dict[
                vol.Optional(f"program_{pid}_name", default=prog_data.get("name", rm_name))
            ] = str
            schema_dict[
                vol.Optional(f"program_{pid}_enabled", default=prog_data.get("enabled", True))
            ] = bool

        return self.async_show_form(
            step_id="programs_options",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_parsers_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage parser entity visibility."""
        stored_parsers = self._config_entry.options.get(CONF_PARSERS, {})
        # Migrate old list format gracefully
        if isinstance(stored_parsers, list):
            stored_parsers = {}

        if user_input is not None:
            all_uid_strs = set(
                list(self._fresh_parsers_map.keys()) + list(stored_parsers.keys())
            )
            parsers = {}
            for uid_str in all_uid_strs:
                fresh = self._fresh_parsers_map.get(uid_str, {})
                stored = stored_parsers.get(uid_str, {})
                desc = fresh.get("description") or (
                    stored.get("description") if isinstance(stored, dict) else f"Parser {uid_str}"
                )
                display = (
                    _parser_display_name(fresh) if fresh.get("name")
                    else (stored.get("name") if isinstance(stored, dict) else None) or desc
                )
                key = self._parser_key_map.get(uid_str, _parser_schema_key(display))
                default_enabled = stored.get("enabled", True) if isinstance(stored, dict) else True
                default_name = (
                    (stored.get("name") or display)
                    if isinstance(stored, dict) else display
                )
                enabled = user_input.get(f"{key}_enabled", default_enabled)
                name = user_input.get(f"{key}_name", default_name)
                parsers[uid_str] = {"description": desc, "name": name, "enabled": bool(enabled)}

            options = {
                **self._general_options,
                CONF_ZONES: self._zone_options,
                CONF_PROGRAMS: self._program_options,
                CONF_PARSERS: parsers,
            }
            return self.async_create_entry(title="", data=options)

        # Fetch fresh parser list from device
        try:
            host = self._config_entry.data[CONF_HOST]
            port = self._config_entry.data[CONF_PORT]
            password = self._config_entry.data[CONF_PASSWORD]
            timeout = self._config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            client = RainMachineClient(host, port, password, timeout)
            fresh_parsers = await client.fetch_parsers()
            self._fresh_parsers_map = {
                str(p["uid"]): p for p in fresh_parsers if p.get("uid")
            }
        except Exception:
            _LOGGER.warning("Could not fetch parsers from RainMachine for options")
            self._fresh_parsers_map = {}

        # Union of fresh + previously stored UIDs
        all_uid_strs = sorted(
            set(list(self._fresh_parsers_map.keys()) + list(stored_parsers.keys())),
            key=lambda x: int(x) if x.isdigit() else 0,
        )

        if not all_uid_strs:
            return await self.async_step_parsers_options(user_input={})

        # Build schema with name-based keys
        schema_dict = {}
        used_keys: set[str] = set()
        self._parser_key_map = {}
        for uid_str in all_uid_strs:
            fresh = self._fresh_parsers_map.get(uid_str, {})
            stored = stored_parsers.get(uid_str, {})
            desc = fresh.get("description") or (
                stored.get("description") if isinstance(stored, dict) else f"Parser {uid_str}"
            )
            display = (
                _parser_display_name(fresh) if fresh.get("name")
                else (stored.get("name") if isinstance(stored, dict) else None) or desc
            )
            key = _parser_schema_key(display)
            if key in used_keys:
                key = f"{key}_{uid_str}"
            used_keys.add(key)
            self._parser_key_map[uid_str] = key

            default_enabled = (
                stored.get("enabled", True) if isinstance(stored, dict)
                else fresh.get("lastRun") not in (None, "unknown", "")
            )
            default_name = (
                (stored.get("name") or display)
                if isinstance(stored, dict) else display
            )
            schema_dict[vol.Optional(f"{key}_name", default=default_name)] = str
            schema_dict[vol.Optional(f"{key}_enabled", default=default_enabled)] = bool

        return self.async_show_form(
            step_id="parsers_options",
            data_schema=vol.Schema(schema_dict),
        )
