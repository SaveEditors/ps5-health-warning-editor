# Changelog

## 1.0.0 — 2026-10-19

- First release: standalone Windows editor for the PS5 cold-boot health-warning
  body text.
- Connects to the console FTP server and backs up the live
  `Sce.PlayStation.PUI_UI3.rco` locally and on the console before editing is
  enabled. Editing stays blocked if either backup fails.
- Finds the English catalogs by the stock title "Health Warning" and computes
  the real body byte budget from the live file (no baked-in offsets).
- Writes the same body into the four SIE region variants
  (siea/siee/sieasia/siej); the title stays "Health Warning".
- Same-size patch: file size and all other catalog values are unchanged, with
  a re-parse verification after building.
- Apply: temp upload → download-back SHA-256 verification → rename over the
  live file. The live file is never written directly.
- Standalone one-file windowed exe (PyInstaller) with icon and Windows version
  info; no Python install required.
- Symbol palette restricted to glyphs confirmed on cold boot:
  △ (U+25B3), ○ (U+25CB), × (U+00D7), □ (U+25A1), ⭐ (U+2B50).
  `✕` (U+2715) is not in the console's legal-text font — it cold-booted as a
  missing-glyph box, so `×` (U+00D7) is used for the cross instead.
- Console-space note: the console backup is a full ~105 MB copy of the RCO and
  Apply needs ~105 MB free for the temporary file; an aborted upload never
  touches the live file. See docs/TROUBLESHOOTING.md.

Tested on PS5 firmware 12.60 with AniketosHEN. Unofficial; not affiliated with
Sony Interactive Entertainment.
