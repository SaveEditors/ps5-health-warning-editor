# Restore the stock warning text

The editor never touches the RCO tree or any other catalog value, so restoring
is just putting a backup file back. Either backup made at Connect time works.

## Option A — local backup (recommended)

1. Open the backups folder: in the editor, **File → Open backups folder**, or
   open `Documents\PS5 Health Warning Editor\backups` manually. The `.json`
   next to each backup records the SHA-256 and the console backup path.
2. Connect to the console's FTP server (anonymous, binary mode, port 1337 on
   AniketosHEN).
3. Upload the original backup over:

   ```
   /system_ex/vsh_asset/Sce.PlayStation.PUI_UI3.rco
   ```

4. Fully power the console off and on.

The warning screen returns to the text that was live when you connected.

## Option B — console backup

If the local file is gone:

1. Connect over FTP and go to `/system_ex/vsh_asset/`.
2. The backup is named `PUI_UI3_BACKUP_<stamp>_<token>.rco.bak`.
3. Download it, then upload it back as `Sce.PlayStation.PUI_UI3.rco`
   (or rename it server-side if your client supports that).
4. Fully power the console off and on.

## Which backup is "stock"?

- The editor's backup is the file as it was when you connected. If the warning
  text was already customized before that, the backup restores that custom
  text — not the factory text.
- For the true factory text on firmware 12.60, use a known stock copy of the
  RCO. Its size must stay 105,673,600 bytes and its SHA-256 is:

  ```
  e7324ad17f37000d205d98d99910f418cf2dbc5be18c93363dc7cdc39639e99f
  ```

- The title stays `Health Warning` either way.

## Safety when restoring

- Prefer the same safe pattern the editor uses: upload to a temp name, copy it
  back / verify the size and hash, then replace the live file. Directly
  overwriting the live file works too, but a dropped connection mid-upload can
  leave the shell without a valid file (recoverable, but avoidable).
- Keep the console on the same firmware while restoring a 12.60 backup.

## If FTP is unavailable

- If the console boots but FTP is unreachable, try a normal reboot. Once the
  shell is up, FTP usually returns.
- If the screen is black or the shell does not start, boot safe mode (hold
  power ~7 seconds until the second beep). Safe mode can reinstall the system
  software; a reinstall may erase data.

This kind of edit cannot hard-brick the console: the boot chain, kernel and
firmware are untouched. The realistic worst case is a soft-brick of the shell,
recoverable by FTP restore or safe mode.
