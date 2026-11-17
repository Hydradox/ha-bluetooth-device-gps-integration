"""Data update coordinator for Integration Template."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import LOGGER, UPDATE_INTERVAL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import IntegrationTemplateConfigEntry


class IntegrationTemplateCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Fetch the data once and share it with every entity.

    Replace `_async_update_data` with the real API call. Raise `UpdateFailed` when the
    source is unreachable (entities become unavailable) and `ConfigEntryAuthFailed` when
    the credentials are rejected (starts the reauth flow).
    """

    config_entry: IntegrationTemplateConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: IntegrationTemplateConfigEntry) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, float]:
        """Return the latest data (a deterministic demo value here)."""
        try:
            return {"value": float(dt_util.utcnow().minute)}
        except Exception as err:  # replace with the exceptions of your client library
            msg = f"Error fetching data: {err}"
            raise UpdateFailed(msg) from err
