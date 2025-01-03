"""Sensor platform for envoystream."""

from collections.abc import Callable
from collections.abc import Iterable

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL_NUMBER
from .const import DOMAIN
from .const import NAME
from .const import VERSION
from .coordinator import EnvoyDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[Iterable[Entity]], None],
) -> None:
    """Sensor platform setup."""

    datas = hass.data

    coordinator: EnvoyDataUpdateCoordinator = datas[DOMAIN][entry.entry_id]
    serial_number: str = coordinator.entry.data[CONF_SERIAL_NUMBER]

    sensors: list[Entity] = [
        EnvoyStreamSensor(coordinator, serial_number, id) for id in coordinator.data
    ]

    async_add_entities(sensors)


def _get_unique_id(envoy_id: str, name: str):
    return f"{envoy_id}_{name}"


def _get_name(envoy_id: str):
    return f"{NAME} {envoy_id}"


class EnvoyStreamSensor(CoordinatorEntity, SensorEntity):
    """envoystream Sensor class."""

    coordinator: EnvoyDataUpdateCoordinator

    def __init__(
        self,
        coordinator: EnvoyDataUpdateCoordinator,
        serial_number: str,
        value_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.value_name = value_name
        self.serial_number = serial_number

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return (
            _get_name(self.serial_number)
            + " "
            + self.value_name.replace("_", " ").replace("-", " ").title()
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return _get_unique_id(self.serial_number, self.value_name)

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.serial_number)},
            "name": _get_name(self.serial_number),
            "model": self.serial_number,
            "sw_version": VERSION,
            "manufacturer": "Enphase",
        }

    @property
    def native_value(self) -> str:
        """Return the state of the entity."""
        return self.coordinator.data[self.value_name]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        datas = self.coordinator.data
        return super().available and self.value_name in datas

    @property
    def device_class(self) -> str:
        """Return the class of this entity."""
        return SensorDeviceClass.POWER

    @property
    def state_class(self):
        """Return the device class."""
        return SensorStateClass.MEASUREMENT

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return UnitOfPower.WATT
