# Building

## Requirements

- Windows 10/11 (64-bit)
- Python 3.10+ (3.13 tested)
- Dev packages: `python -m pip install -e ".[dev]"` — installs pytest,
  pytest-cov, ruff, PyInstaller, pyftpdlib and Pillow

## Tests

```powershell
python -m pytest -q                            # unit + local FTP integration
python -m ruff check .                         # lint
python -m pytest --cov=ps5_health_warning_editor
```

The FTP integration tests start a local `pyftpdlib` server on `127.0.0.1` and
mirror the console's behavior (including rename-over-existing). No console is
needed.

`tests/test_rco.py` builds synthetic RCO catalogs and checks catalog
detection, the byte budget, same-size patching and validation.
`tests/test_service.py` covers Connect (both backups), Apply (temp upload →
SHA-256 verify → rename) and the over-limit rejection path.

## Release build

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# or, to skip tests/lint:
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -SkipTests
```

The script:

1. Runs pytest and ruff.
2. Builds the one-file/windowed exe with
   `packaging\PS5HealthWarningEditor.spec` (icon + Windows version info).
3. Smoke-tests `dist\PS5HealthWarningEditor.exe --smoke-test` (constructs the
   GUI hidden and exits 0).
4. Writes `dist\PS5HealthWarningEditor.exe.sha256`.
5. Creates `release\PS5-Health-Warning-Editor-<version>-win64.zip` containing
   the exe, README, CHANGELOG, LICENSE, START-HERE, `docs/` and the checksum,
   and copies the exe + checksum into `release\`.

`build/`, `dist/` and `release/` are ignored by git.

## Version bump

1. `src/ps5_health_warning_editor/version.py` — `__version__`
2. `pyproject.toml` — `version`
3. `packaging/version_info.txt` — `filevers`/`prodvers` and the string values
4. Add a `CHANGELOG.md` entry

## Icon

`assets/icon.ico` (16/24/32/48/64/128/256) and `assets/icon-256.png` are
generated with Pillow. The spec needs `assets/icon.ico`; the 256 px PNG is for
docs/preview.

## Package layout

```
src/ps5_health_warning_editor/
  __main__.py       argparse entry point (+ hidden --smoke-test)
  app.py            Tk GUI
  constants.py      remote paths, msgids, symbols, tested config
  ftp_client.py     ftplib wrapper (progress, atomic download)
  logging_setup.py  rotating log file
  paths.py          settings/log/backup locations
  rco.py            catalog detection, byte budget, same-size patch
  service.py        backup/session/apply orchestration
  settings.py       host/port/geometry JSON
  version.py        __version__
tests/              pytest suites + synthetic RCO helper
packaging/          spec, version info, entrypoint, build.ps1
assets/             icon
docs/               how-it-works, restore, building, troubleshooting
```

## Runtime data locations

- Settings: `%APPDATA%\PS5HealthWarningEditor\settings.json`
- Log: `%LOCALAPPDATA%\PS5HealthWarningEditor\logs\app.log`
- Backups: `Documents\PS5 Health Warning Editor\backups\`
