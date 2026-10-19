"""Backup, session, and apply orchestration.

The GUI only calls two functions:

* ``create_session`` downloads the live RCO, backs it up locally and on the
  console, and returns a parsed session.
* ``apply_text`` builds a same-size patched RCO, uploads it to a temporary
  remote name, downloads it back to verify SHA-256, and only then renames it
  over the live file.

This module is independent of Tkinter so it can be tested against a local FTP
server.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .constants import (
    BACKUP_PREFIX,
    REMOTE_APPLY_TMP,
    REMOTE_BACKUP_PREFIX,
    REMOTE_DIR,
    REMOTE_RCO,
)
from .ftp_client import FTPClient
from .rco import BudgetError, RcoError, RcoImage, analyze_rco, build_rco, sha256
from .version import __version__

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, int | None], None]


class ServiceError(RuntimeError):
    """A console operation failed."""


@dataclass(frozen=True)
class BackupRecord:
    local_path: Path
    remote_path: str
    sha256: str
    size: int
    created_at: datetime


@dataclass(frozen=True)
class Session:
    host: str
    port: int
    rco: RcoImage
    backup: BackupRecord


@dataclass(frozen=True)
class ApplyResult:
    sha256: str
    size: int


def _emit(
    callback: EventCallback | None, message: str, percent: int | None = None
) -> None:
    if callback is None:
        return
    try:
        callback(message, percent)
    except Exception:
        logger.exception("UI event callback failed")


def _progress(
    callback: EventCallback | None, message: str
) -> Callable[[int | None], None]:
    def report(percent: int | None) -> None:
        _emit(callback, message, percent)

    return report


def _backup_names(
    backup_dir: Path, now: datetime, token: str
) -> tuple[Path, str]:
    stamp = now.strftime("%Y%m%d-%H%M%S")
    local = backup_dir / f"{BACKUP_PREFIX}_{stamp}_{token}.rco"
    counter = 1
    while local.exists():
        local = backup_dir / f"{BACKUP_PREFIX}_{stamp}_{token}-{counter}.rco"
        counter += 1

    remote_name = local.stem.replace(
        BACKUP_PREFIX, REMOTE_BACKUP_PREFIX, 1
    )
    remote = f"{REMOTE_DIR}/{remote_name}.rco.bak"
    return local, remote


def _write_manifest(
    record: BackupRecord,
    image: RcoImage,
    host: str,
    port: int,
) -> None:
    payload = {
        "schema": 1,
        "application": "PS5 Health Warning Editor",
        "application_version": __version__,
        "created_at": record.created_at.isoformat(),
        "host": host,
        "port": port,
        "source": REMOTE_RCO,
        "remote_backup": record.remote_path,
        "local_file": record.local_path.name,
        "size": record.size,
        "sha256": record.sha256,
        "english_catalogs": len(image.catalogs),
        "catalogs": [
            {
                "offset": catalog.start,
                "size": catalog.end - catalog.start,
                "max_total_bytes": catalog.max_total,
            }
            for catalog in image.catalogs
        ],
        "max_body_bytes": image.max_body,
    }
    path = record.local_path.with_suffix(".json")
    temp = path.with_name(path.name + ".part")
    try:
        temp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, path)
        logger.info("Wrote backup manifest %s", path)
    except OSError as exc:
        logger.warning("Could not write backup manifest %s: %s", path, exc)
        try:
            temp.unlink()
        except OSError:
            pass


def create_session(
    host: str,
    port: int,
    backup_dir: Path,
    on_event: EventCallback | None = None,
    *,
    now: datetime | None = None,
    token: str | None = None,
) -> Session:
    """Download the live RCO and make both backups.

    Editing is only enabled by the caller after this function returns, so a
    failed backup never leads to an edit.
    """
    now = now or datetime.now().astimezone()
    token = token or secrets.token_hex(2)
    backup_dir.mkdir(parents=True, exist_ok=True)
    local, remote = _backup_names(backup_dir, now, token)
    remote_part = remote + ".part"

    _emit(on_event, f"Connecting to {host}:{port} ...")
    ftp = FTPClient(host, port)
    image: RcoImage | None = None
    size = 0
    digest = ""

    try:
        ftp.connect()
        _emit(on_event, "Downloading the current PUI_UI3.rco ...", 0)
        size, digest = ftp.download(
            REMOTE_RCO,
            local,
            _progress(on_event, "Downloading the current PUI_UI3.rco ..."),
        )
        _emit(on_event, f"Local backup saved: {local}", 100)

        image = analyze_rco(local.read_bytes())
        _emit(
            on_event,
            f"Found {len(image.catalogs)} English catalog(s); "
            f"body limit {image.max_body} bytes.",
        )

        _emit(on_event, "Uploading the backup to the console ...", 0)
        ftp.upload(
            local,
            remote_part,
            _progress(on_event, "Uploading the backup to the console ..."),
        )
        remote_size = ftp.size(remote_part)
        if remote_size is not None and remote_size != size:
            raise ServiceError(
                f"The console backup is {remote_size:,} bytes, expected "
                f"{size:,} bytes."
            )
        ftp.rename(remote_part, remote)
        _emit(on_event, f"Console backup saved: {remote}", 100)
        _emit(on_event, "Backups complete. The editor is ready.")
    except Exception as exc:
        try:
            ftp.delete(remote_part)
        except Exception:
            pass
        message = str(exc)
        if local.exists():
            message += (
                f"\n\nThe downloaded original was saved locally at:\n{local}"
            )
        logger.exception("Could not create a console session")
        raise ServiceError(message) from exc
    finally:
        ftp.close()

    assert image is not None  # for type checkers; analyze_rco raises otherwise

    record = BackupRecord(
        local_path=local,
        remote_path=remote,
        sha256=digest,
        size=size,
        created_at=now,
    )
    _write_manifest(record, image, host, port)
    logger.info(
        "Session ready: host=%s port=%s local=%s remote=%s size=%s sha256=%s",
        host,
        port,
        local,
        remote,
        size,
        digest,
    )
    return Session(host=host, port=port, rco=image, backup=record)


def apply_text(
    session: Session,
    body: str,
    on_event: EventCallback | None = None,
) -> ApplyResult:
    """Build, upload, verify, and install the patched RCO.

    The live file is replaced only after the downloaded copy of the temporary
    upload matches the locally built file's SHA-256.
    """
    try:
        output = build_rco(session.rco, body)
    except (RcoError, BudgetError) as exc:
        raise ServiceError(str(exc)) from exc

    digest = sha256(output)
    logger.info(
        "Applying body: host=%s port=%s bytes=%s sha256=%s",
        session.host,
        session.port,
        len(output),
        digest,
    )

    fd, temp_name = tempfile.mkstemp(prefix="pui_apply_", suffix=".rco")
    os.close(fd)
    local_temp = Path(temp_name)
    fd, verify_name = tempfile.mkstemp(prefix="pui_verify_", suffix=".rco")
    os.close(fd)
    verify_temp = Path(verify_name)

    ftp = FTPClient(session.host, session.port)
    renamed = False
    try:
        local_temp.write_bytes(output)
        ftp.connect()
        _emit(on_event, "Uploading the patched RCO ...", 0)
        ftp.upload(
            local_temp,
            REMOTE_APPLY_TMP,
            _progress(on_event, "Uploading the patched RCO ..."),
        )

        _emit(on_event, "Downloading it back to verify SHA-256 ...", 0)
        got_size, got_digest = ftp.download(
            REMOTE_APPLY_TMP,
            verify_temp,
            _progress(
                on_event, "Downloading it back to verify SHA-256 ..."
            ),
        )
        if got_size != len(output) or got_digest != digest:
            raise ServiceError(
                "Upload verification failed, so the live file was not "
                "touched.\n\n"
                f"Expected {len(output):,} bytes / {digest}\n"
                f"Got      {got_size:,} bytes / {got_digest}"
            )

        _emit(on_event, "Verified. Replacing the live file ...")
        ftp.rename(REMOTE_APPLY_TMP, REMOTE_RCO)
        renamed = True
        _emit(on_event, "Applied successfully.", 100)
    except Exception as exc:
        try:
            ftp.delete(REMOTE_APPLY_TMP)
        except Exception:
            pass
        message = str(exc)
        if not renamed:
            message += (
                "\n\nThe live file was not changed. A temporary file may "
                "remain on the console."
            )
        logger.exception("Apply failed")
        raise ServiceError(message) from exc
    finally:
        ftp.close()
        for path in (local_temp, verify_temp):
            try:
                path.unlink()
            except OSError:
                pass

    return ApplyResult(sha256=digest, size=len(output))
