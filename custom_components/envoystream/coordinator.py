"""DataUpdateCoordinator for the IRegul integration."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_TOKEN
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SERIAL_NUMBER
from .const import CONF_UPDATE_INTERVAL
from .const import DEFAULT_UPDATE_INTERVAL
from .const import DOMAIN
from .const import LOGGER
from .envoy_reader import EnvoyReader


class EnvoyDataUpdateCoordinator(DataUpdateCoordinator):
    """Envoy Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the IRegul hub."""

        self.entry = entry

        scan_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)

        self.envoy_reader = EnvoyReader(
            entry.data[CONF_HOST],
            enlighten_user=entry.data[CONF_USERNAME],
            enlighten_pass=entry.data[CONF_PASSWORD],
            enlighten_serial_num=entry.data[CONF_SERIAL_NUMBER],
            enlighten_token=entry.data[CONF_TOKEN],
        )

        self.session = async_create_clientsession(hass, verify_ssl=False)

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from IRegul."""

        return await self.envoy_reader.get_datas(self.session)
