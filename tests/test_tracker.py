"""State machine tests with fake Companion app phones (registry entries plus states)."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.bluetooth_device_gps.const import (
    CONF_MACS,
    CONF_PICTURE,
    DOMAIN,
    SUBENTRY_VEHICLE,
)

CAR_MAC = "00:0E:9F:7F:77:DC"
CAR_ATTR = [f"{CAR_MAC} (Car)"]
TRACKER = "device_tracker.car"
GRACE = 20
TIMEOUT = 300


class Phone:
    def __init__(self, hass, name: str, mobile_entry: MockConfigEntry) -> None:
        self.hass = hass
        self.name = name
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=mobile_entry.entry_id, identifiers={("mobile_app", name)}, name=name
        )
        registry = er.async_get(hass)
        self.sensor_id = registry.async_get_or_create(
            "sensor",
            "mobile_app",
            f"{name}-bluetooth_connection",
            device_id=device.id,
            config_entry=mobile_entry,
            suggested_object_id=f"{name}_bluetooth_connection",
        ).entity_id
        self.tracker_id = registry.async_get_or_create(
            "device_tracker",
            "mobile_app",
            name,
            device_id=device.id,
            config_entry=mobile_entry,
            suggested_object_id=name,
        ).entity_id

    def bluetooth(self, connected: list[str] | None) -> None:
        attrs = {"connected_paired_devices": connected or []}
        self.hass.states.async_set(self.sensor_id, str(len(connected or [])), attrs)

    def location(self, lat: float, lon: float, accuracy: float = 10) -> None:
        self.hass.states.async_set(
            self.tracker_id,
            "not_home",
            {"latitude": lat, "longitude": lon, "gps_accuracy": accuracy},
        )


async def _tick(hass, freezer, seconds: float) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def notify_calls(hass):
    return async_mock_service(hass, "notify", "mobile_app_pixel")


@pytest.fixture(autouse=True)
def _notify_service():
    with patch(
        "custom_components.bluetooth_device_gps.providers._notify_service_for",
        return_value="mobile_app_pixel",
    ):
        yield


async def _setup(hass, *phone_names: str):
    mobile = MockConfigEntry(domain="mobile_app")
    mobile.add_to_hass(hass)
    phones = [Phone(hass, name, mobile) for name in phone_names]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bluetooth Device GPS",
        subentries_data=[
            ConfigSubentryData(
                data={CONF_MACS: [CAR_MAC], CONF_PICTURE: None},
                subentry_id="car01",
                subentry_type=SUBENTRY_VEHICLE,
                title="Car",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bluetooth_device_gps.async_setup", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry, phones


async def test_follows_phone_then_parks_on_requested_fix(hass, freezer, notify_calls):
    _, (phone,) = await _setup(hass, "pixel")
    phone.location(40.0, -3.0)
    phone.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()

    state = hass.states.get(TRACKER)
    assert state.attributes["latitude"] == 40.0
    assert state.attributes["phase"] == "connected"
    assert state.attributes["location_source"] == "live"
    assert hass.states.get("binary_sensor.car_connected").state == "on"

    await _tick(hass, freezer, 1)
    phone.location(40.001, -3.001)
    await hass.async_block_till_done()
    assert hass.states.get(TRACKER).attributes["latitude"] == 40.001

    phone.bluetooth([])
    await hass.async_block_till_done()
    assert hass.states.get(TRACKER).attributes["phase"] == "settling"
    # The request goes out immediately, not after the grace period.
    assert [call.data["message"] for call in notify_calls] == ["request_location_update"]

    await _tick(hass, freezer, 2)
    phone.location(40.002, -3.002, accuracy=8)
    await hass.async_block_till_done()
    # A good fix is in, but parking waits for the grace period.
    assert hass.states.get(TRACKER).attributes["phase"] == "settling"

    await _tick(hass, freezer, GRACE)
    state = hass.states.get(TRACKER)
    assert state.attributes["phase"] == "parked"
    assert state.attributes["location_source"] == "requested_fix"
    assert state.attributes["latitude"] == 40.002
    assert state.attributes["last_driver"] == "pixel"
    assert hass.states.get("binary_sensor.car_connected").state == "off"
    assert hass.states.get("sensor.car_parked_since").state != "unknown"
    event = hass.states.get("event.car_activity")
    assert event.attributes["event_type"] == "parked"
    assert event.attributes["latitude"] == 40.002
    assert event.attributes["location_source"] == "requested_fix"
    assert event.attributes["last_driver"] == "pixel"

    phone.bluetooth(CAR_ATTR)  # driving again
    await hass.async_block_till_done()
    event = hass.states.get("event.car_activity")
    assert event.attributes["event_type"] == "departed"
    assert event.attributes["latitude"] == 40.002  # the spot it left


async def test_timeout_falls_back_to_last_live_fix(hass, freezer):
    _, (phone,) = await _setup(hass, "pixel")
    phone.location(40.0, -3.0)
    phone.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()
    phone.bluetooth([])
    await _tick(hass, freezer, GRACE + 1)
    assert hass.states.get(TRACKER).attributes["phase"] == "settling"  # keeps trying
    await _tick(hass, freezer, TIMEOUT + 1)

    state = hass.states.get(TRACKER)
    assert state.attributes["phase"] == "parked"
    assert state.attributes["location_source"] == "last_live"
    assert state.attributes["latitude"] == 40.0


async def test_flap_within_grace_does_not_park(hass, freezer):
    _, (phone,) = await _setup(hass, "pixel")
    phone.location(40.0, -3.0)
    phone.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()
    departed_at = hass.states.get("event.car_activity").state  # the real departure
    phone.bluetooth([])
    await _tick(hass, freezer, GRACE - 5)
    phone.bluetooth(CAR_ATTR)
    await _tick(hass, freezer, 30)

    assert hass.states.get(TRACKER).attributes["phase"] == "connected"
    assert hass.states.get(TRACKER).attributes["latitude"] == 40.0  # nothing was parked
    assert hass.states.get("sensor.car_parked_since").state == "unknown"
    event = hass.states.get("event.car_activity")
    assert event.state == departed_at  # the flap fired no parked/departed event
    assert event.attributes["event_type"] == "departed"


async def test_first_accurate_fix_wins_over_later_ones(hass, freezer):
    _, (phone,) = await _setup(hass, "pixel")
    phone.location(40.0, -3.0)
    phone.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()
    await _tick(hass, freezer, 1)
    phone.bluetooth([])
    await _tick(hass, freezer, 2)
    phone.location(40.0001, -3.0001, accuracy=6)  # at the car
    await _tick(hass, freezer, 5)
    phone.location(40.0100, -3.0100, accuracy=4)  # already walking away, even more accurate
    await _tick(hass, freezer, GRACE)

    state = hass.states.get(TRACKER)
    assert state.attributes["phase"] == "parked"
    assert state.attributes["latitude"] == 40.0001


async def test_poor_fixes_keep_trying_until_timeout(hass, freezer):
    _, (phone,) = await _setup(hass, "pixel")
    phone.location(40.0, -3.0)
    phone.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()
    await _tick(hass, freezer, 1)
    phone.bluetooth([])
    await _tick(hass, freezer, 2)
    phone.location(40.0001, -3.0001, accuracy=200)
    await _tick(hass, freezer, GRACE + 1)
    assert hass.states.get(TRACKER).attributes["phase"] == "settling"

    await _tick(hass, freezer, 5)
    phone.location(40.0002, -3.0002, accuracy=20)  # good enough: parks, grace already over
    await hass.async_block_till_done()
    state = hass.states.get(TRACKER)
    assert state.attributes["phase"] == "parked"
    assert state.attributes["latitude"] == 40.0002


async def test_two_phones_park_only_when_last_one_leaves(hass, freezer, notify_calls):
    _, (a, b) = await _setup(hass, "pixel", "galaxy")
    a.location(40.0, -3.0, accuracy=30)
    b.location(41.0, -4.0, accuracy=5)
    a.bluetooth(CAR_ATTR)
    b.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()
    assert hass.states.get(TRACKER).attributes["latitude"] == 41.0  # best accuracy wins

    a.bluetooth([])
    await _tick(hass, freezer, GRACE + 1)
    assert hass.states.get(TRACKER).attributes["phase"] == "connected"
    assert not notify_calls

    b.bluetooth([])
    await _tick(hass, freezer, GRACE + 1)
    assert hass.states.get(TRACKER).attributes["phase"] == "settling"
    assert len(notify_calls) >= 1


async def test_last_driver_prefers_the_person_entity(hass):
    _, (phone,) = await _setup(hass, "pixel")
    hass.states.async_set(
        "person.ana",
        "home",
        {"friendly_name": "Ana", "device_trackers": [phone.tracker_id]},
    )
    phone.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()
    assert hass.states.get(TRACKER).attributes["last_driver"] == "Ana"
    assert hass.states.get("sensor.car_last_driver").state == "Ana"


async def test_unavailable_sensor_is_not_a_disconnect(hass, freezer, notify_calls):
    _, (phone,) = await _setup(hass, "pixel")
    phone.location(40.0, -3.0)
    phone.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()
    hass.states.async_set(phone.sensor_id, "unavailable")
    await _tick(hass, freezer, GRACE + TIMEOUT)

    assert hass.states.get(TRACKER).attributes["phase"] == "connected"
    assert not notify_calls


async def test_other_bluetooth_device_is_ignored(hass):
    _, (phone,) = await _setup(hass, "pixel")
    phone.location(40.0, -3.0)
    phone.bluetooth(["AA:BB:CC:DD:EE:FF (Headset)"])
    await hass.async_block_till_done()
    assert hass.states.get(TRACKER).attributes["phase"] == "parked"


async def test_state_survives_reload(hass, freezer):
    entry, (phone,) = await _setup(hass, "pixel")
    phone.location(40.0, -3.0)
    phone.bluetooth(CAR_ATTR)
    await hass.async_block_till_done()
    phone.bluetooth([])
    await _tick(hass, freezer, GRACE + 1)
    phone.location(40.002, -3.002, accuracy=8)
    await hass.async_block_till_done()

    with patch("custom_components.bluetooth_device_gps.async_setup", return_value=True):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    state = hass.states.get(TRACKER)
    assert state.attributes["latitude"] == 40.002
    assert state.attributes["phase"] == "parked"


async def test_set_location_service(hass):
    await _setup(hass, "pixel")
    await hass.services.async_call(
        DOMAIN,
        "set_location",
        {"entity_id": TRACKER, "location": {"latitude": 1.5, "longitude": 2.5, "radius": 30}},
        blocking=True,
    )
    state = hass.states.get(TRACKER)
    assert (state.attributes["latitude"], state.attributes["longitude"]) == (1.5, 2.5)
    assert state.attributes["location_source"] == "manual"
    assert state.attributes["gps_accuracy"] == 30


async def test_map_step_sets_location(hass):
    entry, _ = await _setup(hass, "pixel")
    flow = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_VEHICLE),
        context={"source": "reconfigure", "subentry_id": "car01"},
    )
    assert flow["type"] is FlowResultType.MENU
    assert list(flow["menu_options"]) == ["edit_vehicle", "set_location"]
    flow = await hass.config_entries.subentries.async_configure(
        flow["flow_id"], {"next_step_id": "set_location"}
    )
    assert flow["step_id"] == "set_location"
    flow = await hass.config_entries.subentries.async_configure(
        flow["flow_id"], {"location": {"latitude": 10.5, "longitude": 20.5}}
    )
    assert flow["type"] is FlowResultType.ABORT
    assert flow["reason"] == "location_set"
    state = hass.states.get(TRACKER)
    assert (state.attributes["latitude"], state.attributes["longitude"]) == (10.5, 20.5)
    assert state.attributes["location_source"] == "manual"
