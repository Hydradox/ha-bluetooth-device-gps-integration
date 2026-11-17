"""Sensor platform for Integration Template."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IntegrationTemplateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import IntegrationTemplateConfigEntry

# The coordinator is the only place that talks to the outside: entities never poll.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: IntegrationTemplateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors of a config entry."""
    async_add_entities([IntegrationTemplateSensor(entry.runtime_data)])


class IntegrationTemplateSensor(CoordinatorEntity[IntegrationTemplateCoordinator], SensorEntity):
    """Example sensor backed by the coordinator."""

    _attr_has_entity_name = True
    _attr_translation_key = "value"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: IntegrationTemplateCoordinator) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        # Stable and unique: never derive it from the name, which the user can change.
        self._attr_unique_id = f"{entry.entry_id}_value"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.coordinator.data.get("value")
