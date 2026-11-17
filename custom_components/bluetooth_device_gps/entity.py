"""Shared base of the vehicle entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

if TYPE_CHECKING:
    from .tracker import Vehicle


class VehicleEntity(Entity):
    """Pushed by the manager: never polls."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, vehicle: Vehicle, key: str) -> None:
        """Attach the entity to the device of a vehicle."""
        self.vehicle = vehicle
        # Stable and unique: never derive it from the name, which the user can change.
        self._attr_unique_id = f"{vehicle.subentry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehicle.subentry_id)},
            name=vehicle.name,
            model="Bluetooth vehicle",
        )

    async def async_added_to_hass(self) -> None:
        """Write the state whenever the manager reports a change."""
        await super().async_added_to_hass()
        self.async_on_remove(self.vehicle.async_add_listener(self.async_write_ha_state))
