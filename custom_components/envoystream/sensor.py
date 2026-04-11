"""Sensor platform for envoystream."""

from collections.abc import Callable
from collections.abc import Iterable

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.const import UnitOfPower
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL_NUMBER
from .const import DOMAIN
from .const import NAME
from .coordinator import EnvoyDataUpdateCoordinator


class EnvoyCoordinatorSensorEntity(  # type: ignore
    CoordinatorEntity[EnvoyDataUpdateCoordinator], SensorEntity
):
    """Runtime base for coordinator-backed sensors."""

    def __init__(self, coordinator: EnvoyDataUpdateCoordinator) -> None:
        """Initialize the runtime base."""
        super().__init__(coordinator)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[Iterable[Entity]], None],
) -> None:
    """Sensor platform setup."""

    datas = hass.data

    coordinator: EnvoyDataUpdateCoordinator = datas[DOMAIN][entry.entry_id]
    serial_number: str = coordinator.entry.data[CONF_SERIAL_NUMBER]
    firmware_version = coordinator.envoy_reader.firmware_version
    if firmware_version is None:
        _, firmware_version = await coordinator.envoy_reader.get_full_serial_number(
            coordinator.session
        )
    device_info = _get_device_info(serial_number, firmware_version)

    sensors: list[Entity] = [
        EnvoyStreamSensor(coordinator, serial_number, id, device_info)
        for id in coordinator.data
    ]
    sensors.append(EnvoyTokenExpirationSensor(coordinator, serial_number, device_info))

    async_add_entities(sensors)


def _get_unique_id(envoy_id: str, name: str) -> str:
    return f"{envoy_id}_{name}"


def _get_name(envoy_id: str) -> str:
    return f"{NAME} {envoy_id}"


def _get_device_info(serial_number: str, firmware_version: str | None) -> DeviceInfo:
    """Build the shared device info."""
    return DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
        name=_get_name(serial_number),
        model=serial_number,
        sw_version=firmware_version,
        manufacturer="Enphase",
    )


class EnvoyStreamSensor(EnvoyCoordinatorSensorEntity):
    """envoystream Sensor class."""

    coordinator: EnvoyDataUpdateCoordinator
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        coordinator: EnvoyDataUpdateCoordinator,
        serial_number: str,
        value_name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.serial_number = serial_number
        self.value_name = value_name
        self._attr_name = (
            _get_name(self.serial_number)
            + " "
            + self.value_name.replace("_", " ").replace("-", " ").title()
        )
        self._attr_unique_id = _get_unique_id(self.serial_number, self.value_name)
        self._attr_device_info = device_info
        self._update_attrs()

    def _update_attrs(self) -> None:
        """Update entity attributes from coordinator data."""
        self._attr_available = (
            self.coordinator.last_update_success
            and self.value_name in self.coordinator.data
        )
        self._attr_native_value = self.coordinator.data.get(self.value_name)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()


class EnvoyTokenExpirationSensor(EnvoyCoordinatorSensorEntity):
    """Sensor exposing the token expiration date."""

    coordinator: EnvoyDataUpdateCoordinator
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: EnvoyDataUpdateCoordinator,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.serial_number = serial_number
        self._attr_name = f"{_get_name(self.serial_number)} Token Expiration"
        self._attr_unique_id = _get_unique_id(self.serial_number, "token_expiration")
        self._attr_device_info = device_info
        self._update_attrs()

    def _update_attrs(self) -> None:
        """Update entity attributes from coordinator data."""
        self._attr_native_value = self.coordinator.envoy_reader.token_expiration_date
        self._attr_available = (
            self.coordinator.last_update_success and self._attr_native_value is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()
