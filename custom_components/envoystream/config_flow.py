"""Config flow for Enphase Envoy integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_NAME
from homeassistant.const import CONF_TOKEN
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from jwt import InvalidTokenError

from .const import CONF_SERIAL_NUMBER
from .const import CONF_UPDATE_INTERVAL
from .const import DEFAULT_UPDATE_INTERVAL
from .const import DOMAIN
from .const import LOGGER
from .envoy_reader import EnvoyReader

ENVOY = "Envoy"
TOKEN_URL = "https://entrez.enphaseenergy.com"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enphase Envoy."""

    VERSION = 1

    def __init__(self):
        """Initialize an envoy flow."""
        self.ip_address: str | None = None
        self._reauth_entry: ConfigEntry | None = None

    @callback
    def _async_generate_schema(self) -> vol.Schema:
        """Generate schema."""
        schema: dict[vol.Marker, object] = {}

        if self.ip_address:
            schema[vol.Required(CONF_HOST, default=self.ip_address)] = vol.In(
                [self.ip_address]
            )
        else:
            schema[vol.Required(CONF_HOST)] = str

        default_token = None
        if self._reauth_entry is not None:
            default_token = self._reauth_entry.data.get(CONF_TOKEN)

        if default_token:
            schema[vol.Required(CONF_TOKEN, default=default_token)] = str
        else:
            schema[vol.Required(CONF_TOKEN)] = str

        return vol.Schema(schema)

    @callback
    def _async_current_hosts(self) -> set[str]:
        """Return a set of hosts."""
        return {
            entry.data[CONF_HOST]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_HOST in entry.data
        }

    async def async_step_zeroconf(self, discovery_info: Any):
        """Handle a flow initialized by zeroconf discovery."""
        serial = discovery_info.properties["serialnum"]
        if isinstance(serial, bytes):
            serial = serial.decode()

        host = str(discovery_info.host)
        await self.async_set_unique_id(serial)

        # 75 If system option to enable newly discoverd entries is off (by user)
        # and uniqueid is this serial then skip updating ip
        for entry in self._async_current_entries(include_ignore=False):
            if entry.pref_disable_new_entities and entry.unique_id is not None:
                if entry.unique_id == serial:
                    LOGGER.debug(
                        "Envoy autodiscovery/ip update disabled for: %s, IP detected: %s %s",
                        serial,
                        host,
                        entry.unique_id,
                    )
                    return self.async_abort(reason="pref_disable_new_entities")

        # autodiscovery is updating the ip address of an existing
        # envoy with matching serial to new detected ip adress
        self.ip_address = host
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
    async def async_step_reauth(self, user_input: dict[str, Any] | None = None):
        """Handle configuration by re-auth."""
        entry_id = self.context.get("entry_id")
        if entry_id is None:
            return self.async_abort(reason="unknown")

        self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        self.ip_address = self._reauth_entry.data[CONF_HOST]
        if self._reauth_entry.unique_id:
            await self.async_set_unique_id(self._reauth_entry.unique_id)
        return await self.async_step_user()

    def _async_envoy_name(self) -> str:
        """Return the name of the envoy."""
        if self.unique_id:
            return f"{ENVOY} {self.unique_id}"
        return ENVOY

    @staticmethod
    @callback
    def _async_description_placeholders() -> dict[str, str]:
        """Return description placeholders for the flow."""
        return {"token_url": TOKEN_URL}

    async def _async_set_unique_id_from_envoy(
        self, hass: HomeAssistant, envoy_reader: EnvoyReader
    ) -> bool:
        """Set the unique id by fetching it from the envoy."""
        serial = envoy_reader.enlighten_serial_num
        if serial is None:
            session = async_create_clientsession(hass, verify_ssl=False)
            serial, firmware_version = await envoy_reader.get_full_serial_number(
                session
            )
            envoy_reader.firmware_version = firmware_version

        if serial:
            envoy_reader.enlighten_serial_num = serial
            await self.async_set_unique_id(serial)
            return True
        return False

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

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
                if (
                    not self.unique_id
                    and not await self._async_set_unique_id_from_envoy(
                        self.hass, envoy_reader
                    )
                ):
                    errors["base"] = "cannot_connect"
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._async_generate_schema(),
                        errors=errors,
                    )

                data = user_input.copy()
                data[CONF_SERIAL_NUMBER] = envoy_reader.enlighten_serial_num
                data[CONF_NAME] = self._async_envoy_name()

                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry,
                        data=data,
                    )
                    return self.async_abort(reason="reauth_successful")

                if self.unique_id:
                    self._abort_if_unique_id_configured({CONF_HOST: data[CONF_HOST]})

                return self.async_create_entry(title=data[CONF_NAME], data=data)

        if self.unique_id:
            self.context["title_placeholders"] = {
                CONF_SERIAL_NUMBER: self.unique_id,
                CONF_HOST: self.ip_address or "",
            }
        return self.async_show_form(
            step_id="user",
            data_schema=self._async_generate_schema(),
            description_placeholders=self._async_description_placeholders(),
            errors=errors,
        )

    async def validate_input(
        self, hass: HomeAssistant, data: dict[str, Any]
    ) -> EnvoyReader:
        """Validate the user input allows us to connect."""
        envoy_reader = EnvoyReader(
            data[CONF_HOST],
            enlighten_token=data[CONF_TOKEN],
        )

        try:
            session = async_create_clientsession(hass, verify_ssl=False)
            await envoy_reader.get_meters(session)
            (
                envoy_reader.enlighten_serial_num,
                envoy_reader.firmware_version,
            ) = await envoy_reader.get_full_serial_number(session)
        except InvalidTokenError as err:
            raise InvalidAuth from err
        except aiohttp.ClientResponseError as err:
            if err.status == 401:
                raise InvalidAuth from err

            LOGGER.debug("Validation error: %s", err)

            raise CannotConnect from err
        except ValueError as err:
            LOGGER.debug("Validation error: %s", err)
            raise CannotConnect from err

        return envoy_reader

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for iregul."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self._config_entry = config_entry

    @staticmethod
    @callback
    def _async_description_placeholders() -> dict[str, str]:
        """Return description placeholders for the flow."""
        return {"token_url": TOKEN_URL}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Handle options flow."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={
                    **self._config_entry.data,
                    CONF_TOKEN: user_input[CONF_TOKEN],
                },
            )
            return self.async_create_entry(
                title="",
                data={CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL]},
            )

        scan_interval = self._config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )

        opt_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TOKEN,
                    default=self._config_entry.data.get(CONF_TOKEN, ""),
                ): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=scan_interval): int,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=opt_schema,
            description_placeholders=self._async_description_placeholders(),
        )

    async def async_step_abort(self, user_input: dict[str, Any] | None = None):
        """Abort options flow."""
        return self.async_create_entry(title="", data=self._config_entry.options)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
