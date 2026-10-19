# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file/windowed build for PS5 Health Warning Editor."""

from pathlib import Path

root = Path(SPECPATH).resolve().parent
icon = root / "assets" / "icon.ico"
version_file = root / "packaging" / "version_info.txt"
entry = root / "packaging" / "entrypoint.py"

a = Analysis(
    [str(entry)],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(icon), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PIL", "pytest", "pyftpdlib", "setuptools", "pip"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PS5HealthWarningEditor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon),
    version=str(version_file),
)
