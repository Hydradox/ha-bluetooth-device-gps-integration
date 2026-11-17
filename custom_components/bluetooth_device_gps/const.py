"""Constants for Bluetooth Device GPS."""

import logging
import re

from homeassistant.const import Platform

DOMAIN = "bluetooth_device_gps"
LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.SENSOR,
]

SUBENTRY_VEHICLE = "vehicle"

# Vehicle (subentry) data
CONF_MACS = "macs"
CONF_LOCATION = "location"  # location selector value (map pin)
CONF_PICTURE = "picture"  # file id on input, stored file name in the subentry data

# Global options
CONF_PHONES = "phones"
CONF_FIX_TIMEOUT = "fix_timeout"
CONF_MAX_ACCURACY = "max_accuracy"
CONF_DISCONNECT_GRACE = "disconnect_grace"

DEFAULT_FIX_TIMEOUT = 300
DEFAULT_MAX_ACCURACY = 50
DEFAULT_DISCONNECT_GRACE = 20

# A live fix older than this (seconds before the disconnect) is not trusted as the parking spot.
LIVE_FIX_MAX_AGE = 120

# Phases of a vehicle
PHASE_PARKED = "parked"
PHASE_CONNECTED = "connected"
PHASE_SETTLING = "settling"

# Event entity types
EVENT_PARKED = "parked"
EVENT_DEPARTED = "departed"

# Where the current location came from
SOURCE_LIVE = "live"
SOURCE_REQUESTED = "requested_fix"
SOURCE_LAST_LIVE = "last_live"
SOURCE_STALE = "stale"
SOURCE_MANUAL = "manual"

BT_SENSOR_SUFFIX = "bluetooth_connection"
BT_ATTR_CONNECTED = "connected_paired_devices"
BT_ATTR_CONNECTED_PREFIX = "connected_"  # also covers connected_not_paired_devices
BT_ATTR_PAIRED = "paired_devices"
REQUEST_LOCATION_MESSAGE = "request_location_update"

MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(?:[:-]?[0-9A-Fa-f]{2}){5}$")
MAC_SEARCH_RE = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")

PICTURE_DIR_NAME = "pictures"
PICTURE_URL_BASE = f"/api/{DOMAIN}/picture"
ISSUE_NO_BLUETOOTH_SENSOR = "no_bluetooth_sensor"
STORAGE_VERSION = 1
