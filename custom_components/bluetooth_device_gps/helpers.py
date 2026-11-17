"""Pure helpers: MAC parsing and fix selection (no Home Assistant state)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import MAC_RE, MAC_SEARCH_RE

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from homeassistant.core import State


@dataclass(frozen=True)
class Fix:
    """A location fix."""

    latitude: float
    longitude: float
    accuracy: float | None
    time: datetime


def normalize_mac(raw: str) -> str | None:
    """Return `AA:BB:CC:DD:EE:FF`, or None when `raw` is not a MAC address."""
    raw = raw.strip()
    if not MAC_RE.match(raw):
        return None
    digits = "".join(ch for ch in raw if ch not in ":-").upper()
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


def parse_macs(value: str | Iterable[object] | None) -> set[str]:
    """Extract every MAC from a companion app attribute (list of `MAC (name)` strings)."""
    if value is None:
        return set()
    items = [value] if isinstance(value, str) else list(value)
    macs: set[str] = set()
    for item in items:
        for match in MAC_SEARCH_RE.finditer(str(item)):
            if mac := normalize_mac(match.group(0)):
                macs.add(mac)
    return macs


def fix_from_state(state: State | None) -> Fix | None:
    """Build a fix from a device_tracker state, or None when it has no usable coordinates."""
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    try:
        latitude = float(state.attributes["latitude"])
        longitude = float(state.attributes["longitude"])
    except KeyError, TypeError, ValueError:
        return None
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        return None
    accuracy = state.attributes.get("gps_accuracy")
    try:
        accuracy = float(accuracy) if accuracy is not None else None
    except TypeError, ValueError:
        accuracy = None
    return Fix(latitude, longitude, accuracy, state.last_updated)


def pick_best_fix(fixes: Iterable[Fix]) -> Fix | None:
    """Best accuracy wins (unknown accuracy is the worst), the newest fix breaks ties."""
    return min(
        fixes,
        key=lambda fix: (
            fix.accuracy if fix.accuracy is not None else math.inf,
            -fix.time.timestamp(),
        ),
        default=None,
    )
