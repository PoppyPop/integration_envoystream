"""
Custom integration to integrate envoystream with Home Assistant.

For more details about this integration, please refer to
https://github.com/poppypop/integration_envoystream
"""
import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config
from homeassistant.core import HomeAssistant

from .const import CONF_HOST
from .const import CONF_PASSWORD
from .const import CONF_USERNAME
from .const import DATA_SERIAL_NUMBER
from .const import DATA_STREAMAPI
from .const import DOMAIN
from .const import PLATFORMS
from .envoystreamapi import EnvoyStreamApi

SCAN_INTERVAL = timedelta(minutes=900)


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    # First gather envoystream frame for config
    hass.data[DOMAIN][entry.entry_id] = {}

    api = EnvoyStreamApi(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    hass.data[DOMAIN][entry.entry_id][DATA_STREAMAPI] = api
    hass.data[DOMAIN][entry.entry_id][DATA_SERIAL_NUMBER] = await api.get_sn()

    # Start reading
    await api.start_reading()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.add_update_listener(_async_reload_entry)

    def handle_restart(call):
        """Handle the service call."""
        restart_api_stream: EnvoyStreamApi = hass.data[DOMAIN][entry.entry_id][
            DATA_STREAMAPI
        ]

        restart_api_stream.stop_envoy_stream_reader()
        restart_api_stream.start_reading()

    hass.services.async_register(DOMAIN, "restart", handle_restart)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    api: EnvoyStreamApi = hass.data[DOMAIN][entry.entry_id][DATA_STREAMAPI]
    await api.unload()

    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
