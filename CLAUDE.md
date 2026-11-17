# CLAUDE.md

Guidance for Claude Code (claude.ai/code) in this repository.

> **Keep this file current.** In the same change that adds, removes or alters something, update the matching section (*Project status*, *Layout*, *Commands*, conventions, CI/CD). Record decisions and gotchas the code does not show, delete what stopped being true, leave no placeholder text.

> **Everything is written in English**: code, log/error messages, comments, docstrings, docs (README, CLAUDE.md, CHANGELOG), commits, PR titles/descriptions, issue templates, whatever language the conversation uses. Only `custom_components/<domain>/translations/<lang>.json` hold other languages (`en.json` is the source).

## Documentation sources

Home Assistant APIs change fast: check the real thing before relying on memory.

1. **The pinned Home Assistant source** in `.venv/lib/python3.14/site-packages/homeassistant/` is the exact version CI tests against. Read it for signatures and patterns (`components/<domain>/` has 1500+ reference integrations; `helpers/update_coordinator.py`, `config_entries.py`, `components/sensor/`). Prefer well-maintained ones as examples.
2. **Home Assistant developer docs**: https://developers.home-assistant.io (frontend, APIs) and https://contributors.home-assistant.io/core/ (integrations: [files, config flow, fetching data](https://contributors.home-assistant.io/core/integrations/), [entities](https://contributors.home-assistant.io/core/entities/), [quality scale](https://contributors.home-assistant.io/core/quality-scale/), [translations](https://contributors.home-assistant.io/translate/guides/developers/), [brands](https://contributors.home-assistant.io/core/integrations/brands/)). Check the quality scale rules for what "done right" means. Some of these pages move, so search from the section index when a link redirects.
3. **HACS**: https://hacs.xyz/docs/publish/start/ (`hacs.json`, releases), [integration](https://hacs.xyz/docs/publish/integration/), [action and checks](https://hacs.xyz/docs/publish/action/), [default list rules](https://hacs.xyz/docs/publish/include/). When the docs are vague, its source is the authority: https://github.com/hacs/integration (`custom_components/hacs/validate/`, `repositories/`).
4. **Validation and tests**: hassfest https://github.com/home-assistant/actions (run locally with `ghcr.io/home-assistant/hassfest`); pytest helpers https://github.com/MatthewFlamm/pytest-homeassistant-custom-component (mirror of core's test fixtures, so core's `tests/components/<domain>/` are good examples).
5. **Tooling**: [uv](https://docs.astral.sh/uv/), [ruff](https://docs.astral.sh/ruff/), [semantic-release](https://semantic-release.gitbook.io/semantic-release), [Conventional Commits](https://www.conventionalcommits.org).

Fetch these with WebFetch/WebSearch when unsure, and write down any lasting finding in this file.

## Project status

`bluetooth_device_gps` (hub, `single_config_entry`) makes vehicles follow Companion app phones over Bluetooth. See the README for user-facing behaviour; this is what the code does not show.

- **Naming**: users see "device" (not "vehicle", which is only the author's use case). Code identifiers (`vehicle` subentry type, `Vehicle` class, `edit_vehicle` step) keep the old name on purpose: renaming the subentry type would orphan configs of released versions. There is no live-update throttle: the position always follows every phone update.
- **Structure**: one hub entry (options flow = global settings) and one `vehicle` config subentry per vehicle (name, MACs, picture file name). Entities are attached with `config_subentry_id=`. Any options/subentry change reloads the entry through an update listener (so the options flow is a plain `OptionsFlow`, not `OptionsFlowWithReload`).
- **Runtime** (`tracker.py`): `BluetoothGpsManager` in `entry.runtime_data`, push only. Phones are discovered from the entity registry (`mobile_app` sensor whose unique_id ends in `bluetooth_connection`, plus the `device_tracker` of the same device). Every Bluetooth event recomputes each vehicle's holders (`vehicle.macs & phone.connected`), which makes restart recovery and flaps idempotent. Phases: `connected` → `settling` (grace debounce, then fix collection) → `parked`. `unavailable`/`unknown` sensor states never count as a disconnect.
- **Persistence**: vehicle state is saved with `helpers.storage.Store` (not `RestoreEntity`) so the manager can recover before entities exist. A vehicle restored as `connected`/`settling` with no holder goes through the normal grace + settle path.
- **Fix rules**: on the last disconnect the request is sent immediately (waiting would let the user walk away from the car) and fixes are collected until `fix_timeout` ("Location timeout", default 300 s). A fix counts only if it arrived strictly after the disconnect. The first fix at or under `max_accuracy` becomes the `candidate` and later ones never replace it (the user is walking away by then). Parking happens when a candidate exists **and** `disconnect_grace` ("Reconnection tolerance", default 20 s, only guards flaps/restarts) has elapsed; at timeout the best of collected and the recent live fix (`LIVE_FIX_MAX_AGE`) is used; with none the old position is kept (`location_source: stale`). A reconnect at any point cancels the settle.
- **Events**: `Vehicle.fire_event` feeds the `event` entity. `parked` fires at the end of `_finish_settle` (final location); `departed` only when a vehicle goes `parked` → `connected`, never for a settling → connected flap.
- **Translations**: `en.json` is the source and the fallback; `es`, `nl`, `de`, `fr`, `it`, `pl`, `sv`, `da`, `nb` (Norwegian Bokmål, HA's code for Norwegian) and `pt` mirror it key for key. `tests/test_translations.py` fails when a language misses or adds a key, loses `**` markdown or the example MAC, so when a string changes update every file. Setup text refers to the **Add vehicle** button by its translated label.
- **Providers** (`providers.py`): everything specific to a kind of phone sits behind `PhoneProvider` (`discover`, `parse_connected`, `known_devices`, `async_request_location`) and is listed in `PROVIDERS`. Today only `AndroidCompanionProvider`; a new source (e.g. iOS, if it ever exposes connected Bluetooth devices) is one class plus an entry in `PROVIDERS`, with no change in the manager, flow or entities. The options phone selector filters on each provider's `integration`.
- **Notify service** (Android provider): resolved from the device registry on every request (`notify.mobile_app_<slug of the config entry's device_name>`), without importing `mobile_app` (its import chain needs packages missing from the test env; it is only in `after_dependencies`).
- **Manual location**: Reconfigure opens a menu (`edit_vehicle` / `set_location`). `set_location` uses HA's `LocationSelector` map and calls `manager.async_set_location` (no reload, `location_source: manual`); the `set_location` entity service takes the same selector value. The next connect/disconnect overrides it.
- **Pictures**: stored under `<config>/bluetooth_device_gps/pictures/<random>.ext` after a magic-byte check, served from a static path (no auth, so the name is random); unreferenced files are deleted on setup.
- **Timers**: callbacks given to `async_call_later` must be `@callback`/`callback(...)`, otherwise Home Assistant runs them in the executor.
- **Companion app facts** (from companion.home-assistant.io): the Android Bluetooth sensor's state is the number of connected devices, it has `connected_paired_devices`, `connected_not_paired_devices` and `paired_devices` lists and is disabled by default; `request_location_update` is documented as best effort (~5 s, only while the app runs or is in the background, avoid frequent calls). The entry format of the lists is not documented, so MACs are extracted by regex (`MAC (name)` and `name (MAC)` both work) and every `connected_*` attribute counts.
- **Not verified yet**: behaviour with a real phone and car. Tests use fake registry entries and states; the dev container only proves the integration loads and the flows work.
- **Deliberately not built**: a "refresh" service (it would park the vehicle at the phone's current position, wherever that is) and iOS support (the Companion app for iOS has no Bluetooth sensor; add a provider if that changes).

## Commands

Python 3.14 (`.python-version`) with [uv](https://docs.astral.sh/uv/). Node is only for release tooling.

- `uv sync`: locked dev deps (`pytest-homeassistant-custom-component` pins Home Assistant and pytest)
- `uv run pytest` (one test: `-k name`); `uv run ruff check .`; `uv run ruff format .` (`select = ["ALL"]`, ignores in `pyproject.toml`)
- `bash dev/ha.sh up|restart|logs|down|reset`: throwaway Home Assistant in Podman (login `dev`/`dev`), integration mounted read-only, one entry created through its config flow (`dev/setup.mjs`; adapt `FLOW_INPUT` when the flow changes). Use it, not mocks, to check real behaviour; Python changes need `restart`.
- `npm ci` only to run `npx semantic-release --dry-run` locally.

## Layout

- `custom_components/<domain>/` (HACS allows exactly one integration per repo)
  - `manifest.json`: requires `domain`, `name`, `documentation`, `issue_tracker`, `codeowners`, `version`. **`version` is written by the release, never by hand.**
  - `__init__.py` (setup/unload, `entry.runtime_data`), `coordinator.py`, `config_flow.py`, platforms (`sensor.py`, ...), `const.py`
  - `translations/<lang>.json`: no `strings.json` for custom integrations; ship every user-facing string (flow, errors, entity names, services).
  - `brand/icon.png` (256×256): required by the HACS `brands` check; local brands need HA 2026.3+ (`hacs.json` `homeassistant`). Never use Home Assistant's own branding. `brand/icon.svg` is the editable source (phone → Bluetooth waves → car, GPS pin above); regenerate the PNG with `magick -background none -density 384 brand/icon.svg -resize 256x256 PNG32:brand/icon.png`.
- `tests/`: pytest; `enable_custom_integrations` is autouse in `conftest.py`
- `dev/`: dev instance (`ha.sh`, `setup.mjs`, seed `config/configuration.yaml`; other `dev/config` files are git-ignored state)
- `scripts/set-version.mjs`: writes the release version into the manifest (called by semantic-release)

## Integration conventions

- UI config (`config_flow: true`), no YAML-only setup. Validate input in the flow (`errors["base"]`), set a stable `unique_id` and `_abort_if_unique_id_configured()`. Add reauth (`ConfigEntryAuthFailed`) and an options flow when needed.
- One `DataUpdateCoordinator` per entry (pass `config_entry=`); entities extend `CoordinatorEntity`, never poll (`PARALLEL_UPDATES = 0`). Raise `UpdateFailed` when the source is down.
- Runtime objects in `entry.runtime_data` (typed `ConfigEntry[...]` alias), not `hass.data`.
- Entities: `_attr_has_entity_name = True`, `translation_key` names, `unique_id` independent of user-editable names, `DeviceInfo` identifiers `(DOMAIN, entry.entry_id)`, correct `device_class`/`state_class`/units.
- Async I/O: `async_get_clientession(hass)` for HTTP, blocking calls via `hass.async_add_executor_job`. Pin third-party libraries exactly in `manifest.json` `requirements` (not `pyproject.toml`, which is for test deps only).
- Handle `unavailable`/`unknown` and missing data; never block the event loop; never log secrets.

## CI/CD and releases

Workflows in `.github/workflows/`, setup in `.github/actions/setup-python` and `setup-node`:
- `pr-title.yml`: Conventional Commit PR title (`PR title`) and every PR commit (`PR commits`); both are required checks in the `main` ruleset (repo setting).
- `quality.yml`: `lint` (ruff check + format check), `test` (pytest), `hassfest`. On PRs, reused by release.
- `hacs.yml`: `hacs/action`, `category: integration`. On PRs, manual dispatch, and after publishing.
- `release.yml`: push to `main` → `quality` → `publish` (semantic-release, `.releaserc.json`) → `hacs`.
- `dependabot-merge.yml`: squash-merges Dependabot `chore(deps)`/`ci(deps)` PRs once `Quality` passes.

Rules:
- **Never edit `CHANGELOG.md` or the manifest `version` by hand.** semantic-release computes the version from Conventional Commits, `scripts/set-version.mjs` writes it into the manifest, the commit `chore(release): x.y.z [skip ci]` holds `CHANGELOG.md` and the manifest, and tag `vX.Y.Z` points at it (HACS installs the tagged files).
- `feat:` → minor, `fix:`/`perf:` → patch, `feat!:` or `BREAKING CHANGE:` footer → major. `docs`, `refactor` appear in the notes; `chore`, `ci`, `build`, `test`, `style` release nothing. Squash-merge so the PR title becomes the commit.
- `conventional-changelog-conventionalcommits` v10 needs `conventional-changelog-writer` 9 while semantic-release bundles 8: keep the `overrides` in `package.json` (drop once semantic-release depends on writer 9). v10 uses `effect` (`bump`/`changelog`/`hidden`), not `hidden: true`; keep `.releaserc.json` on `effect`.
- First release is `1.0.0`. No asset is attached: HACS downloads `custom_components/<domain>` from the tag. For a zip, set `zip_release: true` and `filename: <domain>.zip` in `hacs.json` and attach it in `.releaserc.json`.
- `main` must let the release push: the ruleset requires `PR title`/`PR commits`, which `chore(release)` cannot have, and `GITHUB_TOKEN` cannot bypass. `release.yml` pushes with the `RELEASE_TOKEN` secret (fine-grained PAT of a repo admin, `Contents: write`) and the ruleset bypass list has the **Repository admin** role.

## HACS requirements

- `hacs.json` in the root: `name`, `render_readme`, `homeassistant` (minimum HA version; only official releases match unless it ends in `b0`).
- Repo needs a description, topics, Issues enabled, an OSI license and a README (settings, not code). The `images` check applies only to plugins/themes.
- Releases are GitHub releases with semver tags `vX.Y.Z` (tags alone are not enough). Keep README options in sync with the config flow.
