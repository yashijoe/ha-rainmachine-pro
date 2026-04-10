"""Config flow for RainMachine Pro integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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
    AVAILABLE_PARSERS,
)

_LOGGER = logging.getLogger(__name__)


class RainMachineProConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RainMachine Pro."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._user_input: dict[str, Any] = {}
        self._available_zones: list[dict] = []
        self._available_programs: list[dict] = []
        self._zone_config: dict = {}

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
                    vol.Required(CONF_HOST, default="192.168.50.2"): str,
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
                    CONF_PROGRAMS: programs,
                    CONF_PARSERS: list(AVAILABLE_PARSERS.keys()),
                },
            )

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
                    vol.Optional(
                        CONF_PARSERS,
                        default=current.get(CONF_PARSERS, list(AVAILABLE_PARSERS.keys())),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v["friendly_name"]}
                                for k, v in AVAILABLE_PARSERS.items()
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
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
            options = {
                **self._general_options,
                CONF_ZONES: self._zone_options,
                CONF_PROGRAMS: programs,
            }
            return self.async_create_entry(title="", data=options)

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
