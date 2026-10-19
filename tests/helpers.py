"""Test helpers shared by the RCO and service tests."""

from __future__ import annotations

import json

from ps5_health_warning_editor.constants import BODY_KEYS, TITLE_KEY


def make_catalog(title: str, body: str, pad: int = 0) -> bytes:
    obj = {TITLE_KEY: title}
    obj.update({key: body for key in BODY_KEYS})
    obj["msgid_unrelated"] = "keep-me"
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return raw[:-1] + b" " * pad + raw[-1:]


def make_synthetic_rco() -> tuple[bytes, bytes]:
    """Return (rco bytes, untouched non-English catalog bytes).

    The two English catalogs have different amounts of JSON whitespace, so the
    smaller budget wins.  The non-English catalog proves that only English
    catalogs are touched.
    """
    english_a = make_catalog("Health Warning", "Original warning body.", pad=160)
    english_b = make_catalog("Health Warning", "Original warning body.", pad=180)
    spanish = make_catalog(
        "Aviso de salud", "Texto original de advertencia.", pad=25
    )
    data = (
        b"RCOF" + b"\x00" * 60
        + english_a
        + b"\x00" * 17
        + english_b
        + b"\x00" * 23
        + spanish
        + b"\x00" * 31
    )
    return data, spanish
