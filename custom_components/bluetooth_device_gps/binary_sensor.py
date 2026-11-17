"""Binary sensor platform: is a phone connected to the vehicle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import PHASE_CONNECTED
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
    """Create one sensor per vehicle."""
    for subentry_id, vehicle in entry.runtime_data.vehicles.items():
        async_add_entities([VehicleConnectedSensor(vehicle)], config_subentry_id=subentry_id)


class VehicleConnectedSensor(VehicleEntity, BinarySensorEntity):
    """On while at least one phone is connected to the vehicle."""

    _attr_translation_key = "connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, vehicle: Vehicle) -> None:
        """Initialise the sensor."""
        super().__init__(vehicle, "connected")

    @property
    def is_on(self) -> bool:
        """Whether a phone is connected."""
        return self.vehicle.phase == PHASE_CONNECTED
