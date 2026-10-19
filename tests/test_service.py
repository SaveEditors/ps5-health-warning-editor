from __future__ import annotations

import hashlib
import json
import os
import threading

import pytest

pyftpdlib = pytest.importorskip("pyftpdlib")
from pyftpdlib.authorizers import DummyAuthorizer  # noqa: E402
from pyftpdlib.handlers import FTPHandler  # noqa: E402
from pyftpdlib.servers import FTPServer  # noqa: E402

from ps5_health_warning_editor.rco import analyze_rco  # noqa: E402
from ps5_health_warning_editor.service import (  # noqa: E402
    ServiceError,
    apply_text,
    create_session,
)

from .helpers import make_synthetic_rco  # noqa: E402


@pytest.fixture
def ftp_console(tmp_path):
    root = tmp_path / "ftp"
    remote_dir = root / "system_ex" / "vsh_asset"
    remote_dir.mkdir(parents=True)
    live = remote_dir / "Sce.PlayStation.PUI_UI3.rco"
    original, _ = make_synthetic_rco()
    live.write_bytes(original)

    authorizer = DummyAuthorizer()
    authorizer.add_anonymous(str(root), perm="elradfmwMT")

    class Handler(FTPHandler):
        """Allow rename-over-existing, like the console's FTP server."""

        def ftp_RNTO(self, path):
            if not self._rnfr:
                self.respond("503 Bad sequence of commands: use RNFR first.")
                return
            source = self._rnfr
            self._rnfr = None
            try:
                # pyftpdlib hands the handlers already-resolved filesystem
                # paths here; os.replace allows rename-over-existing, which
                # the console's FTP server also allows.
                os.replace(source, path)
            except OSError as exc:
                self.respond(f"550 {exc}.")
            else:
                self.respond("250 Renaming ok.")
                return (source, path)

    Handler.authorizer = authorizer
    Handler.passive_ports = range(50000, 50020)

    server = FTPServer(("127.0.0.1", 0), Handler)
    port = server.socket.getsockname()[1]
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"timeout": 0.2},
        daemon=True,
    )
    thread.start()
    try:
        yield root, live, port, original
    finally:
        server.close_all()
        thread.join(timeout=3)


def test_session_backs_up_locally_and_on_console(ftp_console, tmp_path) -> None:
    root, live, port, original = ftp_console
    backup_dir = tmp_path / "backups"
    events = []

    session = create_session(
        "127.0.0.1",
        port,
        backup_dir,
        lambda message, percent: events.append((message, percent)),
    )

    assert session.backup.local_path.read_bytes() == original
    assert session.backup.local_path.parent == backup_dir
    assert session.backup.size == len(original)
    assert session.backup.sha256 == hashlib.sha256(original).hexdigest()
    assert session.rco.current_body == "Original warning body."

    remote_backup = root / session.backup.remote_path.lstrip("/")
    assert remote_backup.exists()
    assert remote_backup.read_bytes() == original

    manifest = session.backup.local_path.with_suffix(".json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["sha256"] == session.backup.sha256
    assert payload["remote_backup"] == session.backup.remote_path
    assert payload["english_catalogs"] == 2
    assert any("Backups complete" in message for message, _ in events)


def test_apply_verifies_and_replaces_live_file(ftp_console, tmp_path) -> None:
    root, live, port, original = ftp_console
    session = create_session("127.0.0.1", port, tmp_path / "backups")
    new_body = "\u25b3\u25cb\u00d7\u25a1 Edited warning."

    result = apply_text(session, new_body)

    assert result.size == len(original)
    assert result.sha256 == hashlib.sha256(live.read_bytes()).hexdigest()
    updated = live.read_bytes()
    assert len(updated) == len(original)
    assert analyze_rco(updated).current_body == new_body

    remote_backup = root / session.backup.remote_path.lstrip("/")
    assert remote_backup.read_bytes() == original
    assert not (
        root / "system_ex" / "vsh_asset" / "PUI_UI3_NEW.rco.tmp"
    ).exists()


def test_over_limit_apply_leaves_live_file_untouched(ftp_console, tmp_path) -> None:
    _root, live, port, _original = ftp_console
    session = create_session("127.0.0.1", port, tmp_path / "backups")
    before = live.read_bytes()

    with pytest.raises(ServiceError):
        apply_text(session, "a" * (session.rco.max_body + 1))

    assert live.read_bytes() == before
