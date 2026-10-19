# PS5 Health Warning Editor

Standalone Windows editor for the text of the PS5 cold-boot **Health Warning**
screen. No Python needed: run the exe, connect to the console's FTP server,
edit the warning body, hit Apply, restart the console.

Tested on **PS5 firmware 12.60** with **AniketosHEN** (its built-in FTP
server).

> Unofficial tool. Not affiliated with Sony Interactive Entertainment.
> Same-size edit of one unsigned asset; worst case is recoverable (see Safety).

## What it changes

One file:

```
/system_ex/vsh_asset/Sce.PlayStation.PUI_UI3.rco
```

Inside that RCO are 32 plaintext JSON locale catalogs. The tool finds the two
English catalogs (default/en-US and en-GB) and writes the same body text into
the four SIE region variants:

```
msgid_legal_health_safety_boot_siea     (SIE America)
msgid_legal_health_safety_boot_siee     (SIE Europe)
msgid_legal_health_safety_boot_sieasia  (SIE Asia)
msgid_legal_health_safety_boot_siej     (SIE Japan)
```

The title `msgid_health_warning` ("Health Warning") is left alone. Non-English
console languages keep their own stock text. The file size, offsets and every
other catalog value are unchanged.

## Quick start

1. Turn the console on and make sure its FTP server is running
   (AniketosHEN: usually port 1337).
2. Run `PS5HealthWarningEditor.exe`.
3. Enter the console IP and FTP port, click **Connect**.
   The tool downloads the live RCO and makes two timestamped backups before it
   lets you edit anything:
   - local: `Documents\PS5 Health Warning Editor\backups\`
   - console: `/system_ex/vsh_asset/PUI_UI3_BACKUP_*.rco.bak`
4. Type the new warning body. There is no character limit in the box; the byte
   limit is calculated from the live catalogs, shown live and enforced.
5. Click **Apply to console**. The tool builds the RCO at exactly the same
   size, uploads it to a temporary name, downloads it back and checks
   SHA-256, and only then replaces the live file.
6. Fully power the console off and on. The warning screen only appears on a
   real cold boot, not Rest Mode. On success the tool says:
   **Restart console to see changes!**

## Symbols

The palette only offers glyphs confirmed on firmware 12.60 cold boots:

| glyph | codepoint | status |
|---|---|---|
| △ | U+25B3 | renders |
| ○ | U+25CB | renders |
| × | U+00D7 | used for the cross because `✕` (U+2715) is missing from the console font and rendered as a box |
| □ | U+25A1 | renders |
| ⭐ | U+2B50 | renders (gold star) |

Other symbols may or may not exist in the console's legal-text font.

## Backups and restore

Every successful **Connect** makes both backups before editing is enabled. If
either backup fails, editing stays blocked. The full restore procedure is in
[docs/RESTORE-STOCK.md](docs/RESTORE-STOCK.md).

Short version: upload `PUI_UI3_original_*.rco` (local) or the console
`PUI_UI3_BACKUP_*.rco.bak` over the live `Sce.PlayStation.PUI_UI3.rco`, then
cold boot.

## Safety

- Same-size edit: the RCO tree/offsets and every other value stay identical.
- The live file is replaced only after a temp upload + SHA-256 download check.
- vsh_asset RCOs are not signature-checked. This cannot hard-brick the console;
  worst case is a soft-brick (shell fails to render), recoverable by FTP
  restore or safe mode.
- One change at a time. Keep the stock backup until the console has cold-booted
  with the new text.

## Requirements

- Windows 10/11 (64-bit).
- PS5 on 12.60 with AniketosHEN (or another FTP server exposing `/`).
- The editor only patches the English catalogs. A non-English console UI shows
  its own stock warning.

## Building from source

See [docs/BUILDING.md](docs/BUILDING.md). In short:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

The build script runs the tests, builds the one-file windowed exe with
PyInstaller, smoke-tests it, writes `dist\PS5HealthWarningEditor.exe.sha256`,
and produces `release\PS5-Health-Warning-Editor-<version>-win64.zip`.

## Docs

- [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md) — boot chain, catalogs, byte
  budget, same-size patch, FTP backup/apply flow.
- [docs/RESTORE-STOCK.md](docs/RESTORE-STOCK.md) — restore from either backup.
- [docs/BUILDING.md](docs/BUILDING.md) — dev setup and release build.
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — common failures.

## Repo layout

```
src/ps5_health_warning_editor/   application package
tests/                           unit + local FTP integration tests
packaging/                       PyInstaller spec, version info, build script
assets/                          app icon
docs/                            how-it-works, restore, build, troubleshooting
```

## License

MIT — see [LICENSE](LICENSE).
