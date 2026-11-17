# CLAUDE.md

Guidance for Claude Code (claude.ai/code) in this repository.

> **Keep this file current.** In the same change that adds, removes or alters something, update the matching section (*Project status*, *Layout*, *Commands*, conventions, CI/CD). Record decisions and gotchas the code does not show, delete what stopped being true, leave no placeholder text.

> **Everything is written in English**: code, log/error messages, comments, docstrings, docs (README, CLAUDE.md, CHANGELOG), commits, PR titles/descriptions, issue templates, whatever language the conversation uses. Only `custom_components/<domain>/translations/<lang>.json` hold other languages (`en.json` is the source).

<!-- template:start -->
## Template only

Template for HACS integrations (category `integration`) with a working example (`integration_template`: config flow, coordinator, one sensor). `scripts/init.py` turns it into a real integration: renames the domain, replaces placeholders, writes a fresh README, deletes `scripts/init.py`, `scripts/README.template.md`, `.github/workflows/template-check.yml` and this section.

- `template-check.yml` runs `init.py` on a copy and lints/tests it. Any new *kind* of placeholder (`integration_template`, `integration-template`, `IntegrationTemplate`, `Integration Template`, `Hydradox`, `ha-template-integration-hacs`) needs an entry in `scripts/init.py`.
- The release job is skipped when `github.event.repository.is_template`, so the repo must be marked as a template in settings.
- The card template (category `plugin`) is a separate repo: no card or Node-build concerns here.
<!-- template:end -->

## Documentation sources

Home Assistant APIs change fast: check the real thing before relying on memory.

1. **The pinned Home Assistant source** in `.venv/lib/python3.14/site-packages/homeassistant/` is the exact version CI tests against. Read it for signatures and patterns (`components/<domain>/` has 1500+ reference integrations; `helpers/update_coordinator.py`, `config_entries.py`, `components/sensor/`). Prefer well-maintained ones as examples.
2. **Home Assistant developer docs**: https://developers.home-assistant.io (frontend, APIs) and https://contributors.home-assistant.io/core/ (integrations: [files, config flow, fetching data](https://contributors.home-assistant.io/core/integrations/), [entities](https://contributors.home-assistant.io/core/entities/), [quality scale](https://contributors.home-assistant.io/core/quality-scale/), [translations](https://contributors.home-assistant.io/translate/guides/developers/), [brands](https://contributors.home-assistant.io/core/integrations/brands/)). Check the quality scale rules for what "done right" means. Some of these pages move, so search from the section index when a link redirects.
3. **HACS**: https://hacs.xyz/docs/publish/start/ (`hacs.json`, releases), [integration](https://hacs.xyz/docs/publish/integration/), [action and checks](https://hacs.xyz/docs/publish/action/), [default list rules](https://hacs.xyz/docs/publish/include/). When the docs are vague, its source is the authority: https://github.com/hacs/integration (`custom_components/hacs/validate/`, `repositories/`).
4. **Validation and tests**: hassfest https://github.com/home-assistant/actions (run locally with `ghcr.io/home-assistant/hassfest`); pytest helpers https://github.com/MatthewFlamm/pytest-homeassistant-custom-component (mirror of core's test fixtures, so core's `tests/components/<domain>/` are good examples).
5. **Tooling**: [uv](https://docs.astral.sh/uv/), [ruff](https://docs.astral.sh/ruff/), [semantic-release](https://semantic-release.gitbook.io/semantic-release), [Conventional Commits](https://www.conventionalcommits.org).

Fetch these with WebFetch/WebSearch when unsure, and write down any lasting finding in this file.

## Project status

`integration_template` is a Home Assistant custom integration distributed through GitHub and HACS. Replace this with what it does and keep it current: supported devices/APIs, entities and services, config/options flow fields, what is verified in real Home Assistant, known gaps.

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
  - `brand/icon.png` (256×256): required by the HACS `brands` check; local brands need HA 2026.3+ (`hacs.json` `homeassistant`). Never use Home Assistant's own branding.
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
