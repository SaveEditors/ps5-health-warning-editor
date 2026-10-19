# Troubleshooting

## "Could not connect..." / connection refused

- Console on? FTP server started? AniketosHEN's default FTP port is **1337**.
- Same network? Use the console's IP (e.g. `192.168.1.155`), not the PC's.
- Windows firewall: outbound connections are normally fine; allow
  Python/the exe on private networks if Windows asks.
- Confirm with an FTP client (FileZilla): anonymous login, port 1337.

## Editing stays disabled after Connect

Editing only turns on after **both** backups succeed. If the console backup
upload fails, the error message includes the path of the local backup that was
already written. Check free space on the console's writable partition, then
Connect again.

## "Over limit by N bytes" / Apply is greyed out

The health strings share a 641-byte budget per catalog. With the stock title
the body limit is **156 UTF-8 bytes**:

- △ ○ □ ⭐ are 3 bytes each; ASCII is 1 byte.
- A newline is serialized as `\n` and counts as 2 bytes.
- `"` and `\` are escaped and add 1 byte each.
- Shorten the text; the counters show the exact values.

## "Upload verification failed"

The temp upload's SHA-256 did not match the locally built file. The tool
deleted the temp file and did not touch the live file. Retry; if it keeps
happening the FTP transfer is being corrupted or interrupted. Wired network
recommended.

## Console still shows old/stock text after Apply

- The warning screen only appears on a full cold boot. Rest Mode and a normal
  reboot skip it. Power off completely (wait for the light to go out), then on.
- If the console UI language is not English, its own stock catalog is used.
  This tool patches only the English catalogs.
- If you see a previous custom text, the apply did not complete. Check the log.

## A symbol shows as a box

That glyph is missing from the console's legal-text font. Known on 12.60:
△ ○ □ ⭐ render; `✕` (U+2715) does not. The editor therefore offers only
verified glyphs and uses `×` (U+00D7) for the cross. If you paste another
symbol, test it on a cold boot and replace it with ASCII if it shows as a box.

## Where are the log and the backups?

- Log: `%LOCALAPPDATA%\PS5HealthWarningEditor\logs\app.log`
  (in the app: **Help → Open log file**)
- Backups: `Documents\PS5 Health Warning Editor\backups\`
  (in the app: **File → Open backups folder**)

## How do I undo everything?

See [RESTORE-STOCK.md](RESTORE-STOCK.md). Either backup (local `.rco` or the
console `.rco.bak`) can be uploaded back over the live file, followed by a cold
boot.

## The exe does nothing / antivirus warning

The exe is unsigned (PyInstaller one-file build). Some antivirus tools flag
unsigned one-file executables. Verify the SHA-256 against
`PS5HealthWarningEditor.exe.sha256` from the release, and allow the file if it
matches. The source is in this repo if you prefer to build it yourself.
