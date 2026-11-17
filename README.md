# ha-template-integration-hacs

Template to create a **Home Assistant custom integration** distributed through **HACS** (category `integration`), with the quality checks, automated releases and development environment already wired up. For Lovelace cards (category `plugin`) use the sibling card template.

It ships a small working example (config flow, coordinator, one sensor, tests) so everything is green from the first commit. You replace the example with your integration.

## What is included

| Area | What you get |
| ---- | ------------ |
| Integration | `custom_components/integration_template/`: manifest, UI config flow, `DataUpdateCoordinator`, sensor platform, `runtime_data`, translations (`en`, `es`), `brand/icon.png` |
| Tests | pytest + [`pytest-homeassistant-custom-component`](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) (config flow, setup/unload, entity state) |
| Lint | [ruff](https://docs.astral.sh/ruff/) (`select = ["ALL"]`) for lint and format, Python 3.14 managed with [uv](https://docs.astral.sh/uv/) |
| CI on pull requests | Conventional Commit PR title and commits, `lint`, `test`, Home Assistant `hassfest`, HACS validation |
| CD on `main` | [semantic-release](https://semantic-release.gitbook.io): version from Conventional Commits, `CHANGELOG.md`, `manifest.json` version, tag and GitHub release, then HACS validation |
| Maintenance | Dependabot (uv, npm, GitHub Actions) with automatic squash-merge of tooling updates once CI passes |
| Dev environment | `dev/ha.sh`: throwaway Home Assistant in Podman with the integration mounted and configured through its own config flow |
| AI guidance | `CLAUDE.md` with the Home Assistant conventions, commands and CI/CD rules |

## Create your integration

1. Click **Use this template → Create a new repository** (or `gh repo create my-org/ha-my-thing --template Hydradox/ha-template-integration-hacs --public --clone`).
2. Clone it and run the initialiser once. It renames the domain, replaces every placeholder (names, URLs, code owner, class names), writes a fresh README for your integration and deletes the template-only files, itself included:

   ```bash
   python3 scripts/init.py                       # asks for everything
   python3 scripts/init.py --domain my_thing --name "My Thing" --repo my-org/ha-my-thing
   ```

   | Value | Example | Notes |
   | ----- | ------- | ----- |
   | Domain | `my_thing` | `snake_case`. It is the folder name and the config entry domain, so it **cannot change later** |
   | Name | `My Thing` | Display name (`manifest.json`, `hacs.json`, UI) |
   | Repository | `my-org/ha-my-thing` | `owner/name` on GitHub; the owner becomes the code owner |

3. Check that everything still works, then replace the example code:

   ```bash
   uv sync
   uv run ruff check . && uv run ruff format --check .
   uv run pytest
   ```

4. Replace `custom_components/<domain>/brand/icon.png` (256×256 PNG) with your icon. The HACS `brands` check requires it, and Home Assistant 2026.3+ reads it from there.
5. Commit with a Conventional Commit message (`feat: initial integration`) and push to `main`. Do it before enabling the ruleset below, or use a pull request.
6. Complete the [repository setup](#repository-setup).

## Repository setup

These are GitHub settings; they cannot be stored in the code.

**Template repository** (only for this repo, not for the ones you generate): *Settings → General → Template repository*. The release job is skipped while `is_template` is true.

**Every repository created from it**

1. *Settings → General*: add a **description** and **topics** (for example `home-assistant`, `hacs`, `integration`) and keep **Issues** enabled. HACS validates all three. Allow **squash merging** and disable merge commits and rebase merging, so the PR title becomes the commit that drives the version.
2. *Settings → Rules → Rulesets*: protect `main` and require pull requests and these status checks: `PR title`, `PR commits`, `lint`, `test`, `hassfest`.
3. *Release token*. The release commit (`chore(release): x.y.z [skip ci]`) cannot pass the required checks and `GITHUB_TOKEN` cannot be a ruleset bypass actor, so:
   - create a fine-grained personal access token of a repository admin with **Contents: Read and write** on this repository,
   - save it as the Actions secret `RELEASE_TOKEN`,
   - add the **Repository admin** role to the ruleset bypass list.

   Without the secret the workflow falls back to `GITHUB_TOKEN`, which is rejected by the ruleset.
4. *Settings → Actions → General → Workflow permissions*: leave the default; each workflow declares its own permissions.
5. *Settings → Advanced Security*: enable **secret scanning with push protection**, **Dependabot alerts** and **private vulnerability reporting**. Never commit tokens, `.env` files or real Home Assistant data: `RELEASE_TOKEN` lives only in Actions secrets, and `dev/config` (the throwaway instance state, user `dev`/`dev`) is git-ignored and only listens on `127.0.0.1`.

## Development

Requirements: [uv](https://docs.astral.sh/uv/), Node 22+ (release tooling only) and Podman (dev instance only).

| Command | What it does |
| ------- | ------------ |
| `uv sync` | Install the locked dev dependencies (Home Assistant, pytest, ruff) |
| `uv run pytest` | Run the tests |
| `uv run ruff check .` / `uv run ruff format .` | Lint / format |
| `bash dev/ha.sh up` | Start Home Assistant on http://localhost:8123 (login `dev` / `dev`) with one entry of your integration already configured |
| `bash dev/ha.sh restart` | Restart it after changing the Python code |
| `bash dev/ha.sh logs` / `down` / `reset` | Follow logs / stop (state kept) / wipe the state |

If you add fields to the config flow, adapt `FLOW_INPUT` in `dev/setup.mjs`. The `HA_IMAGE` and `HA_PORT` environment variables change the image and the port.

## How releases work

1. Open a pull request. Its title must be a [Conventional Commit](https://www.conventionalcommits.org): `feat:` bumps the minor version, `fix:` and `perf:` the patch, and `feat!:` (or a `BREAKING CHANGE:` footer) the major. `docs` and `refactor` appear in the notes; `chore`, `ci`, `build`, `test` and `style` release nothing.
2. CI runs `lint`, `test`, `hassfest` and HACS validation.
3. Squash-merge into `main`. The `Release` workflow runs the same quality checks and then semantic-release writes the version into `manifest.json`, updates `CHANGELOG.md`, commits `chore(release): x.y.z [skip ci]`, tags `vX.Y.Z` and creates the GitHub release. HACS installs `custom_components/<domain>` from that tag.
4. HACS validates the repository once the release exists. The first release is `1.0.0`.

Never edit the version in `manifest.json` or `CHANGELOG.md` by hand.

## Good to know

- **One integration per repository.** HACS only manages one folder under `custom_components/`.
- **Minimum Home Assistant version.** `hacs.json` sets `homeassistant: 2026.3.0`, the first version that reads brand images from the integration folder. It works like Android's `minSdkVersion`, only coarser: HACS refuses to install or update on an older Home Assistant (it reads the file from the default branch) and does nothing else, there are no per-feature fallbacks. Home Assistant has no API levels and removes deprecated APIs quickly, so set it to the oldest version you actually test against and raise it when you start using newer APIs. Only official releases match unless you append `b0` (`2026.3.0b0`).
- **Python version.** `.python-version` and `requires-python` follow what the pinned Home Assistant needs (currently 3.14). Dependabot updates `pytest-homeassistant-custom-component`, which moves Home Assistant along with it.
- **Runtime requirements** (libraries your integration imports) go in `manifest.json` `requirements`, pinned, not in `pyproject.toml`.
- **Zip release.** By default no asset is attached: HACS downloads the tagged folder. To ship a zip, set `zip_release: true` and `filename: <domain>.zip` in `hacs.json` and attach the zip in `.releaserc.json`.
- **Template CI.** `.github/workflows/template-check.yml` generates a copy with other values and lints and tests it, so the template does not rot. `init.py` deletes it from your repository.
- The code is licensed under GPL-3.0 (see `LICENSE`). Change the license in your generated repository if you prefer another one.
