"""PyInstaller entry point.

Kept outside the package so relative imports work correctly in the frozen
one-file build.
"""

from ps5_health_warning_editor.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
