# Bluetooth Device GPS

> Remember where your vehicles are parked: a vehicle follows the phone connected to its Bluetooth address and stays at the last good GPS fix when the phone disconnects.

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hydradox&repository=ha-bluetooth-device-gps-integration&category=integration)

## Installation

### HACS (recommended)

1. In Home Assistant open **HACS**, menu (⋮) → **Custom repositories**.
2. Add `https://github.com/Hydradox/ha-bluetooth-device-gps-integration` with category **Integration**.
3. Search for **Bluetooth Device GPS**, download it and restart Home Assistant.
4. **Settings → Devices & services → Add integration → Bluetooth Device GPS**.

### Manual

Copy `custom_components/bluetooth_device_gps` into the `custom_components` folder of your Home Assistant configuration and restart.

Available in English (default and fallback), Dutch, French, German, Italian, Norwegian (Bokmål), Polish, Portuguese, Spanish, Swedish and Danish.

## How it works

1. A vehicle is a `device_tracker` with a name, an optional picture and a list of Bluetooth MAC addresses (for example `00:0E:9F:7F:77:DC`).
2. While a phone with the Home Assistant Companion app is connected to one of those addresses (read from its **Bluetooth connection** sensor), the vehicle follows the phone's location live.
3. When the last phone disconnects, the integration asks the phone for a fresh location (`request_location_update`) **immediately** and keeps trying for up to 5 minutes. The vehicle is parked at the first fix that is accurate enough (once a short minimum time has passed, so brief drops and engine restarts do not park it). If none is accurate enough by the end, it uses the best fix received, otherwise the last live position.
4. If several phones are connected, the vehicle is parked only when the last one leaves and the most accurate fix wins.

## Requirements

- Android phones with the Companion app. Enable the **Bluetooth connection** sensor in the app (*Settings → Companion app → Manage sensors*). iOS has no equivalent sensor, so it is not supported.
- Location permission and a GPS-reporting device tracker on the phone.

## Configuration

Everything is configured from the UI. Add the integration once, then use **Add vehicle** for each vehicle.

**Vehicle** (one per vehicle, editable with *Reconfigure*):

| Field | Description |
| ----- | ----------- |
| Name | Name of the vehicle |
| Bluetooth addresses | MACs picked from the devices your phones know, or typed. A MAC can belong to one vehicle only |
| Picture | Optional JPEG, PNG, GIF or WebP (max 10 MB) shown as the entity picture |

**Options** (shared by all vehicles):

| Option | Default | Description |
| ------ | ------- | ----------- |
| Phones | all | Only these phones move vehicles; empty allows every phone with the sensor |
| Minimum time before parking | 20 s | The request is sent at once; parking waits at least this long so short drops do not park the vehicle |
| Location request duration | 5 min | How long to keep trying for an accurate fix before using the best one available |
| Good enough accuracy | 50 m | Park as soon as a fix is at least this accurate |
| Minimum seconds between live updates | 0 | Throttle for the live position while driving |

## Entities

Per vehicle (one device):

| Entity | Description |
| ------ | ----------- |
| `device_tracker.<vehicle>` | GPS position. Attributes: `phase` (`connected`, `settling`, `parked`), `location_source` (`live`, `requested_fix`, `last_live`, `stale`, `manual`), `last_driver`, `fix_time` |
| `binary_sensor.<vehicle>_connected` | On while a phone is connected to the vehicle |
| `event.<vehicle>_activity` | Fires `parked` (when the final location is known) and `departed` (when a phone connects to a parked vehicle). Attributes: `latitude`, `longitude`, `accuracy`, `location_source`, `last_driver`, `parked_at`. Use it as an automation trigger, for example to notify where you parked |
| `sensor.<vehicle>_last_driver` | Name of the phone that connected last |
| `sensor.<vehicle>_parked_since` | When the vehicle was parked (unknown while driving) |

To place a vehicle by hand (for example after a phone ran out of battery) use either:

- **Settings → Devices & services → Bluetooth Device GPS → the vehicle's ⋮ menu → Reconfigure → Set the location on the map**, or
- the service `bluetooth_device_gps.set_location` with a `location` (map picker; the radius is stored as accuracy).

## Known limitations

- Home Assistant only sees when the phone *reports*: if the phone has no data connection in an underground garage, the disconnect and the new fix arrive late and the vehicle may be parked where the phone got signal again. Place the vehicle on the map to correct it.
- Changing a vehicle or the options reloads the integration; parked positions are kept.

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
