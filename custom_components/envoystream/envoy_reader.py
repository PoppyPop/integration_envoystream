"""Module to read production and consumption values from an Enphase Envoy on the local network."""
import datetime
import logging
import typing

import aiohttp
import jwt
from homeassistant.util.network import is_ipv6_address

LOGIN_URL = "https://enlighten.enphaseenergy.com/login/login.json?"
TOKEN_URL = "https://entrez.enphaseenergy.com/tokens"

METERS_URL = "/ivp/meters"
READINGS_URL = f"{METERS_URL}/readings"

_LOGGER = logging.getLogger(__name__)


class EnvoyReader:  # pylint: disable=too-many-instance-attributes
    """Instance of EnvoyReader."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        host,
        enlighten_user=None,
        enlighten_pass=None,
        enlighten_serial_num=None,
        enlighten_token=None,
    ):
        """Init the EnvoyReader."""
        self.host = host.lower()
        # IPv6 addresses need to be enclosed in brackets
        if is_ipv6_address(self.host):
            self.host = f"[{self.host}]"
        self.enlighten_user = enlighten_user
        self.enlighten_pass = enlighten_pass
        self.enlighten_serial_num = enlighten_serial_num
        self.enlighten_token = enlighten_token
        self._phase_number = None

        if self.enlighten_token is not None:
            self._get_expiry_date(self.enlighten_token)

    async def _async_get(
        self, url: str, http_session: aiohttp.ClientSession, is_retry=False
    ) -> typing.Any:
        _LOGGER.debug("HTTP GET Attempt: %s", url)

        headers = {"Authorization": f"Bearer {self.enlighten_token}"}
        async with http_session.get(url, headers=headers) as resp:
            if is_retry:
                resp.raise_for_status()

            if resp.status == 401:
                self.enlighten_token = None
                await self._login(http_session)
                return await self._async_get(url, http_session)

            return await resp.json()

    async def _get_enphase_sessionid(
        self, http_session: aiohttp.ClientSession, user: str, password: str
    ) -> str:
        """get session_id from login."""
        data = {"user[email]": user, "user[password]": password}
        _LOGGER.debug("Getting session_id: %s", LOGIN_URL)
        async with http_session.post(LOGIN_URL, data=data) as resp:
            resp.raise_for_status()
            result = await resp.json()
            return result.session_id

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
        _LOGGER.debug("Getting Token: %s", TOKEN_URL)
        async with http_session.post(TOKEN_URL, json=data) as resp:
            resp.raise_for_status()
            jwt_token = await resp.text()
            await self._get_expiry_date(jwt_token)
            return jwt_token

    async def _get_expiry_date(self, jwt_token: str):
        decoded_token = jwt.decode(jwt_token, options={"verify_signature": False})
        self._expirydate = datetime.datetime().fromtimestamp(decoded_token["exp"])
        _LOGGER.debug("Token expiry date: %s", self._expirydate)

    async def _is_token_expired(self) -> bool:
        if datetime.datetime().now() > self._expirydate:
            return True

        return False

    async def _login(self, http_session: aiohttp.ClientSession):
        if self.enlighten_token is None or self._is_token_expired():
            self.enlighten_token = await self._get_enphase_token(
                http_session,
                self.enlighten_serial_num,
                self.enlighten_user,
                self.enlighten_pass,
            )

    async def get_phase_number(self, http_session: aiohttp.ClientSession) -> int:
        if self._phase_number is None:
            self._login(http_session)
            _ = await self._async_get(METERS_URL, http_session)

    async def getData(self, getInverters=True):  # pylint: disable=invalid-name
        """Fetch data from the endpoint and if inverters selected default."""
        """to fetching inverter data."""

        return
        # Check if the Secure flag is set
        # if self.https_flag == "s":
        #     _LOGGER.debug("Checking Token value: %s", self.token)
        #     # Check if a token has already been retrieved
        #     if self.token == "":
        #         _LOGGER.debug("Found empty token: %s", self.token)
        #         await self._getEnphaseToken()
        #     else:
        #         _LOGGER.debug("Token is populated: %s", self.token)
        #         if self._is_enphase_token_expired(self.token):
        #             _LOGGER.debug("Found Expired token - Retrieving new token")
        #             await self._getEnphaseToken()

        # if not self.endpoint_type:
        #     await self.detect_model()
        # else:
        #     await self._update()

        # if not self.get_inverters or not getInverters:
        #     return

        # inverters_url = ENDPOINT_URL_PRODUCTION_INVERTERS.format(
        #     self.https_flag, self.host
        # )
        # inverters_auth = httpx.DigestAuth(self.username, self.password)

        # response = await self._async_fetch_with_retry(
        #     inverters_url, auth=inverters_auth
        # )
        # _LOGGER.debug(
        #     "Fetched from %s: %s: %s",
        #     inverters_url,
        #     response,
        #     response.text,
        # )
        # if response.status_code == 401:
        #     response.raise_for_status()
        # self.endpoint_production_inverters = response
        # return
