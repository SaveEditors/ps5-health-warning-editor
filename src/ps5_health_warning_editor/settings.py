"""Small JSON settings file.

Only connection details and window geometry are stored.  Warning text and FTP
credentials are never persisted.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .constants import DEFAULT_HOST, DEFAULT_PORT
from .paths import get_settings_path

logger = logging.getLogger(__name__)

_GEOMETRY_RE = re.compile(r"\d+x\d+\+-?\d+\+-?\d+")


@dataclass
class Settings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    geometry: str | None = None


def load_settings(path: Path | None = None) -> Settings:
    path = path or get_settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError) as exc:
        logger.warning("Could not read settings %s: %s", path, exc)
        return Settings()

    if not isinstance(data, dict):
        return Settings()

    host = data.get("host", DEFAULT_HOST)
    if not isinstance(host, str) or not host.strip():
        host = DEFAULT_HOST

    try:
        port = int(data.get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    if not 1 <= port <= 65535:
        port = DEFAULT_PORT

    geometry = data.get("geometry")
    if not isinstance(geometry, str) or not _GEOMETRY_RE.fullmatch(geometry):
        geometry = None

    return Settings(host=host.strip(), port=port, geometry=geometry)


def save_settings(settings: Settings, path: Path | None = None) -> bool:
    path = path or get_settings_path()
    payload = {
        "host": settings.host.strip(),
        "port": settings.port,
    }
    if settings.geometry and _GEOMETRY_RE.fullmatch(settings.geometry):
        payload["geometry"] = settings.geometry

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".part")
        temp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, path)
        return True
    except OSError as exc:
        logger.warning("Could not save settings %s: %s", path, exc)
        return False
