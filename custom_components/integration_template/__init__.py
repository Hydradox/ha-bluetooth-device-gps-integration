"""The Integration Template integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .const import PLATFORMS
from .coordinator import IntegrationTemplateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# `runtime_data` holds the coordinator for the lifetime of the entry (no `hass.data[DOMAIN]`).
type IntegrationTemplateConfigEntry = ConfigEntry[IntegrationTemplateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IntegrationTemplateConfigEntry) -> bool:
    """Set up Integration Template from a config entry."""
    coordinator = IntegrationTemplateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IntegrationTemplateConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
