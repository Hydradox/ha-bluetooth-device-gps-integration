# Bluetooth Device GPS

> Remember where your vehicles (or anything with Bluetooth) are parked: a device follows the phone connected to its Bluetooth address and stays at the last good GPS fix when the phone disconnects.

Available in English (default and fallback), Dutch, French, German, Italian, Norwegian (Bokmål), Polish, Portuguese, Spanish, Swedish and Danish.

## Installation

### Marketplace (recommended)

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hydradox&repository=ha-bluetooth-device-gps-integration&category=integration)

### Manual

Copy `custom_components/bluetooth_device_gps` into the `custom_components` folder of your Home Assistant configuration and restart.

## Quick start

1. On each Android phone enable the **Bluetooth connection** sensor in the Companion app (*Settings → Companion app → Manage sensors*) and allow location access.
2. Add the integration, then **Add device**: name, the car's Bluetooth address (pick it from the list your phones know) and an optional picture.
3. Drive. The device follows your phone while connected and stays where you parked.

## How it works

1. A device is a `device_tracker` with a name, an optional picture and a list of Bluetooth MAC addresses (for example `00:0E:9F:7F:77:DC`).
2. While a phone with the Home Assistant Companion app is connected to one of those addresses (read from its **Bluetooth connection** sensor), the device follows the phone's location live.
3. When the last phone disconnects, the integration asks the phone for a fresh location (`request_location_update`) **immediately** and keeps trying for up to 5 minutes. The device is parked at the first location that is accurate enough (once the reconnection tolerance has passed, so brief drops and engine restarts do not park it). If none is accurate enough by the end, it uses the best location received, otherwise the last live position.
4. If several phones are connected, the device is parked only when the last one leaves and the most accurate fix wins.

## Requirements

- Android phones with the Companion app and its **Bluetooth connection** sensor enabled (it is disabled by default). iOS has no equivalent sensor, so it is not supported yet. A repair notice appears if no phone has the sensor.
- Location permission and a GPS-reporting device tracker on the phone.

## Configuration

Everything is configured from the UI. Add the integration once, then use **Add device** for each device.

**Device** (one per device, editable with *Reconfigure*):

| Field | Description |
| ----- | ----------- |
| Name | Name of the device |
| Bluetooth addresses | MACs picked from the Bluetooth devices your phones know, or typed. A MAC can belong to one device only |
| Picture | Optional JPEG, PNG, GIF or WebP (max 10 MB) shown as the entity picture |

**Options** (shared by all devices):

| Option | Default | Description |
| ------ | ------- | ----------- |
| Allowed phones (whitelist) | all | Only these phones can move devices; empty allows every phone with the sensor |
| Reconnection tolerance | 20 s | The location is requested at once, but the device is parked only after this time, so a short drop or an engine restart (phone reconnecting in between) does not park it |
| Location timeout | 5 min | How long to keep asking the phone for an accurate location before using the best one available |
| Minimum accuracy | 50 m | Park as soon as a location is at least this accurate (metres) |

## Entities

Per device (one device):

| Entity | Description |
| ------ | ----------- |
| `device_tracker.<device>` | GPS position. Attributes: `phase` (`connected`, `settling`, `parked`), `location_source` (`live`, `requested_fix`, `last_live`, `stale`, `manual`, `home`), `last_driver`, `fix_time` |
| `binary_sensor.<device>_connected` | On while a phone is connected to the device |
| `event.<device>_activity` | Fires `parked` (when the final location is known) and `departed` (when a phone connects to a parked device). Attributes: `latitude`, `longitude`, `accuracy`, `location_source`, `last_driver`, `parked_at`. Use it as an automation trigger, for example to notify where you parked |
| `sensor.<device>_last_driver` | Person (the `person` entity that has the phone's `device_tracker`) who connected last; falls back to the phone's name when no person is linked |
| `sensor.<device>_parked_since` | When the device was parked (unknown while driving) |

To place a device by hand (for example after a phone ran out of battery) use either:

- **Settings → Devices & services → Bluetooth Device GPS → the device's ⋮ menu → Reconfigure → Set the location on the map**, or
- the service `bluetooth_device_gps.set_location` with a `location` (map picker; the radius is stored as accuracy).

## Known limitations

- The Companion app's location request is best effort (the app documents it as "hit or miss", about 5 s, and only while the app runs or is in the background). That is why the integration keeps retrying and falls back to the last live position.
- Home Assistant only sees when the phone *reports*: if the phone has no data connection in an underground garage, the disconnect and the new fix arrive late and the device may be parked where the phone got signal again. Place the device on the map to correct it.
- Changing a device or the options reloads the integration; parked positions are kept.

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node 22+ (release tooling) and, for the dev instance, Podman.

```bash
uv sync                   # Python and Home Assistant test dependencies
uv run ruff check . && uv run ruff format --check .
uv run pytest
bash dev/ha.sh up         # throwaway Home Assistant on http://localhost:8123 (login dev / dev)
```

Other `dev/ha.sh` commands: `restart` (after changing the code), `logs`, `down`, `reset`.

Commit messages and PR titles follow [Conventional Commits](https://www.conventionalcommits.org): `feat:` releases a minor version, `fix:`/`perf:` a patch and `feat!:` a major one. The release (tag, GitHub release, `CHANGELOG.md` and the `manifest.json` version) is automatic when a PR is merged into `main`. Never edit them by hand.
