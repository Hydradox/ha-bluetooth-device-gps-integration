from datetime import UTC, datetime, timedelta

from homeassistant.core import State

from custom_components.bluetooth_device_gps.helpers import (
    Fix,
    normalize_mac,
    parse_macs,
    pick_best_fix,
)
from custom_components.bluetooth_device_gps.providers import AndroidCompanionProvider

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_normalize_mac():
    assert normalize_mac("00:0e:9f:7f:77:dc") == "00:0E:9F:7F:77:DC"
    assert normalize_mac("00-0E-9F-7F-77-DC") == "00:0E:9F:7F:77:DC"
    assert normalize_mac(" 000e9f7f77dc ") == "00:0E:9F:7F:77:DC"
    assert normalize_mac("00:0E:9F:7F:77") is None
    assert normalize_mac("not a mac") is None


def test_parse_macs():
    assert parse_macs(["00:0E:9F:7F:77:DC (Car)", "Headset (aa:bb:cc:dd:ee:ff)", "junk"]) == {
        "00:0E:9F:7F:77:DC",
        "AA:BB:CC:DD:EE:FF",
    }
    assert parse_macs(None) == set()
    assert parse_macs("00:0E:9F:7F:77:DC") == {"00:0E:9F:7F:77:DC"}


def test_pick_best_fix():
    old_exact = Fix(1, 1, 5, NOW)
    new_exact = Fix(2, 2, 5, NOW + timedelta(seconds=1))
    coarse = Fix(3, 3, 80, NOW + timedelta(seconds=2))
    unknown = Fix(4, 4, None, NOW + timedelta(seconds=3))
    assert pick_best_fix([old_exact, new_exact, coarse, unknown]) is new_exact
    assert pick_best_fix([coarse, unknown]) is coarse
    assert pick_best_fix([]) is None


def test_android_provider_reads_every_connected_list():
    provider = AndroidCompanionProvider()
    state = State(
        "sensor.pixel_bluetooth_connection",
        "2",
        {
            "connected_paired_devices": ["00:0E:9F:7F:77:DC (Car)"],
            "connected_not_paired_devices": ["Beacon (aa:bb:cc:dd:ee:ff)"],
            "paired_devices": ["11:22:33:44:55:66 (Headset)"],
        },
    )
    assert provider.parse_connected(state) == {"00:0E:9F:7F:77:DC", "AA:BB:CC:DD:EE:FF"}
    assert provider.parse_connected(State("sensor.x", "unavailable")) is None
    assert provider.parse_connected(State("sensor.x", "0")) == set()
    assert "11:22:33:44:55:66" in provider.known_devices(state)
    devices = provider.known_devices(state)
    assert devices["11:22:33:44:55:66"] == "Headset (11:22:33:44:55:66)"
    assert devices["00:0E:9F:7F:77:DC"] == "Car (00:0E:9F:7F:77:DC)"
