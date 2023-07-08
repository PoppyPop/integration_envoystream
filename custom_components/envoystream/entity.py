"""EnvoyStreamEntity class."""
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .const import NAME
from .const import SIGNAL_RECEIVE_MESSAGE
from .const import VERSION


class EnvoyStreamEntity(Entity):
    """Representation of an base envoystream api.

    The api is responsible for receiving the envoystream frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    def __init__(self, envoy_id):
        """Initialize the device."""
        self.envoy_id = envoy_id

    @property
    def device_info(self):
        """Get device Info."""
        return {
            "identifiers": {(DOMAIN, self.envoy_id)},
            "name": NAME,
            "model": self.envoy_id,
            "sw_version": VERSION,
            "manufacturer": "Enphase",
        }

    @property
    def should_poll(self):
        """Push mode do not poll."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_RECEIVE_MESSAGE, self._message_received_callback
            )
        )

    def _message_received_callback(self, frame):
        """Handle incoming packets."""
        self.value_changed(frame)

    def value_changed(self, frame):
        """Update the internal state of the device when a packet arrives."""
