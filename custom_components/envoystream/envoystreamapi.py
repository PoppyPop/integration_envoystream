"""Representation of an Teleinformation dongle."""
import asyncio
import aiohttp
import logging
from typing import Dict
from typing import Callable

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


from .const import SIGNAL_RECEIVE_MESSAGE

_LOGGER = logging.getLogger(__name__)


class EnvoyStreamApi:
    """Representation of an TeleInformation dongle.

    The dongle is responsible for receiving the TeleInformation frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    hass: HomeAssistant
    device_id: str = None
    detectedValue: Dict[str, str] = {}
    dataAvailable: bool = None

    async def __init__(self, hass: HomeAssistant, host: str, user: str, passw: str):
        """Initialize the TeleInformation dongle."""

        self._serial_loop_task = None
        self.host = host
        self.basicauth = aiohttp.BasicAuth(user, passw)
        self.hass = hass
        self.session = async_get_clientsession(hass)

    async def unload(self):
        """Disconnect callbacks established at init time."""
        _LOGGER.info("Unload")
        self.stop_envoy_stream_reader()

    async def GetSN(self):
        """Register read task to home assistant"""
        url = 'http://%s/inventory.json' % self.host
        _LOGGER.debug(u"Opening %s", url)

        async with self.session.get(url, auth=self.basicauth) as resp:
            response = await resp.json()
            print(response)
            for line in response:
                if line.type == "NSRB" and len(line.devices) == 1:
                    return line.devices[0].serial_num

    async def StartReading(self):
        """Register read task to home assistant"""
        if self._serial_loop_task:
            _LOGGER.warn("task already initialized")
            return

        _LOGGER.info("Initialize teleinfo task")
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.stop_envoy_stream_reader()
        )

        self._serial_loop_task = self.hass.loop.create_task(self.envoy_stream_reader(self.envoy_stream_callback))

    @callback
    async def envoy_stream_callback(self, line: str):
        self.hass.helpers.dispatcher.dispatcher_send(
            SIGNAL_RECEIVE_MESSAGE, line
        )

    async def envoy_stream_reader(self, callback: Callable[[str]]):
        """Process the serial data."""
        _LOGGER.info(u"Initializing Teleinfo loop")

        while True:
            try:
                url = 'http://%s/stream/meter' % self.host
                _LOGGER.debug(u"Opening %s", url)

                async with self.session.get(url, auth=self.basicauth) as r:
                    async for line in r.content:
                        lineJson = await line.json()

                        for key in lineJson:
                            lineJson[key]['ph-t'].p = lineJson[key]['ph-a'].p + lineJson[key]['ph-b'].p + lineJson[key]['ph-c'].p

                        callback(lineJson)

            except Exception as exc:
                _LOGGER.exception(
                    "Unable to connect to the serial device %s: %s. Will retry",
                    self.port,
                    exc,
                )
                await asyncio.sleep(5)

    @callback
    def stop_envoy_stream_reader(self):
        """Close resources."""
        if self._serial_loop_task:
            self._serial_loop_task.cancel()
            self._serial_loop_task = None
