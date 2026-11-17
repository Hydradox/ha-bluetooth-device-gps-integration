"""Sensor platform: last driver and parked-since time."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .entity import VehicleEntity

if TYPE_CHECKING:
    from datetime import datetime

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
    """Create the sensors of every vehicle."""
    for subentry_id, vehicle in entry.runtime_data.vehicles.items():
        async_add_entities(
            [VehicleLastDriverSensor(vehicle), VehicleParkedSinceSensor(vehicle)],
            config_subentry_id=subentry_id,
        )


class VehicleLastDriverSensor(VehicleEntity, SensorEntity):
    """Name of the phone that connected to the vehicle last."""

    _attr_translation_key = "last_driver"

    def __init__(self, vehicle: Vehicle) -> None:
        """Initialise the sensor."""
        super().__init__(vehicle, "last_driver")

    @property
    def native_value(self) -> str | None:
        """Phone name."""
        return self.vehicle.last_driver


class VehicleParkedSinceSensor(VehicleEntity, SensorEntity):
    """When the vehicle was parked; unknown while it is being driven."""

    _attr_translation_key = "parked_since"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, vehicle: Vehicle) -> None:
        """Initialise the sensor."""
        super().__init__(vehicle, "parked_since")

    @property
    def native_value(self) -> datetime | None:
        """Parking time."""
        return self.vehicle.parked_at
