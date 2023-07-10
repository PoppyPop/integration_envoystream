"""Constants for envoy stream."""
# Base component constants
import logging

NAME = "Envoy"
DOMAIN = "envoystream"
VERSION = "0.2.0"

LOGGER = logging.getLogger(__package__)

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]


# Configuration and options
CONF_UPDATE_INTERVAL = "upd_int"
DEFAULT_UPDATE_INTERVAL = 2

CONF_SERIAL_NUMBER = "serial"
