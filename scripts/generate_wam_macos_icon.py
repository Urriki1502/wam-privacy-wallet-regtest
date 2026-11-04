#!/usr/bin/env python3
"""Isolate the owner WAM coin and emit macOS icon assets.

Does not overwrite design-reference artwork or assets/wam-coin-original.png.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "design-reference" / "og-card.png"
ORIGINAL = ROOT / "assets" / "wam-coin-original.png"
LOGO = ROOT / "assets" / "wam-coin-logo.png"
MASTER = ROOT / "assets" / "wam-coin-logo-1024.png"
ICNS = ROOT / "assets" / "wam-wallet.icns"
ORIGINAL_SHA256 = "1b189fb54969e6229a984f27ade4524bf4c327bb447d6da9fdbef3a8c2c30989"


def isolate_coin(source: Path) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    width, height = image.size
    pixels = image.load()
    cx, cy = (width - 1) / 2.0, (height - 1) / 2.0
    # The supplied artwork is a circular coin on a rectangular black canvas.
    radius = min(width, height) / 2.0 - 1.5
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dest = out.load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            dx, dy = x - cx, y - cy
            distance = (dx * dx + dy * dy) ** 0.5
            if distance > radius:
                continue
            # Soften only the outermost ring so Dock/Finder edges stay circular.
            edge = radius - distance
            alpha = a if edge >= 1.4 else int(a * max(0.0, edge / 1.4))
            dest[x, y] = (r, g, b, alpha)
    bbox = out.getbbox()
    if bbox is None:
        raise SystemExit("WAM_COIN_ISOLATION_DENIED")
    cropped = out.crop(bbox)
    # Keep a small transparent margin so the circular rim is not clipped.
    side = max(cropped.size) + 16
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - cropped.size[0]) // 2, (side - cropped.size[1]) // 2), cropped)
    return canvas


def fit_square(image: Image.Image, size: int) -> Image.Image:
    square = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # Leave ~7% transparent padding so the coin remains circular in the Dock.
    inner = int(size * 0.86)
    scaled = image.resize((inner, inner), Image.Resampling.LANCZOS)
    origin = (size - inner) // 2
    square.paste(scaled, (origin, origin), scaled)
    return square


def main() -> None:
    if sha256(ORIGINAL.read_bytes()).hexdigest() != ORIGINAL_SHA256:
        raise SystemExit("WAM_ORIGINAL_BRAND_IMAGE_DENIED")
    if not SOURCE.is_file():
        raise SystemExit("WAM_OWNER_COIN_ARTWORK_MISSING")
    coin = isolate_coin(SOURCE)
    master = fit_square(coin, 1024)
    LOGO.parent.mkdir(parents=True, exist_ok=True)
    # Runtime Qt branding uses a high-quality transparent coin, not the canvas.
    coin.resize((512, 512), Image.Resampling.LANCZOS).save(LOGO, "PNG", optimize=True)
    master.save(MASTER, "PNG", optimize=True)
    sizes = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    with tempfile.TemporaryDirectory(prefix="wam-iconset-") as tmp:
        iconset = Path(tmp) / "wam-wallet.iconset"
        iconset.mkdir()
        for name, size in sizes.items():
            fit_square(coin, size).save(iconset / name, "PNG")
        subprocess.check_call(["iconutil", "-c", "icns", "-o", str(ICNS), str(iconset)])
    print("logo", sha256(LOGO.read_bytes()).hexdigest())
    print("master", sha256(MASTER.read_bytes()).hexdigest())
    print("icns", sha256(ICNS.read_bytes()).hexdigest())
    print("original_preserved", sha256(ORIGINAL.read_bytes()).hexdigest())
    print("source_preserved", sha256(SOURCE.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
