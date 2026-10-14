"""Owner-supplied WAM identity; no generated or fallback artwork."""
from hashlib import sha256
from pathlib import Path
import sys

ORIGINAL_SHA256 = "1b189fb54969e6229a984f27ade4524bf4c327bb447d6da9fdbef3a8c2c30989"
ICON_SHA256 = "dc8c4de2aeac66e062ac530b2a462e639646e02b3cfe5a7ba6f8c4bd8f571fb7"


def brand_image():
    root = (Path(sys._MEIPASS) / "branding" if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2] / "assets")
    image = root / "wam-coin-original.png"
    if sha256(image.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("WAM_ORIGINAL_BRAND_IMAGE_DENIED")
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
