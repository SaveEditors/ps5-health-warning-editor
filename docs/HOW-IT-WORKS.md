# How it works

## The screen

Cold boot (full power off → on):

1. **PS logo / familymark splash** — drawn by `/SceSysAvControl.elf` from a
   bitmap inside the signed binary on the read-only rootfs. Locked, not
   editable.
2. **Health Warning screen** — text from
   `/system_ex/vsh_asset/Sce.PlayStation.PUI_UI3.rco`. **This is the screen the
   editor changes.**
3. **Boot animation** (particles, etc.) — separate files.
4. Home screen.

Warm boot and Rest Mode resume skip the warning screen, so a change only shows
up after a real power cycle.

## The file

`/system_ex/vsh_asset/Sce.PlayStation.PUI_UI3.rco` is 105,673,600 bytes on
firmware 12.60. It contains 32 plaintext JSON locale catalogs (msgid → string
maps, 24,105 keys each). The English ones:

| catalog | offset | size |
|---|---|---|
| default / en-US | 18,447,808 | 2,168,287 |
| en-GB | 33,882,432 | 2,169,945 |

The tool does not require those exact offsets: it scans the live file for
`{"msgid` objects and finds the English catalogs by the stock title
`Health Warning`. That means it also works on a console whose warning text has
already been customized (as long as the title is still the stock one), and the
byte budget is always calculated from the live file.

## The five strings

```
msgid_health_warning                    title (left unchanged)
msgid_legal_health_safety_boot_siea     SIE America body
msgid_legal_health_safety_boot_siee     SIE Europe body
msgid_legal_health_safety_boot_sieasia  SIE Asia body
msgid_legal_health_safety_boot_siej     SIE Japan body
```

The screen shows the title plus exactly one body variant, chosen by the
console's SIE region. The catalog is chosen by the system UI language
(English → one of the two patched catalogs). The editor writes the same body
into all four variants in both English catalogs, so any region shows the same
text while the UI language is English.

## Byte budget

The five values share a fixed serialized budget inside each catalog. Stock:

```
14 + 62 + 227 + 227 + 111 = 641 bytes
```

A same-size patch must keep each catalog blob at its exact byte size. The tool
re-serializes the catalog compactly, replaces the four bodies, then pads with
spaces (valid JSON whitespace) after `"msgid_health_warning":` back to the
original size. For four identical bodies and the stock title:

```
14 + 4 × body ≤ 641   →   body ≤ 156 bytes
```

- Count UTF-8 bytes, not characters. △ ○ □ ⭐ are 3 bytes each; ASCII is 1.
- `"` and `\` are escaped and add 1 serialized byte each; a real newline
  becomes `\n` (2 serialized bytes instead of 1).
- The title shares the budget, but this tool keeps it stock.

The GUI shows the limit and the current size live; Apply is disabled while the
body is over the limit or empty.

## The same-size patch

For each English catalog:

1. Parse the JSON catalog (catalogs with duplicate keys or an unexpected shape
   are skipped).
2. Verify the title is exactly `Health Warning`.
3. Set the four body values to the new text.
4. Serialize compactly (`ensure_ascii=False`, separators `,` and `:`), UTF-8.
5. Pad with spaces after the title key to the exact original blob size.
6. Re-parse and verify: only the four body values differ, the title is
   unchanged, and every other value is identical.
7. Write the blob back at the same offset; assert the file size is unchanged.

The RCO tree, block table and all 30 other catalogs are untouched. vsh_asset
RCOs are not signature-checked, which is why this works.

## Connect / backup flow

When you click **Connect**:

1. Connect to the console's FTP server (anonymous, binary, passive).
2. Download the live RCO to a timestamped local backup:
   `Documents\PS5 Health Warning Editor\backups\PUI_UI3_original_<stamp>_<token>.rco`
3. Compute SHA-256, parse the file and calculate the body budget.
4. Upload the same file to the console as
   `/system_ex/vsh_asset/PUI_UI3_BACKUP_<stamp>_<token>.rco.bak`
   (uploaded to a `.part` name, size-checked, then renamed).
5. Write a `.json` manifest next to the local backup: source size and SHA-256,
   catalog offsets, byte budget, console backup path.

Editing stays disabled unless both backups succeed.

The console backup is a full copy of the RCO (~105 MB), and Apply needs about
the same amount again for the temporary file. If the console's writable space
is tight, delete old `PUI_UI3_BACKUP_*.rco.bak` files over FTP before applying
(see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)).

## Apply flow

When you click **Apply to console**:

1. Build the same-size RCO in memory.
2. Upload it to `/system_ex/vsh_asset/PUI_UI3_NEW.rco.tmp`.
3. Download that temp file back and compare its SHA-256 with the built file.
4. Only if it matches, rename the temp file over the live
   `Sce.PlayStation.PUI_UI3.rco`.
5. Clean up local temp files. If anything fails before the rename, the live
   file is untouched and the console temp file is deleted.

## Glyph support

Measured on firmware 12.60 cold boots:

| glyph | codepoint | result |
|---|---|---|
| △ | U+25B3 | renders |
| ○ | U+25CB | renders |
| □ | U+25A1 | renders |
| ⭐ | U+2B50 | renders (gold star) |
| ✕ | U+2715 | missing glyph (box) |

The editor uses `×` (U+00D7 MULTIPLICATION SIGN) for the cross. Other symbols
may or may not exist in the console's legal-text font; test one on a cold boot
before keeping it.

## Limitations

- Only the English catalogs are patched. A non-English console UI keeps its own
  stock warning.
- Only the body text is changed; the title stays `Health Warning`.
- The body is limited to 156 UTF-8 bytes with the stock title (see above).
- Tested on firmware 12.60 with AniketosHEN. Other firmware/jailbreak
  combinations are not verified; the tool reads the live catalogs, so a
  different layout will be rejected rather than patched blindly.
