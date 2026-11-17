"""Device tracker platform: one GPS tracker per vehicle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.helpers import entity_platform
from homeassistant.helpers.selector import LocationSelector

from .const import CONF_LOCATION, PICTURE_URL_BASE
from .entity import VehicleEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import BluetoothDeviceGpsConfigEntry
    from .tracker import BluetoothGpsManager, Vehicle

PARALLEL_UPDATES = 0

SERVICE_SET_LOCATION = "set_location"


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: BluetoothDeviceGpsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the trackers and register the entity service."""
    manager = entry.runtime_data
    for subentry_id, vehicle in manager.vehicles.items():
        async_add_entities([VehicleTracker(manager, vehicle)], config_subentry_id=subentry_id)

    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_SET_LOCATION,
        {
            vol.Required(CONF_LOCATION): LocationSelector(),
        },
        "async_set_location",
    )


class VehicleTracker(VehicleEntity, TrackerEntity):
    """The vehicle: follows the connected phone, parks on disconnect."""

    _attr_name = None  # the entity is the device

    def __init__(self, manager: BluetoothGpsManager, vehicle: Vehicle) -> None:
        """Initialise the tracker."""
        super().__init__(vehicle, "tracker")
        self._manager = manager
        if vehicle.picture:
            self._attr_entity_picture = f"{PICTURE_URL_BASE}/{vehicle.picture}"

    @property
    def source_type(self) -> SourceType:
        """The coordinates come from the phone's GPS."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Latitude of the vehicle."""
        return self.vehicle.fix.latitude if self.vehicle.fix else None

    @property
    def longitude(self) -> float | None:
        """Longitude of the vehicle."""
        return self.vehicle.fix.longitude if self.vehicle.fix else None

    @property
    def location_accuracy(self) -> float:
        """Accuracy of the fix in metres."""
        fix = self.vehicle.fix
        return fix.accuracy if fix and fix.accuracy is not None else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Phase, where the location came from and who drove."""
        vehicle = self.vehicle
        return {
            "phase": vehicle.phase,
            "location_source": vehicle.source,
            "last_driver": vehicle.last_driver,
            "fix_time": vehicle.fix.time.isoformat() if vehicle.fix else None,
        }

    async def async_set_location(self, location: dict[str, float]) -> None:
        """Entity service: place the vehicle by hand (latitude, longitude, optional radius)."""
        self._manager.async_set_location(
            self.vehicle, location["latitude"], location["longitude"], location.get("radius")
        )
