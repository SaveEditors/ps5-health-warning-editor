from __future__ import annotations

import json

from ps5_health_warning_editor.constants import DEFAULT_HOST, DEFAULT_PORT
from ps5_health_warning_editor.settings import (
    Settings,
    load_settings,
    save_settings,
)


def test_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings(host="10.0.0.5", port=2121, geometry="900x700+10+20")
    assert save_settings(settings, path)
    assert load_settings(path) == settings


def test_invalid_settings_fall_back_to_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"host": "", "port": 99999, "geometry": "junk"}),
        encoding="utf-8",
    )
    settings = load_settings(path)
    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT
    assert settings.geometry is None


def test_missing_settings_use_defaults(tmp_path) -> None:
    assert load_settings(tmp_path / "missing.json") == Settings()
