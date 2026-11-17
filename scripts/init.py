#!/usr/bin/env python3
"""Turn this template into your integration (run once, then it deletes itself).

    python3 scripts/init.py                       # asks for everything
    python3 scripts/init.py --domain my_thing --name "My Thing" --repo owner/ha-my-thing

It renames `custom_components/integration_template`, replaces every placeholder, writes a fresh
README for your integration and removes the template-only files (this script included).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Placeholders of the template. The repo slug goes first because it contains the owner.
TEMPLATE_DOMAIN = "integration_template"
TEMPLATE_NAME = "Integration Template"
TEMPLATE_CLASS = "IntegrationTemplate"
TEMPLATE_SLUG = "Hydradox/ha-template-integration-hacs"  # owner/repo, as in URLs
TEMPLATE_OWNER = "Hydradox"
TEMPLATE_REPO = "ha-template-integration-hacs"

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".ruff_cache", ".pytest_cache"}
SKIP_SUFFIXES = {".png", ".jpg", ".ico", ".pyc"}
TEMPLATE_ONLY = [
    "scripts/init.py",
    "scripts/README.template.md",
    ".github/workflows/template-check.yml",
]


def ask(prompt: str, default: str | None = None) -> str:
    """Ask on the terminal."""
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default or ""


def text_files() -> list[Path]:
    """Every text file of the repository."""
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not SKIP_DIRS.intersection(path.relative_to(ROOT).parts)
        and path.suffix not in SKIP_SUFFIXES
        and path.name != "LICENSE"
    ]


def main() -> int:
    """Run the initialisation."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--domain", help="integration domain, e.g. my_thing (snake_case, never changes later)"
    )
    parser.add_argument("--name", help='display name, e.g. "My Thing"')
    parser.add_argument("--repo", help="GitHub repository, e.g. owner/ha-my-thing")
    args = parser.parse_args()

    if not (ROOT / "custom_components" / TEMPLATE_DOMAIN).is_dir():
        print("Nothing to do: this repository has already been initialised.")
        return 1

    domain = args.domain or ask("Domain (snake_case, permanent)")
    name = args.name or ask("Display name", domain.replace("_", " ").title())
    repo = args.repo or ask("GitHub repository (owner/name)")

    if not re.fullmatch(r"[a-z][a-z0-9_]*", domain):
        print(
            "The domain must be snake_case (lowercase letters, digits, underscores).",
            file=sys.stderr,
        )
        return 1
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        print("The repository must look like owner/name.", file=sys.stderr)
        return 1
    if not name:
        print("The display name cannot be empty.", file=sys.stderr)
        return 1

    owner, repo_name = repo.split("/")
    class_prefix = "".join(re.findall(r"[A-Za-z0-9]+", name.title().replace("_", " ")))
    replacements = [
        (TEMPLATE_SLUG, repo),
        (f"@{TEMPLATE_OWNER}", f"@{owner}"),
        (f"owner={TEMPLATE_OWNER}", f"owner={owner}"),  # my.home-assistant.io badge
        (TEMPLATE_REPO, repo_name),
        (TEMPLATE_DOMAIN, domain),
        (TEMPLATE_DOMAIN.replace("_", "-"), domain.replace("_", "-")),
        (TEMPLATE_CLASS, class_prefix),
        (TEMPLATE_NAME, name),
    ]

    # The README becomes the integration one before the placeholders are applied to it.
    readme_template = (ROOT / "scripts" / "README.template.md").read_text(encoding="utf-8")
    (ROOT / "README.md").write_text(readme_template, encoding="utf-8")

    for path in text_files():
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = original
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != original:
            path.write_text(updated, encoding="utf-8")

    # CLAUDE.md: drop the sections that only make sense in the template.
    claude = ROOT / "CLAUDE.md"
    claude.write_text(
        re.sub(
            r"<!-- template:start -->.*?<!-- template:end -->\n+",
            "",
            claude.read_text(encoding="utf-8"),
            flags=re.DOTALL,
        ),
        encoding="utf-8",
    )

    shutil.move(ROOT / "custom_components" / TEMPLATE_DOMAIN, ROOT / "custom_components" / domain)

    for relative in TEMPLATE_ONLY:
        (ROOT / relative).unlink(missing_ok=True)
    (ROOT / "CHANGELOG.md").unlink(missing_ok=True)

    print(f"\nDone: {name} ({domain}) for github.com/{repo}\n")
    print("Next steps:")
    print("  1. uv sync && uv run pytest        # checks that everything still works")
    print(f"  2. Replace custom_components/{domain}/brand/icon.png with your icon")
    print("  3. Commit with a Conventional Commit message and push to main")
    print("  4. Repository settings (see CLAUDE.md, 'CI/CD and releases'):")
    print("     description + topics + Issues enabled; squash-merge only;")
    print("     ruleset on main requiring 'PR title', 'PR commits', lint, test, hassfest;")
    print("     secret RELEASE_TOKEN (PAT of an admin, Contents: write) + admin bypass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
