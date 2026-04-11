"""Module to read production and consumption values from an Enphase Envoy on the local network."""

from __future__ import annotations

import typing
import xml.etree.ElementTree as ET
from datetime import UTC
from datetime import datetime

import aiohttp
import jwt
from homeassistant.util.network import is_ipv6_address

from .const import LOGGER

LOGIN_URL = "https://enlighten.enphaseenergy.com/login/login.json?"
TOKEN_URL = "https://entrez.enphaseenergy.com/tokens"

INFO_URL = "https://{}/info.json"

METERS_URL = "https://{}/ivp/meters"
READINGS_URL = f"{METERS_URL}/readings"


class EnvoyReader:
    """Instance of EnvoyReader."""

    def __init__(
        self,
        host: str,
        enlighten_user: str | None = None,
        enlighten_pass: str | None = None,
        enlighten_serial_num: str | None = None,
        enlighten_token: str | None = None,
    ) -> None:
        """Init the EnvoyReader."""
        self.host: str = host.lower()
        # IPv6 addresses need to be enclosed in brackets
        if is_ipv6_address(self.host):
            self.host = f"[{self.host}]"
        self.enlighten_user = enlighten_user
        self.enlighten_pass = enlighten_pass
        self.enlighten_serial_num = enlighten_serial_num
        self.enlighten_token = enlighten_token
        self.firmware_version: str | None = None
        self._meters: dict[str, str] | None = None
        self._phase_count: int = 0
        self._expirydate: datetime | None = None

        if self.enlighten_token is not None:
            self._get_expiry_date(self.enlighten_token)

    @property
    def token_expiration_date(self) -> datetime | None:
        """Return the expiration date of the current token."""
        return self._expirydate

    async def _async_get(
        self,
        url: str,
        http_session: aiohttp.ClientSession,
        is_json: bool = True,
        is_retry: bool = False,
    ) -> typing.Any:
        url = url.format(self.host)
        LOGGER.debug("HTTP GET Attempt: %s", url)
        headers = {"Authorization": f"Bearer {self.enlighten_token}"}
        async with http_session.get(url, headers=headers) as resp:
            if is_retry:
                resp.raise_for_status()

            if resp.status == 401:
                if (
                    self.enlighten_user
                    and self.enlighten_pass
                    and self.enlighten_serial_num
                ):
                    self.enlighten_token = None
                    await self._login(http_session)
                    return await self._async_get(url, http_session, is_retry=True)

                resp.raise_for_status()

            if is_json:
                return await resp.json(content_type=None)
            else:
                return await resp.text()

    async def _get_enphase_sessionid(
        self, http_session: aiohttp.ClientSession, user: str, password: str
    ) -> str:
        """Get session_id from login."""
        data = {"user[email]": user, "user[password]": password}
        LOGGER.debug("Getting session_id: %s", LOGIN_URL)
        async with http_session.post(LOGIN_URL, data=data) as resp:
            resp.raise_for_status()
            result = await resp.json()
            return result["session_id"]

    async def _get_enphase_token(
        self,
        http_session: aiohttp.ClientSession,
        envoy_serial: str,
        user: str,
        password: str,
    ) -> str:
        """Get long-term token."""
        session_id = await self._get_enphase_sessionid(http_session, user, password)
        data = {"session_id": session_id, "serial_num": envoy_serial, "username": user}
        LOGGER.debug("Getting Token: %s", TOKEN_URL)
        async with http_session.post(TOKEN_URL, json=data) as resp:
            resp.raise_for_status()
            jwt_token = await resp.text()
            self._get_expiry_date(jwt_token)
            return jwt_token

    def _get_expiry_date(self, jwt_token: str) -> None:
        """Decode the token and store its expiry date."""
        decoded_token = jwt.decode(jwt_token, options={"verify_signature": False})
        self._expirydate = datetime.fromtimestamp(decoded_token["exp"], tz=UTC)
        LOGGER.debug("Token expiry date: %s", self._expirydate)

    def _is_token_expired(self) -> bool:
        return self._expirydate is not None and datetime.now() > self._expirydate

    async def _login(self, http_session: aiohttp.ClientSession) -> None:
        if (
            self.enlighten_user
            and self.enlighten_pass
            and self.enlighten_serial_num
            and (self.enlighten_token is None or self._is_token_expired())
        ):
            self.enlighten_token = await self._get_enphase_token(
                http_session,
                self.enlighten_serial_num,
                self.enlighten_user,
                self.enlighten_pass,
            )

    async def get_meters(self, http_session: aiohttp.ClientSession) -> dict[str, str]:
        """Get."""
        if self._meters is None:
            await self._login(http_session)
            meters = await self._async_get(METERS_URL, http_session)

            self._meters = {}
            for meter in meters:
                self._meters[meter["eid"]] = meter["measurementType"]
                self._phase_count = meter["phaseCount"]

        return self._meters

    async def get_datas(self, http_session: aiohttp.ClientSession) -> dict[str, float]:
        """Fetch data from the endpoint."""

        await self._login(http_session)
        await self.get_meters(http_session)
        assert self._meters is not None

        readings = await self._async_get(READINGS_URL, http_session)

        result: dict[str, float] = {}

        for reading in readings:
            if reading["eid"] not in self._meters:
                LOGGER.debug("Unknown meter eid: %s", reading["eid"])
                continue
            reading_type = self._meters[reading["eid"]]

            result[f"{reading_type}"] = reading["instantaneousDemand"]

            phase_number: int = 1
            for phase in reading["channels"]:
                result[f"{reading_type}_phase_{phase_number}"] = phase[
                    "instantaneousDemand"
                ]
                phase_number += 1

        # Add full consumption
        result["total_consumption"] = result["production"] + result["net-consumption"]
        for i in range(1, self._phase_count + 1):
            result[f"total_consumption_phase_{i}"] = (
                result[f"production_phase_{i}"] + result[f"net-consumption_phase_{i}"]
            )

        return result

    async def get_full_serial_number(
        self, http_session: aiohttp.ClientSession
    ) -> tuple[str, str | None]:
        """Get serial number and firmware version."""

        infos = await self._async_get(INFO_URL, http_session, is_json=False)
        infos_obj = ET.fromstring(infos)
        if (device := infos_obj.find("device")) is None:
            raise ValueError("Device information not found")

        if (serial := device.find("sn")) is None or serial.text is None:
            raise ValueError("Serial number not found")

        firmware_version = None
        if (software := device.find("software")) is not None:
            firmware_version = software.text

        self.enlighten_serial_num = serial.text
        self.firmware_version = firmware_version

        return serial.text, firmware_version
