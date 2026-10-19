"""Application constants.

The tool only touches the English catalogs in PUI_UI3.rco.  Those catalogs are
identified by the stock title "Health Warning"; every other locale uses a
translated title.  Editing the body is therefore possible even after the body
has already been customised.
"""

APP_NAME = "PS5 Health Warning Editor"
APP_ID = "PS5HealthWarningEditor"
APP_DESCRIPTION = "Cold-boot health-warning text editor for PS5"

# Tested configuration.  The tool is not firmware-specific by design, but this
# is the only configuration it has been verified on.
TESTED_FIRMWARE = "12.60"
TESTED_JAILBREAK = "AniketosHEN"

REMOTE_RCO = "/system_ex/vsh_asset/Sce.PlayStation.PUI_UI3.rco"
REMOTE_DIR = "/system_ex/vsh_asset"
REMOTE_APPLY_TMP = "/system_ex/vsh_asset/PUI_UI3_NEW.rco.tmp"

TITLE_KEY = "msgid_health_warning"
TITLE_TEXT = "Health Warning"
BODY_KEYS = (
    "msgid_legal_health_safety_boot_siea",
    "msgid_legal_health_safety_boot_siee",
    "msgid_legal_health_safety_boot_sieasia",
    "msgid_legal_health_safety_boot_siej",
)
ALL_KEYS = (TITLE_KEY,) + BODY_KEYS

DEFAULT_HOST = "192.168.1.155"
DEFAULT_PORT = 1337

# Only glyphs confirmed to render in the console's legal-text font are offered.
# U+2715 ("\u2715") is NOT present in that font: it cold-booted as a missing-glyph
# box, so the cross uses U+00D7 MULTIPLICATION SIGN instead.
SYMBOLS = (
    "\u25b3",  # triangle
    "\u25cb",  # circle
    "\u00d7",  # cross (multiplication sign)
    "\u25a1",  # square
    "\u2b50",  # star (confirmed on cold boot, firmware 12.60)
)

# Hours/minutes/seconds timestamp plus a short random token.  The token avoids
# overwriting a backup if the same second is used more than once.
BACKUP_PREFIX = "PUI_UI3_original"
REMOTE_BACKUP_PREFIX = "PUI_UI3_BACKUP"
