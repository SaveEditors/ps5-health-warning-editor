"""Reading and same-size patching of PUI_UI3.rco.

The health-warning strings live in plaintext JSON catalogs inside the RCO.  A
catalog is a flat object of ``msgid`` keys.  This module finds the English
catalogs, calculates how much room the five health-warning values have, and
rewrites the four region bodies without changing the RCO's size or offsets.

Nothing here knows about FTP or the GUI, which makes it easy to test.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .constants import ALL_KEYS, BODY_KEYS, TITLE_KEY, TITLE_TEXT


class RcoError(Exception):
    """Base class for RCO errors."""


class UnsupportedRcoError(RcoError):
    """The file is not a supported PUI_UI3.rco."""


class BudgetError(RcoError):
    """The requested body would not fit the fixed catalog size."""


class BodyValidationError(RcoError):
    """The requested body is empty or contains invalid characters."""


@dataclass(frozen=True)
class Catalog:
    start: int
    end: int
    max_total: int
    current_body: str


@dataclass(frozen=True)
class RcoImage:
    data: bytes
    catalogs: tuple[Catalog, ...]
    sha256: str

    @property
    def title(self) -> str:
        return TITLE_TEXT

    @property
    def current_body(self) -> str:
        return self.catalogs[0].current_body

    @property
    def max_body(self) -> int:
        return min(
            max(0, (catalog.max_total - serialized_len(TITLE_TEXT)) // 4)
            for catalog in self.catalogs
        )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_end_bytes(buf: bytes, start: int) -> int:
    """Return the index just past the matching close brace of a JSON object."""
    i, depth, in_str, esc = start, 0, False, False
    while i < len(buf):
        c = buf[i]
        if in_str:
            if esc:
                esc = False
            elif c == 0x5C:  # backslash
                esc = True
            elif c == 0x22:  # quote
                in_str = False
        else:
            if c == 0x22:
                in_str = True
            elif c == 0x7B:  # {
                depth += 1
            elif c == 0x7D:  # }
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    raise UnsupportedRcoError(
        f"JSON object starting at offset {start} is not terminated."
    )


def iter_json_blobs(data: bytes):
    """Yield (start, end) for every top-level ``{"msgid"`` object."""
    i = data.find(b'{"msgid')
    while i != -1:
        end = json_end_bytes(data, i)
        yield i, end
        i = data.find(b'{"msgid', end)


def serialized_len(value: str) -> int:
    """Length of a string as a JSON value, without the surrounding quotes."""
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8")) - 2


def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def analyze_rco(data: bytes) -> RcoImage:
    """Find the English health-warning catalogs and their byte budgets.

    English catalogs are identified by the exact stock title "Health Warning".
    The body values may already be customised.  Every catalog is expected to be
    a compact JSON object padded with JSON whitespace; the slack is included in
    the available budget.
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) < 32:
        raise UnsupportedRcoError("The file is too small to be a PUI_UI3.rco.")

    catalogs: list[Catalog] = []
    for start, end in iter_json_blobs(bytes(data)):
        blob = data[start:end]
        if not all(f'"{key}"'.encode() in blob for key in ALL_KEYS):
            continue

        try:
            obj = json.loads(blob, object_pairs_hook=_no_duplicate_keys)
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get(TITLE_KEY) != TITLE_TEXT:
            continue
        if any(not isinstance(obj.get(key), str) for key in ALL_KEYS):
            continue

        try:
            full_len = len(
                json.dumps(
                    obj, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")
            )
        except UnicodeEncodeError:
            continue

        slack = (end - start) - full_len
        if slack < 0:
            raise UnsupportedRcoError(
                f"The catalog at offset {start} is not in the expected compact "
                "layout, so a same-size edit cannot be guaranteed."
            )

        current_total = serialized_len(obj[TITLE_KEY]) + sum(
            serialized_len(obj[key]) for key in BODY_KEYS
        )
        catalogs.append(
            Catalog(
                start=start,
                end=end,
                max_total=current_total + slack,
                current_body=obj[BODY_KEYS[0]],
            )
        )

    if not catalogs:
        raise UnsupportedRcoError(
            "No English health-warning catalogs were found "
            "(title 'Health Warning').\n\n"
            "This does not look like a supported Sce.PlayStation.PUI_UI3.rco."
        )

    return RcoImage(data=bytes(data), catalogs=tuple(catalogs), sha256=sha256(data))


def validate_body(body: str) -> None:
    if not isinstance(body, str):
        raise BodyValidationError("The warning text must be a string.")
    if not body.strip():
        raise BodyValidationError("The warning text cannot be empty.")
    if "\x00" in body:
        raise BodyValidationError(
            "The text contains a NUL character, which is not supported."
        )
    try:
        body.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BodyValidationError(
            "The text contains invalid Unicode."
        ) from exc


def build_rco(image: RcoImage, body: str) -> bytes:
    """Return a same-size RCO with the new body in every English catalog."""
    validate_body(body)
    data = bytearray(image.data)

    for catalog in image.catalogs:
        size = catalog.end - catalog.start
        obj = json.loads(image.data[catalog.start:catalog.end])
        if obj.get(TITLE_KEY) != TITLE_TEXT:
            raise RcoError("The catalog title changed unexpectedly.")

        for key in BODY_KEYS:
            obj[key] = body

        try:
            serialized = json.dumps(
                obj, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        except UnicodeEncodeError as exc:
            raise BodyValidationError(
                "The text contains invalid Unicode."
            ) from exc

        if len(serialized) > size:
            raise BudgetError(
                f"The text is too long for the catalog at offset "
                f"{catalog.start}.\n\n"
                f"It would grow by {len(serialized) - size} bytes. "
                f"The maximum body is {image.max_body} bytes; this text is "
                f"{serialized_len(body)} bytes."
            )

        pad = size - len(serialized)
        anchor = f'"{TITLE_KEY}":'.encode()
        anchor_at = serialized.find(anchor)
        if anchor_at < 0:
            raise RcoError("The catalog padding anchor is missing.")
        insert_at = anchor_at + len(anchor)
        serialized = (
            serialized[:insert_at] + b" " * pad + serialized[insert_at:]
        )

        check = json.loads(serialized)
        if check.get(TITLE_KEY) != TITLE_TEXT or any(
            check.get(key) != body for key in BODY_KEYS
        ):
            raise RcoError("Internal verification failed after serializing.")
        if len(serialized) != size:
            raise RcoError("Internal error: catalog size changed.")
        data[catalog.start:catalog.end] = serialized

    if len(data) != len(image.data):
        raise RcoError("Internal error: file size changed.")

    output = bytes(data)

    # Only the four body values may differ from the source file.
    for catalog in image.catalogs:
        old = json.loads(image.data[catalog.start:catalog.end])
        new = json.loads(output[catalog.start:catalog.end])
        if list(old.keys()) != list(new.keys()):
            raise RcoError("Internal error: catalog key order changed.")
        if new.get(TITLE_KEY) != TITLE_TEXT:
            raise RcoError("Internal error: the title changed.")
        for key, value in old.items():
            if key not in BODY_KEYS and new.get(key) != value:
                raise RcoError(
                    f"Internal error: unrelated catalog value changed ({key})."
                )
        if any(new.get(key) != body for key in BODY_KEYS):
            raise RcoError("Internal verification failed.")

    return output
