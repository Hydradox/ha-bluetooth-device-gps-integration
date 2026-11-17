# Integration Template

> One-line description of what the integration does.

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Hydradox&repository=ha-template-integration-hacs&category=integration)

## Installation

### HACS (recommended)

1. In Home Assistant open **HACS**, menu (⋮) → **Custom repositories**.
2. Add `https://github.com/Hydradox/ha-template-integration-hacs` with category **Integration**.
3. Search for **Integration Template**, download it and restart Home Assistant.
4. **Settings → Devices & services → Add integration → Integration Template**.

### Manual

Copy `custom_components/integration_template` into the `custom_components` folder of your Home Assistant configuration and restart.

## Configuration

Everything is configured from the UI.

| Field | Description |
| ----- | ----------- |
| Name  | Name of this instance |

## Entities

| Entity | Description |
| ------ | ----------- |
| `sensor.<name>_value` | Example sensor |

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
