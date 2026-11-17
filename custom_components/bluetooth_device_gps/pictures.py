"""Vehicle pictures, stored in `<config>/bluetooth_device_gps/pictures/` and served statically."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from homeassistant.components.file_upload import process_uploaded_file

from .const import DOMAIN, PICTURE_DIR_NAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

MAX_PICTURE_BYTES = 10 * 1024 * 1024
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)


def picture_dir(hass: HomeAssistant) -> Path:
    """Directory that holds the pictures."""
    return Path(hass.config.path(DOMAIN, PICTURE_DIR_NAME))


def _extension(head: bytes) -> str | None:
    """Image type from the file's first bytes (never trust the upload's name)."""
    for magic, ext in _MAGIC:
        if head.startswith(magic):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def ensure_dir(hass: HomeAssistant) -> None:
    """Create the pictures directory (executor)."""
    picture_dir(hass).mkdir(parents=True, exist_ok=True)


def store_upload(hass: HomeAssistant, file_id: str) -> str:
    """Copy an uploaded image into the pictures directory and return its new file name (executor).

    The name is random, so replacing a picture also busts every cache.
    """
    with process_uploaded_file(hass, file_id) as path:
        if path.stat().st_size > MAX_PICTURE_BYTES:
            msg = "Picture too large"
            raise ValueError(msg)
        with path.open("rb") as file:
            ext = _extension(file.read(12))
        if ext is None:
            msg = "Unsupported image type"
            raise ValueError(msg)
        ensure_dir(hass)
        name = f"{uuid4().hex}.{ext}"
        shutil.copyfile(path, picture_dir(hass) / name)
    return name


def cleanup(hass: HomeAssistant, keep: set[str]) -> None:
    """Delete every stored picture that no vehicle references any more (executor)."""
    directory = picture_dir(hass)
    if not directory.is_dir():
        return
    for file in directory.iterdir():
        if file.is_file() and file.name not in keep:
            file.unlink(missing_ok=True)
