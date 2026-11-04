"""Owner-supplied WAM identity; no generated or fallback artwork."""
from hashlib import sha256
from pathlib import Path
import sys

# Historical owner PNG, retained verbatim in assets/ and never overwritten.
ORIGINAL_SHA256 = "1b189fb54969e6229a984f27ade4524bf4c327bb447d6da9fdbef3a8c2c30989"
# Isolated circular coin derived from design-reference/og-card.png.
LOGO_SHA256 = "6e1dc7be0b1c49c24a406e388869e50f4a9b222c75871f5339c72ff648bfd700"
ICON_SHA256 = "833c0c6149a87d0cfa76dc4f5ee4bc03e0267aa3e326b6223e9ee7eed8b67525"


def brand_image():
    root = (Path(sys._MEIPASS) / "branding" if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2] / "assets")
    image = root / "wam-coin-logo.png"
    if sha256(image.read_bytes()).hexdigest() != LOGO_SHA256:
        raise ValueError("WAM_OWNER_BRAND_IMAGE_DENIED")
    return image


def check_bundle_icon(app):
    import plistlib
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    name = info["CFBundleIconFile"]
    if type(name) is not str or Path(name).name != name:
        raise ValueError("WAM_BUNDLE_ICON_NAME_DENIED")
    icon = app / "Contents/Resources" / name
    if sha256(icon.read_bytes()).hexdigest() != ICON_SHA256:
        raise ValueError("WAM_ORIGINAL_BRAND_ICON_DENIED")
