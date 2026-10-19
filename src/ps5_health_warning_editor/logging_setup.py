"""File logging with rotation.

The GUI shows a short activity log; the full log is written here for
troubleshooting.  No warning text or credentials are logged.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import get_log_path


def setup_logging(path: Path | None = None) -> Path:
    path = path or get_log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Avoid duplicate handlers when a test or reload calls this twice.
    for handler in root.handlers:
        if isinstance(handler, RotatingFileHandler):
            return path

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    )

    try:
        file_handler = RotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        # A read-only install directory should not prevent the app from
        # running; the GUI log still works.
        pass

    if not getattr(sys, "frozen", False) and sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        root.addHandler(console)

    logging.getLogger(__name__).info(
        "Logging started: %s (frozen=%s, python=%s)",
        path,
        getattr(sys, "frozen", False),
        sys.version.split()[0],
    )
    return path
