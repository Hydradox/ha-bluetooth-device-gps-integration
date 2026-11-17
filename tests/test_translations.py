"""Every translation must have exactly the keys of en.json (the source and the fallback)."""

import json
from pathlib import Path

import pytest

DIR = Path(__file__).parent.parent / "custom_components" / "bluetooth_device_gps" / "translations"
EXPECTED = {"da", "de", "en", "es", "fr", "it", "nb", "nl", "pl", "pt", "sv"}


def _flatten(data: dict, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], str]:
    flat: dict[tuple[str, ...], str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, (*prefix, key)))
        else:
            flat[(*prefix, key)] = value
    return flat


SOURCE = _flatten(json.loads((DIR / "en.json").read_text(encoding="utf-8")))


def test_expected_languages_exist():
    assert {file.stem for file in DIR.glob("*.json")} == EXPECTED


@pytest.mark.parametrize("lang", sorted(EXPECTED - {"en"}))
def test_translation_matches_source(lang):
    flat = _flatten(json.loads((DIR / f"{lang}.json").read_text(encoding="utf-8")))
    assert set(flat) == set(SOURCE), f"{lang}: keys differ from en.json"
    for key, text in flat.items():
        assert text.strip(), f"{lang}: empty {key}"
        assert text.count("**") == SOURCE[key].count("**"), f"{lang}: markdown differs in {key}"
        assert ("00:0E:9F:7F:77:DC" in text) == ("00:0E:9F:7F:77:DC" in SOURCE[key]), (
            f"{lang}: example MAC differs in {key}"
        )
