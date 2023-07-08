"""Representation of an envoystream api."""
import asyncio
import json
import logging
from collections.abc import Callable

import anyio
import httpx
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from .const import SIGNAL_RECEIVE_MESSAGE

_LOGGER = logging.getLogger(__name__)


class EnvoyStreamApi:
    """Representation of an envoystream api.

    The api is responsible for receiving the envoystream frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    hass: HomeAssistant
    device_id: str = None
    detectedValue: dict[str, str] = {}
    dataAvailable: bool = None

    def __init__(self, hass: HomeAssistant, host: str, user: str, passw: str):
        """Initialize the envoystream dongle."""
        self._serial_loop_task = None
        self.host = host
        self.digestauth = httpx.DigestAuth(user, passw)
        self.hass = hass
        self.session = get_async_client(hass)

    async def unload(self):
        """Disconnect callbacks established at init time."""
        _LOGGER.info("Unload")
        self.stop_envoy_stream_reader()

    async def get_sn(self):
        """Register read task to home assistant."""
        url = "http://%s/inventory.json" % self.host
        _LOGGER.debug("Opening %s", url)

        resp = await self.session.get(url, auth=self.digestauth)
        response = resp.json()
        # print(response)
        for line in response:
            if line["type"] == "NSRB" and len(line["devices"]) == 1:
                serial_num = line["devices"][0]["serial_num"]
                _LOGGER.debug("Serial Number: %s" % serial_num)

                return serial_num

    async def start_reading(self):
        """Register read task to home assistant."""
        if self._serial_loop_task:
            _LOGGER.warn("task already initialized")
            return

        _LOGGER.info("Initialize envoystream task")
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.stop_envoy_stream_reader()
        )

        self._serial_loop_task = self.hass.loop.create_task(
            self.envoy_stream_reader(self.envoy_stream_callback)
        )

    async def get_key(self, typedata: str, phase: str, datatype: str) -> str:
        """Process the serial data."""
        return f"{typedata}-{phase}-{datatype}"

    @callback
    async def envoy_stream_callback(self, message):
        """Process the serial data."""

        result = {}
        # Format datas
        for type in message:
            for phase in message[type]:
                for data in message[type][phase]:
                    result[await self.get_key(type, phase, data)] = message[type][
                        phase
                    ][data]

        self.hass.helpers.dispatcher.dispatcher_send(SIGNAL_RECEIVE_MESSAGE, result)

    async def envoy_stream_reader(self, data_callback: Callable[[str], None]):
        """Process the serial data."""
        _LOGGER.info("Initializing envoystream loop")

        while True:
            try:
                url = "http://%s/stream/meter" % self.host
                _LOGGER.debug("Opening %s", url)

                counter: int = 0
                async with self.session.stream(
                    "GET", url, auth=self.digestauth
                ) as resp:
                    async for line in resp.aiter_lines():
                        if counter == 0:
                            await self.handle_json_message(line, data_callback)
                            counter = 6

                        counter = counter - 1

            except anyio.ClosedResourceError:
                break
            except Exception as exc:
                _LOGGER.exception(
                    "Unable to connect to the serial device %s: %s. Will retry",
                    self.host,
                    exc,
                )
                await asyncio.sleep(5)

    async def handle_json_message(
        self, message: bytes, data_callback: Callable[[object], None]
    ):
        """Process the serial data."""
        line_text = message.replace("data: ", "").replace("'", '"').strip()

        if len(line_text) > 0:
            line_json = json.loads(line_text)

            # Add totals to response
            for key in line_json:
                line_json[key]["ph-t"] = {}
                line_json[key]["ph-t"]["p"] = (
                    line_json[key]["ph-a"]["p"]
                    + line_json[key]["ph-b"]["p"]
                    + line_json[key]["ph-c"]["p"]
                )

            await data_callback(line_json)

    @callback
    def stop_envoy_stream_reader(self):
        """Close resources."""
        if self._serial_loop_task:
            self._serial_loop_task.cancel()
            self._serial_loop_task = None
