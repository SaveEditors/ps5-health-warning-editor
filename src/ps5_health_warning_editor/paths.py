"""Filesystem locations used by the application."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .constants import APP_ID


def resource_path(relative: str | Path) -> Path:
    """Return a path to a bundled resource.

    In a PyInstaller one-file build the data is unpacked under ``sys._MEIPASS``.
    During development the repository root is two levels above this package.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parents[2] / relative


def _roaming_dir() -> Path:
    raw = os.environ.get("APPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Roaming"


def _local_dir() -> Path:
    raw = os.environ.get("LOCALAPPDATA")
    if raw:
        return Path(raw)
    return Path.home() / "AppData" / "Local"


def documents_dir() -> Path:
    """Return the user's Documents folder, including OneDrive redirection."""
    if os.name == "nt":
        try:
            import winreg

            key_path = (
                r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                r"\User Shell Folders"
            )
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "Personal")
            expanded = os.path.expandvars(str(value))
            if expanded:
                return Path(expanded)
        except OSError:
            pass
    return Path.home() / "Documents"


def get_settings_path() -> Path:
    return _roaming_dir() / APP_ID / "settings.json"


def get_log_path() -> Path:
    return _local_dir() / APP_ID / "logs" / "app.log"


def get_backup_dir() -> Path:
    return documents_dir() / "PS5 Health Warning Editor" / "backups"
