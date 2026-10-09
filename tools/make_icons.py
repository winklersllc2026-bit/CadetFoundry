"""
Draw Vanguard's app icons (PNG) for "Add to Home Screen" / "Install app". Run once when the icon changes:

    python tools/make_icons.py        (needs Pillow on the developer's computer; Vanguard itself doesn't)

Writes web/icon-192.png, web/icon-512.png, web/apple-touch-icon.png (180 px) and web/icon-maskable-512.png.
"""
from pathlib import Path

from PIL import Image, ImageDraw

WEB = Path(__file__).resolve().parent.parent / "web"
BG, GOLD = (15, 18, 14), (201, 169, 110)          # the app's dark background and tan accent


def icon(size: int, maskable: bool = False) -> Image.Image:
    scale = 4                                       # draw large, shrink for smooth edges
    s = size * scale
    img = Image.new("RGB", (s, s), BG)
    d = ImageDraw.Draw(img)
    pad = s * (0.22 if maskable else 0.14)          # maskable icons keep the mark inside the safe circle
    w = s - 2 * pad
    stroke = w * 0.16
    # a chevron "V" (the vanguard: out in front), with a small bar over it
    left, right, top = pad, s - pad, pad + w * 0.30
    bottom = pad + w * 0.92
    d.line([(left + stroke / 2, top), (s / 2, bottom - stroke / 2), (right - stroke / 2, top)], fill=GOLD,
           width=int(stroke), joint="curve")
    bar_y = pad + w * 0.10
    d.rounded_rectangle([s / 2 - w * 0.18, bar_y, s / 2 + w * 0.18, bar_y + stroke * 0.7], radius=stroke * 0.35, fill=GOLD)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    icon(192).save(WEB / "icon-192.png", optimize=True)
    icon(512).save(WEB / "icon-512.png", optimize=True)
    icon(180).save(WEB / "apple-touch-icon.png", optimize=True)
    icon(512, maskable=True).save(WEB / "icon-maskable-512.png", optimize=True)
    print("icons written to", WEB)


if __name__ == "__main__":
    main()
