from __future__ import annotations

import json

import pytest

from ps5_health_warning_editor.constants import BODY_KEYS, TITLE_KEY
from ps5_health_warning_editor.rco import (
    BodyValidationError,
    BudgetError,
    UnsupportedRcoError,
    analyze_rco,
    build_rco,
    serialized_len,
)

from .helpers import make_catalog, make_synthetic_rco


def test_analyze_finds_only_english_catalogs() -> None:
    data, _ = make_synthetic_rco()
    image = analyze_rco(data)
    assert len(image.catalogs) == 2
    assert image.title == "Health Warning"
    assert image.current_body == "Original warning body."
    assert image.max_body > len(image.current_body)


def test_analyze_rejects_unknown_file() -> None:
    data = b"RCOF" + b"\x00" * 100 + make_catalog("Aviso de salud", "hola")
    with pytest.raises(UnsupportedRcoError):
        analyze_rco(data)


def test_build_is_same_size_and_only_changes_bodies() -> None:
    data, spanish = make_synthetic_rco()
    image = analyze_rco(data)
    new_body = "\u25b3\u25cb\u00d7\u25a1 Hello from the editor"
    output = build_rco(image, new_body)

    assert len(output) == len(data)
    assert spanish in output

    rebuilt = analyze_rco(output)
    assert len(rebuilt.catalogs) == 2
    assert rebuilt.current_body == new_body

    for catalog in rebuilt.catalogs:
        obj = json.loads(output[catalog.start:catalog.end])
        assert obj[TITLE_KEY] == "Health Warning"
        assert all(obj[key] == new_body for key in BODY_KEYS)


def test_budget_boundary() -> None:
    data, _ = make_synthetic_rco()
    image = analyze_rco(data)

    exact = "a" * image.max_body
    output = build_rco(image, exact)
    assert len(output) == len(data)
    assert analyze_rco(output).current_body == exact

    with pytest.raises(BudgetError):
        build_rco(image, "a" * (image.max_body + 1))


def test_escaped_characters_count_serialized_bytes() -> None:
    assert serialized_len("abc") == 3
    assert serialized_len('a"b') == 4
    assert serialized_len("a\nb") == 4


def test_body_validation() -> None:
    data, _ = make_synthetic_rco()
    image = analyze_rco(data)
    for body in ("", "   \n", "bad\x00text"):
        with pytest.raises(BodyValidationError):
            build_rco(image, body)


def test_literal_msgid_text_does_not_break_detection() -> None:
    data, _ = make_synthetic_rco()
    image = analyze_rco(data)
    body = 'text containing "msgid_health_warning" is fine'
    output = build_rco(image, body)
    assert analyze_rco(output).current_body == body


def test_duplicate_keys_are_not_accepted_as_a_catalog() -> None:
    duplicate = (
        b'{"msgid_health_warning":"Health Warning",'
        b'"msgid_health_warning":"Health Warning"}'
    )
    with pytest.raises(UnsupportedRcoError):
        analyze_rco(b"RCOF" + b"\x00" * 60 + duplicate)
