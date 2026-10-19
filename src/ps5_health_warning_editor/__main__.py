"""Application entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tkinter as tk
import traceback
from tkinter import messagebox

from . import __version__
from .app import EditorApp
from .constants import APP_NAME
from .logging_setup import setup_logging
from .paths import get_log_path


def _ensure_standard_streams() -> None:
    # A windowed PyInstaller build has no stdout/stderr.  argparse and logging
    # can still be used, but writes must go somewhere.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _ensure_standard_streams()
    parser = argparse.ArgumentParser(
        prog="PS5HealthWarningEditor",
        description="Cold-boot health-warning text editor for PS5.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    setup_logging()
    logger = logging.getLogger(__name__)

    if args.smoke_test:
        try:
            root = tk.Tk()
            root.withdraw()
            EditorApp(root)
            root.update_idletasks()
            root.update()
            root.destroy()
            logger.info("Smoke test passed")
            return 0
        except Exception:
            logger.exception("Smoke test failed")
            return 1

    try:
        root = tk.Tk()
        EditorApp(root)
        root.mainloop()
        return 0
    except Exception:
        logger.exception("Fatal error")
        detail = traceback.format_exc(limit=6)
        try:
            messagebox.showerror(
                APP_NAME,
                "The editor could not start.\n\n"
                f"{detail}\n\nLog file:\n{get_log_path()}",
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
