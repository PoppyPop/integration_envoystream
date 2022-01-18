"""
Custom integration to integrate teleinformation with Home Assistant.

For more details about this integration, please refer to
https://github.com/poppypop/integration_teleinformation
"""
import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config
from homeassistant.core import HomeAssistant

from .const import DATA_DETECTED_VALUE
from .const import DATA_DONGLE
from .const import DATA_SERIAL_NUMBER
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

    # First gather teleinfo frame for config
    hass.data[DOMAIN][entry.entry_id] = {}

    api = EnvoyStreamApi(hass, entry)

    hass.data[DOMAIN][entry.entry_id][DATA_DONGLE] = api

    # serialnumber = await usb_dongle.async_config_entry_first_refresh()
    usb_dongle.initialize_reading()

    while usb_dongle.dataAvailable is not True:
        await asyncio.sleep(1)

    hass.data[DOMAIN][entry.entry_id][
        DATA_DETECTED_VALUE
    ] = usb_dongle.detectedValue.keys()
    hass.data[DOMAIN][entry.entry_id][DATA_SERIAL_NUMBER] = usb_dongle.device_id

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.add_update_listener(_async_reload_entry)

    def handle_restart(call):
        """Handle the service call."""
        restart_usb_dongle = hass.data[DOMAIN][entry.entry_id][DATA_DONGLE]

        restart_usb_dongle.stop_serial_read()
        restart_usb_dongle.initialize_reading()

    hass.services.async_register(DOMAIN, "restart", handle_restart)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    usb_dongle = hass.data[DOMAIN][entry.entry_id][DATA_DONGLE]
    usb_dongle.unload()

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
