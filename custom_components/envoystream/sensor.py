"""Sensor platform for envoystream."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_SERIAL_NUMBER
from .const import DOMAIN
from .const import SENSOR_TYPES
from .entity import EnvoyStreamEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_devices):
    """Setup sensor platform."""

    serial_number: str = hass.data[DOMAIN][entry.entry_id][DATA_SERIAL_NUMBER]

    for device in SENSOR_TYPES:
        async_add_devices([EnvoyStreamSensor(serial_number, device)])


def _get_unique_id(envoy_id: str, name: str):
    return f"{envoy_id}_{name}"


class EnvoyStreamSensor(EnvoyStreamEntity, SensorEntity):
    """envoystream Sensor class."""

    def __init__(self, envoy_id: str, dev_name: str):
        """Initialize the EnOcean sensor device."""
        super().__init__(envoy_id)
        self._state = None
        self.dev_name = dev_name

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_TYPES[self.dev_name][0]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return _get_unique_id(self.envoy_id, self.dev_name)

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def state_class(self):
        """Return the state_class of the device."""
        return SENSOR_TYPES[self.dev_name][3]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._state is not None

    @property
    def device_class(self):
        """Return de device class of the sensor."""
        return SENSOR_TYPES[self.dev_name][2]

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return SENSOR_TYPES[self.dev_name][1]

    def value_changed(self, frame):
        """Update the internal state of the sensor."""

        if self.dev_name in frame:
            self._state = frame[self.dev_name]
            self.schedule_update_ha_state()
