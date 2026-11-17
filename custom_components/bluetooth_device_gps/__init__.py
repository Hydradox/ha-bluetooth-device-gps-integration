"""The Bluetooth Device GPS integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PICTURE_URL_BASE, PLATFORMS
from .pictures import cleanup, ensure_dir, picture_dir
from .tracker import BluetoothGpsManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# `runtime_data` holds the manager for the lifetime of the entry (no `hass.data[DOMAIN]`).
type BluetoothDeviceGpsConfigEntry = ConfigEntry[BluetoothGpsManager]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: ARG001
    """Serve the vehicle pictures (registered once per Home Assistant run)."""
    await hass.async_add_executor_job(ensure_dir, hass)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(PICTURE_URL_BASE, str(picture_dir(hass)), cache_headers=True)]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BluetoothDeviceGpsConfigEntry) -> bool:
    """Set up the manager and one device with its entities per vehicle subentry."""
    manager = BluetoothGpsManager(hass, entry)
    await manager.async_start()
    entry.async_on_unload(manager.async_stop)
    entry.runtime_data = manager

    keep = {vehicle.picture for vehicle in manager.vehicles.values() if vehicle.picture}
    await hass.async_add_executor_job(cleanup, hass, keep)

    # Options and subentry changes both reload the entry; state survives through the store.
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: BluetoothDeviceGpsConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BluetoothDeviceGpsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
