"""
Draw Cadet Foundry's icons: a gold "CF" monogram on the app's dark background. Run once when the icon changes:

    python tools/make_icons.py        (needs Pillow and a bold font on the developer's computer; Cadet Foundry doesn't)

Writes web/icon-192.png, web/icon-512.png, web/apple-touch-icon.png (180 px), web/icon-maskable-512.png,
web/icon.ico (the desktop, Start menu and installer icon: 16-256 px) and web/icon.svg (the browser tab and website).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WEB = Path(__file__).resolve().parent.parent / "web"
BG, GOLD = (15, 18, 14), (201, 169, 110)          # the app's dark background and tan accent
FONTS = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]


def _font(px: int) -> ImageFont.FreeTypeFont:
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, px)
    raise SystemExit("No bold font found -- add one to FONTS in tools/make_icons.py.")


def icon(size: int, maskable: bool = False, frame: bool = True) -> Image.Image:
    scale = 4                                       # draw large, shrink for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), BG + (255,))
    d = ImageDraw.Draw(img)
    pad = s * (0.20 if maskable else 0.08)          # maskable icons keep the mark inside the safe circle
    framed = frame and size >= 48                   # a thin gold frame; too fussy at desktop-list sizes
    if framed:
        w = max(2, int(s * 0.03))
        d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=s * 0.16, outline=GOLD, width=w)
    inner = s - 2 * pad
    font = _font(int(inner * (0.50 if framed else 0.66)))
    x0, y0, x1, y1 = d.textbbox((0, 0), "CF", font=font)
    d.text(((s - (x1 - x0)) / 2 - x0, (s - (y1 - y0)) / 2 - y0), "CF", font=font, fill=GOLD)
    return img.resize((size, size), Image.LANCZOS)


SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <!-- Cadet Foundry icon: a gold CF monogram on the app's dark background (tools/make_icons.py) -->
  <rect width="256" height="256" rx="44" fill="#0f120e"/>
  <rect x="20" y="20" width="216" height="216" rx="36" fill="none" stroke="#c9a96e" stroke-width="7"/>
  <text x="128" y="128" text-anchor="middle" dominant-baseline="central" fill="#c9a96e"
        font-family="'Segoe UI', Arial, Helvetica, sans-serif" font-weight="700" font-size="112">CF</text>
</svg>
"""


def main() -> None:
    icon(192).convert("RGB").save(WEB / "icon-192.png", optimize=True)
    icon(512).convert("RGB").save(WEB / "icon-512.png", optimize=True)
    icon(180).convert("RGB").save(WEB / "apple-touch-icon.png", optimize=True)
    icon(512, maskable=True).convert("RGB").save(WEB / "icon-maskable-512.png", optimize=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    icon(256).save(WEB / "icon.ico", sizes=[(n, n) for n in sizes],
                   append_images=[icon(n) for n in sizes if n != 256])
    (WEB / "icon.svg").write_text(SVG, encoding="utf-8")
    print("icons written to", WEB)


if __name__ == "__main__":
    main()
