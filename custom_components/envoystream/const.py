"""Constants for envoy stream."""
# Base component constants
import logging

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import DEVICE_CLASS_POWER
from homeassistant.const import POWER_WATT

NAME = "Envoy stream"
DOMAIN = "envoystream"
VERSION = "0.1.0"

LOGGER = logging.getLogger(__package__)


# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]


# Configuration and options
CONF_DEVICE = "device"

SIGNAL_RECEIVE_MESSAGE = "envoystream.receive_message"
DATA_SERIAL_NUMBER = "envoystream.sn"
DATA_STREAMAPI = "envoystream.streamapi"

SENSOR_TYPES = {
    "production-ph-a-p": [
        "Production Phase A",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
    "production-ph-b-p": [
        "Production Phase B",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
    "production-ph-c-p": [
        "Production Phase C",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
    "total-consumption-ph-a-p": [
        "Total Consumption Phase A",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
    "total-consumption-ph-b-p": [
        "Total Consumption Phase B",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
    "total-consumption-ph-c-p": [
        "Total Consumption Phase C",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
    "net-consumption-ph-a-p": [
        "Net Consumption Phase A",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
    "net-consumption-ph-b-p": [
        "Net Consumption Phase B",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
    "net-consumption-ph-c-p": [
        "Net Consumption Phase C",
        POWER_WATT,
        DEVICE_CLASS_POWER,
        STATE_CLASS_MEASUREMENT,
    ],
}
