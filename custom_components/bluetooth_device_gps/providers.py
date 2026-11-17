"""Sources of "which Bluetooth devices is this phone connected to" and of the phone's location.

Every source implements `PhoneProvider`. The Android Companion app is the only one today. A new
source (for example an iOS sensor, if one ever exists) is one class added to `PROVIDERS`: the
manager, the config flow and the entities never look at provider details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import BT_ATTR_CONNECTED, BT_ATTR_PAIRED, BT_SENSOR_SUFFIX, REQUEST_LOCATION_MESSAGE
from .helpers import parse_macs

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State

MOBILE_APP = "mobile_app"


@dataclass
class Phone:
    """A phone: where its connections and its location are read from."""

    device_id: str
    name: str
    provider: PhoneProvider
    sensor_id: str  # entity whose state changes when the Bluetooth connections change
    tracker_id: str | None  # device_tracker with the phone's GPS position
    # MACs currently connected; kept when the sensor is unavailable.
    connected: set[str] = field(default_factory=set)


class PhoneProvider(ABC):
    """A kind of phone the integration can read from."""

    #: Integration whose devices this provider handles (used to filter the phone selector).
    integration: str

    @abstractmethod
    def discover(self, hass: HomeAssistant, allowed: set[str]) -> dict[str, Phone]:
        """Return the usable phones by device id; `allowed` empty means every phone."""

    @abstractmethod
    def parse_connected(self, state: State) -> set[str] | None:
        """Return the connected MACs of a sensor state, or None to keep the previous value."""

    @abstractmethod
    def known_devices(self, state: State) -> dict[str, str]:
        """Return MAC -> label of the devices the phone knows, to offer them in the UI."""

    @abstractmethod
    async def async_request_location(self, hass: HomeAssistant, phone: Phone) -> bool:
        """Ask the phone for a fresh location; return False when it cannot be asked."""


class AndroidCompanionProvider(PhoneProvider):
    """Home Assistant Companion app for Android (`mobile_app`, `bluetooth_connection` sensor)."""

    integration = MOBILE_APP

    def discover(self, hass: HomeAssistant, allowed: set[str]) -> dict[str, Phone]:
        """Phones with an enabled Bluetooth connection sensor (disabled by default in the app)."""
        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)
        trackers: dict[str, str] = {}
        sensors: dict[str, str] = {}
        for entry in ent_reg.entities.values():
            if entry.platform != MOBILE_APP or entry.disabled_by or not entry.device_id:
                continue
            if entry.domain == "device_tracker":
                trackers.setdefault(entry.device_id, entry.entity_id)
            elif entry.domain == "sensor" and entry.unique_id.endswith(BT_SENSOR_SUFFIX):
                sensors[entry.device_id] = entry.entity_id

        phones: dict[str, Phone] = {}
        for device_id, sensor_id in sensors.items():
            if allowed and device_id not in allowed:
                continue
            device = dev_reg.async_get(device_id)
            name = (device.name_by_user or device.name) if device else None
            phones[device_id] = Phone(
                device_id, name or device_id, self, sensor_id, trackers.get(device_id)
            )
        return phones

    def parse_connected(self, state: State) -> set[str] | None:
        """Read `connected_paired_devices`; unavailable/unknown keep the previous value."""
        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return parse_macs(state.attributes.get(BT_ATTR_CONNECTED))

    def known_devices(self, state: State) -> dict[str, str]:
        """Paired and connected devices; the format is `MAC (name)` or `name (MAC)`."""
        devices: dict[str, str] = {}
        for attribute in (BT_ATTR_PAIRED, BT_ATTR_CONNECTED):
            for item in state.attributes.get(attribute) or []:
                macs = parse_macs(item)
                if len(macs) == 1:
                    devices.setdefault(next(iter(macs)), str(item))
        return devices

    async def async_request_location(self, hass: HomeAssistant, phone: Phone) -> bool:
        """Send `request_location_update` through the phone's notify service."""
        if (service := _notify_service_for(hass, phone.device_id)) is None:
            return False
        await hass.services.async_call("notify", service, {"message": REQUEST_LOCATION_MESSAGE})
        return True


def _notify_service_for(hass: HomeAssistant, device_id: str) -> str | None:
    """Return the `notify` service of a phone, resolved fresh so renames never break it.

    mobile_app registers `notify.mobile_app_<slug of the app's device name>` per registration.
    """
    if (device := dr.async_get(hass).async_get(device_id)) is None:
        return None
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry is None
            or entry.domain != MOBILE_APP
            or not (name := entry.data.get("device_name"))
        ):
            continue
        service = f"mobile_app_{slugify(name)}"
        if hass.services.has_service("notify", service):
            return service
    return None


#: Every supported source. Add new providers here.
PROVIDERS: tuple[PhoneProvider, ...] = (AndroidCompanionProvider(),)


def discover_phones(hass: HomeAssistant, allowed: set[str]) -> dict[str, Phone]:
    """Return the phones of every provider by device id."""
    phones: dict[str, Phone] = {}
    for provider in PROVIDERS:
        phones.update(provider.discover(hass, allowed))
    return phones
