"""Sensor platform for envoystream."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MONITORED_VARIABLES
from .const import DATA_DETECTED_VALUE
from .const import DATA_SERIAL_NUMBER
from .const import DOMAIN
from .const import LOGGER
from .const import SENSOR_TYPES
from .const import SENSOR_TYPES_ALL
from .entity import TeleinformationEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_devices):
    """Setup sensor platform."""

    serialNumber: str = hass.data[DOMAIN][entry.entry_id][DATA_SERIAL_NUMBER]

    defaultValue: list[str] = [
        detectedSensor
        for detectedSensor in hass.data[DOMAIN][entry.entry_id][DATA_DETECTED_VALUE]
        if (detectedSensor in SENSOR_TYPES_ALL)
    ]

    devices = entry.options.get(CONF_MONITORED_VARIABLES, defaultValue)

    platform = "sensor"

    # Clean removed entity
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    toremove = [removed for removed in SENSOR_TYPES_ALL if (removed not in devices)]
    LOGGER.debug(toremove)

    for removedSensor in toremove:
        sensor_uid = _get_unique_id(serialNumber, removedSensor)
        entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, sensor_uid)
        if entity_id:
            LOGGER.debug("Removing entity: %s %s", platform, sensor_uid)
            entity_registry.async_remove(entity_id)

    for device in devices:
        async_add_devices([TeleinformationSensor(serialNumber, device)])


def _get_unique_id(meter_id: str, dev_name: str):
    return f"{meter_id}_{dev_name}"


class TeleinformationSensor(TeleinformationEntity, SensorEntity):
    """teleinformation Sensor class."""

    def __init__(self, meter_id, dev_name):
        """Initialize the EnOcean sensor device."""
        super().__init__(meter_id)
        self.dev_name = dev_name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_TYPES[self.dev_name][0]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return _get_unique_id(self.meter_id, self.dev_name)

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
