"""Event platform: `parked` and `departed`, with the location and the driver as attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.event import EventEntity
from homeassistant.core import callback

from .const import EVENT_DEPARTED, EVENT_PARKED
from .entity import VehicleEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import BluetoothDeviceGpsConfigEntry
    from .tracker import Vehicle

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: BluetoothDeviceGpsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one event entity per vehicle."""
    for subentry_id, vehicle in entry.runtime_data.vehicles.items():
        async_add_entities([VehicleActivityEvent(vehicle)], config_subentry_id=subentry_id)


class VehicleActivityEvent(VehicleEntity, EventEntity):
    """Fires `parked` once the final location is known and `departed` when driving starts."""

    _attr_translation_key = "activity"

    def __init__(self, vehicle: Vehicle) -> None:
        """Initialise the event entity."""
        super().__init__(vehicle, "activity")
        self._attr_event_types = [EVENT_PARKED, EVENT_DEPARTED]

    async def async_added_to_hass(self) -> None:
        """Listen to the vehicle's events."""
        await super().async_added_to_hass()
        self.async_on_remove(self.vehicle.async_add_event_listener(self._handle_event))

    @callback
    def _handle_event(self, event_type: str, data: dict[str, Any]) -> None:
        self._trigger_event(event_type, data)
        self.async_write_ha_state()
