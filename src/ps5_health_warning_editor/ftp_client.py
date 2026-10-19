"""Thin, testable wrapper around ftplib.

The PS5's FTP server is used in passive mode with anonymous login.  Transfers
are binary.  Downloads are written to a ``.part`` file and moved into place only
after the byte count checks out; uploads are deliberately done to temporary
remote names by the service layer.
"""

from __future__ import annotations

import ftplib
import hashlib
import os
from collections.abc import Callable
from pathlib import Path

ProgressCallback = Callable[[int | None], None]


class FTPError(RuntimeError):
    """A console FTP operation failed."""


class FTPClient:
    def __init__(self, host: str, port: int, timeout: int = 120) -> None:
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self._ftp: ftplib.FTP | None = None

    # -- connection ------------------------------------------------------

    def connect(self) -> None:
        ftp = ftplib.FTP()
        try:
            ftp.connect(self.host, self.port, timeout=self.timeout)
            ftp.login()
        except ftplib.all_errors as exc:
            try:
                ftp.close()
            except Exception:
                pass
            raise FTPError(
                f"Could not connect to the console's FTP server at "
                f"{self.host}:{self.port}: {exc}"
            ) from exc
        self._ftp = ftp

    def close(self) -> None:
        ftp, self._ftp = self._ftp, None
        if ftp is None:
            return
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass

    def __enter__(self) -> FTPClient:
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _require(self) -> ftplib.FTP:
        if self._ftp is None:
            raise FTPError("The FTP connection is not open.")
        return self._ftp

    # -- operations ------------------------------------------------------

    def size(self, remote: str) -> int | None:
        """Return a remote file's size, or None when it cannot be queried."""
        ftp = self._require()
        try:
            raw = ftp.size(remote)
            return int(raw) if raw is not None else None
        except ftplib.error_perm:
            return None
        except ftplib.all_errors:
            return None

    def download(
        self,
        remote: str,
        dest: Path,
        progress: ProgressCallback | None = None,
    ) -> tuple[int, str]:
        """Download remote to dest atomically and return (size, sha256)."""
        ftp = self._require()
        total = self.size(remote)
        if progress:
            progress(0 if total else None)

        digest = hashlib.sha256()
        received = 0
        last_pct = -1
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")

        try:
            with open(part, "wb") as handle:
                def callback(block: bytes) -> None:
                    nonlocal received, last_pct
                    handle.write(block)
                    digest.update(block)
                    received += len(block)
                    if total and progress:
                        pct = int(received * 100 / total)
                        if pct != last_pct:
                            last_pct = pct
                            progress(pct)

                ftp.retrbinary("RETR " + remote, callback, blocksize=65536)

            if total is not None and received != total:
                raise FTPError(
                    f"The download of {remote} was incomplete "
                    f"({received:,} of {total:,} bytes)."
                )
            os.replace(part, dest)
        except FTPError:
            try:
                part.unlink()
            except OSError:
                pass
            raise
        except ftplib.all_errors as exc:
            try:
                part.unlink()
            except OSError:
                pass
            raise FTPError(f"Could not download {remote}: {exc}") from exc

        if progress:
            progress(100)
        return received, digest.hexdigest()

    def upload(
        self,
        src: Path,
        remote: str,
        progress: ProgressCallback | None = None,
    ) -> int:
        """Upload src to remote and return the number of bytes sent."""
        ftp = self._require()
        total = src.stat().st_size
        sent = 0
        last_pct = -1
        if progress:
            progress(0)

        def callback(block: bytes) -> None:
            nonlocal sent, last_pct
            sent += len(block)
            if progress and total:
                pct = int(sent * 100 / total)
                if pct != last_pct:
                    last_pct = pct
                    progress(pct)

        try:
            with open(src, "rb") as handle:
                ftp.storbinary(
                    "STOR " + remote, handle, blocksize=65536, callback=callback
                )
        except ftplib.all_errors as exc:
            raise FTPError(f"Could not upload {remote}: {exc}") from exc

        if sent != total:
            raise FTPError(
                f"The upload of {remote} was incomplete "
                f"({sent:,} of {total:,} bytes)."
            )
        if progress:
            progress(100)
        return sent

    def rename(self, source: str, destination: str) -> None:
        ftp = self._require()
        try:
            ftp.rename(source, destination)
        except ftplib.all_errors as exc:
            raise FTPError(
                f"Could not rename {source} to {destination}: {exc}"
            ) from exc

    def delete(self, remote: str) -> None:
        ftp = self._require()
        try:
            ftp.delete(remote)
        except ftplib.all_errors as exc:
            raise FTPError(f"Could not delete {remote}: {exc}") from exc
