"""Config flow for Enphase Envoy integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_TOKEN
from homeassistant.const import CONF_USERNAME
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_SERIAL_NUMBER
from .const import CONF_UPDATE_INTERVAL
from .const import DEFAULT_UPDATE_INTERVAL
from .const import DOMAIN
from .const import LOGGER
from .envoy_reader import EnvoyReader

ENVOY = "Envoy"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Envoy."""

    VERSION = 1

    def __init__(self):
        """Initialize an envoy flow."""
        self.ip_address = None
        self.username = None
        self._reauth_entry = None

    @callback
    def _async_generate_schema(self):
        """Generate schema."""
        schema = {}

        if self.ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = vol.In(
                [self.ip_address]
            )
        else:
            schema[vol.Required(CONF_HOST)] = str

        schema[vol.Required(CONF_USERNAME, default=self.username or "envoy")] = str
        schema[vol.Required(CONF_PASSWORD, default="")] = str
        schema[vol.Required(CONF_SERIAL_NUMBER, default=self.unique_id)] = str
        return vol.Schema(schema)

    @callback
    def _async_current_hosts(self):
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        serial = discovery_info.properties["serialnum"]
        await self.async_set_unique_id(serial)

        # 75 If system option to enable newly discoverd entries is off (by user)
        # and uniqueid is this serial then skip updating ip
        for entry in self._async_current_entries(include_ignore=False):
            if entry.pref_disable_new_entities and entry.unique_id is not None:
                if entry.unique_id == serial:
                    LOGGER.debug(
                        "Envoy autodiscovery/ip update disabled for: %s, IP detected: %s %s",
                        serial,
                        discovery_info.host,
                        entry.unique_id,
                    )
                    return self.async_abort(reason="pref_disable_new_entities")

        # autodiscovery is updating the ip address of an existing
        # envoy with matching serial to new detected ip adress
        self.ip_address = discovery_info.host
        self._abort_if_unique_id_configured({CONF_HOST: self.ip_address})
        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.unique_id is None
                and CONF_HOST in entry.data
                and entry.data[CONF_HOST] == self.ip_address
            ):
                title = f"{ENVOY} {serial}" if entry.title == ENVOY else ENVOY
                self.hass.config_entries.async_update_entry(
                    entry, title=title, unique_id=serial
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
                return self.async_abort(reason="already_configured")

        return await self.async_step_user()

    # pylint: disable=unused-argument
    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    def _async_envoy_name(self) -> str:
        """Return the name of the envoy."""
        if self.unique_id:
            return f"{ENVOY} {self.unique_id}"
        return ENVOY

    async def _async_set_unique_id_from_envoy(
        self, hass: HomeAssistant, envoy_reader: EnvoyReader
    ) -> bool:
        """Set the unique id by fetching it from the envoy."""
        serial = None

        session = async_create_clientsession(hass, verify_ssl=False)
        serial = await envoy_reader.get_full_serial_number(session)
        if serial:
            await self.async_set_unique_id(serial)
            return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if (
                not self._reauth_entry
                and user_input[CONF_HOST] in self._async_current_hosts()
            ):
                return self.async_abort(reason="already_configured")
            try:
                envoy_reader = await self.validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = user_input.copy()
                data[CONF_NAME] = self._async_envoy_name()

                # Save token
                data[CONF_TOKEN] = envoy_reader.enlighten_token

                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=data,
                    )
                    return self.async_abort(reason="reauth_successful")

                if not self.unique_id and await self._async_set_unique_id_from_envoy(
                    self.hass, envoy_reader
                ):
                    data[CONF_NAME] = self._async_envoy_name()

                if self.unique_id:
                    self._abort_if_unique_id_configured({CONF_HOST: data[CONF_HOST]})

                return self.async_create_entry(title=data[CONF_NAME], data=data)

        if self.unique_id:
            self.context["title_placeholders"] = {
                CONF_SERIAL_NUMBER: self.unique_id,
                CONF_HOST: self.ip_address,
            }
        return self.async_show_form(
            step_id="user",
            data_schema=self._async_generate_schema(),
            errors=errors,
        )

    async def validate_input(
        self, hass: HomeAssistant, data: dict[str, Any]
    ) -> EnvoyReader:
        """Validate the user input allows us to connect."""
        envoy_reader = EnvoyReader(
            data[CONF_HOST],
            enlighten_user=data[CONF_USERNAME],
            enlighten_pass=data[CONF_PASSWORD],
            enlighten_serial_num=data[CONF_SERIAL_NUMBER],
        )

        try:
            session = async_create_clientsession(hass, verify_ssl=False)
            await envoy_reader.get_meters(session)
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise InvalidAuth from err

            LOGGER.debug("Validation error: %s", err)

            raise CannotConnect from err

        return envoy_reader

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for iregul."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        scan_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )

        optSchem = vol.Schema(
            {
                vol.Optional(CONF_UPDATE_INTERVAL, default=scan_interval): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=optSchem)

    async def async_step_abort(self, user_input=None):
        """Abort options flow."""
        return self.async_create_entry(title="", data=self.config_entry.options)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
