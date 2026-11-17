"""Constants for Integration Template."""

import logging
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "integration_template"
LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

UPDATE_INTERVAL = timedelta(minutes=1)
