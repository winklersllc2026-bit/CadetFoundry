"""
Build the demo kit: a USB drive to hand over, plus everything to turn a Raspberry Pi (Zero 2 W or newer) into a
portable Vanguard with its own Wi-Fi.

    python tools/make_demo_kit.py E:\\
    python tools/make_demo_kit.py E:\\ --wifi-password "eagle-river-472" --ssid Vanguard
    python tools/make_demo_kit.py E:\\ --with-ai          (the USB also carries the offline AI for laptops)

Needs Pillow and qrcode on THIS computer (python -m pip install qrcode pillow); Vanguard itself needs neither.
Run  python site/build.py  first so the installer goes on the drive and onto the Pi's download page.

Adds to the drive (besides everything tools/make_usb.py puts there):
    demo/Demo-Card.html       print it: Wi-Fi name, password and address, with QR codes for phones
    demo/vanguard-demo.conf   the Wi-Fi name and password tools/pi_setup.sh reads on the Pi
    demo/README-PI.txt        how to set up the Pi
"""
from __future__ import annotations

import base64
import html
import io
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import make_usb  # noqa: E402

ADDRESS = "http://vanguard.lan"
FALLBACK = "http://10.42.0.1"
WORDS = ("eagle", "river", "summit", "anchor", "harbor", "ranger", "falcon", "cedar", "valley", "compass",
         "granite", "liberty", "beacon", "meadow", "canyon", "timber", "glacier", "prairie", "orchard", "lantern")

README_PI = """VANGUARD DEMO BOX - RASPBERRY PI SETUP
=====================================

You need: a Raspberry Pi Zero 2 W (or newer), a microSD card (16 GB+), a power supply or USB power bank,
and - once, for setup - internet for the Pi.

1. On a computer, use Raspberry Pi Imager to write "Raspberry Pi OS Lite (64-bit)" to the microSD card.
   In Imager's settings (the gear / "Edit settings"): set a username and password, your home Wi-Fi, and turn on SSH.
2. Put the card in the Pi and power it on. Wait two minutes for it to join your home Wi-Fi.
3. Copy the "Vanguard" and "demo" folders from this USB drive to the Pi. From a Windows computer on the same Wi-Fi
   (replace pi with your username and raspberrypi with the Pi's name):
       scp -r E:\\Vanguard E:\\demo pi@raspberrypi.local:~/
   (Or plug this drive into the Pi with a micro-USB OTG adapter and copy the two folders from it.)
4. Connect to the Pi and run the setup (it asks you to choose the Instructor PIN):
       ssh pi@raspberrypi.local
       sudo sh ~/Vanguard/tools/pi_setup.sh
5. At the end the Pi switches to its own Wi-Fi network: {ssid}. From now on it starts Vanguard by itself
   whenever it has power - no internet, no screen, no keyboard.

Using it
  * Join the Wi-Fi "{ssid}" (password: {password}) on a phone, tablet or laptop, then open {address}
    (or {fallback}). The printed Demo-Card has QR codes for both.
  * First time: "+ New profile" -> choose instructor -> enter the Instructor PIN. Cadets make their own profiles.
  * About 10 Cadets at a time; have them sign in a few at a time. Answers come from the library (no AI on a Pi Zero).
  * Phones may say "No internet" - choose "Stay connected" (Android) or just keep going (iPhone). Turning off mobile
    data during the demo helps.
  * Visitors can download Vanguard for their own computer from the sign-in screen ("Get Vanguard for your own computer").

Back on your home Wi-Fi (for updates):   sudo nmcli connection down vanguard-hotspot
Demo network again:                      sudo nmcli connection up vanguard-hotspot
Update Vanguard on the Pi: copy a newer Vanguard folder over and run pi_setup.sh again (profiles are kept).
"""


def friendly_password() -> str:
    return f"{secrets.choice(WORDS)}-{secrets.choice(WORDS)}-{secrets.randbelow(900) + 100}"


def wifi_qr_text(ssid: str, password: str) -> str:
    esc = lambda s: re.sub(r'([\\;,:"])', r"\\\1", s)  # noqa: E731  (the WIFI: QR format's escapes)
    return f"WIFI:T:WPA;S:{esc(ssid)};P:{esc(password)};;"


def qr_png(text: str) -> str:
    import qrcode
    img = qrcode.make(text, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def card(ssid: str, password: str) -> str:
    e = html.escape
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Vanguard demo card</title>
<style>
body {{ font-family: system-ui, Segoe UI, sans-serif; color: #111; margin: 24px; }}
.card {{ border: 2px solid #111; border-radius: 14px; padding: 22px; max-width: 720px; margin: 0 auto 24px; }}
h1 {{ margin: 0 0 4px; font-size: 30px; }} .sub {{ margin: 0 0 18px; color: #444; }}
.row {{ display: flex; gap: 24px; flex-wrap: wrap; }} .col {{ flex: 1; min-width: 260px; text-align: center; }}
.col img {{ width: 220px; height: 220px; }} .big {{ font-size: 22px; font-weight: 700; }}
.step {{ font-size: 14px; color: #333; }} .note {{ font-size: 13px; color: #444; margin-top: 16px; }}
@media print {{ body {{ margin: 0; }} }}
</style></head><body>
<div class="card">
  <h1>✦ Vanguard</h1><p class="sub">Leadership. Learning. Character. — Demo unit, no internet needed</p>
  <div class="row">
    <div class="col"><p class="step"><b>1.</b> Scan to join the Wi-Fi</p><img src="{qr_png(wifi_qr_text(ssid, password))}" alt="Wi-Fi QR code">
      <p>Wi-Fi: <span class="big">{e(ssid)}</span><br>Password: <span class="big">{e(password)}</span></p></div>
    <div class="col"><p class="step"><b>2.</b> Scan to open Vanguard</p><img src="{qr_png(ADDRESS)}" alt="Vanguard address QR code">
      <p>Or type: <span class="big">{e(ADDRESS.removeprefix('http://'))}</span><br><span class="step">(or {e(FALLBACK.removeprefix('http://'))})</span></p></div>
  </div>
  <p class="note">This small portable Vanguard runs on a Raspberry Pi — about <b>10 Cadets at a time</b>; please sign in a few at a time.
  If your phone says "No internet", choose <b>Stay connected</b>. To keep Vanguard, tap <b>Get Vanguard for your own computer</b> on the sign-in screen.</p>
  <p class="note">Vanguard is designed to support JROTC instruction. It is not an official JROTC, Army or school product.</p>
</div></body></html>"""


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    opt = lambda name: argv[argv.index(name) + 1] if name in argv else None  # noqa: E731
    if not args:
        print(__doc__)
        return 1
    try:
        import qrcode  # noqa: F401
    except ImportError:
        print("The QR codes need the qrcode package on this computer:  python -m pip install qrcode pillow")
        return 1
    drive = Path(args[0])
    # Re-running on the same drive keeps its Wi-Fi name and password (a printed card and a set-up Pi still match)
    # unless new ones are given.
    old = {}
    conf = drive / "demo" / "vanguard-demo.conf"
    if conf.exists():
        old = dict(re.findall(r"^(SSID|PASSWORD)='([^'\n]*)'$", conf.read_text(encoding="utf-8"), re.M))
    ssid = opt("--ssid") or old.get("SSID") or "Vanguard"
    password = opt("--wifi-password") or old.get("PASSWORD") or friendly_password()
    if len(password) < 8 or any(c in password for c in "'\n\r"):
        print("The Wi-Fi password needs at least 8 characters (and no quote marks).")
        return 1

    passthrough = [a for a in argv if a in ("--with-ai", "--all-gpu")]
    if "--model" in argv:
        passthrough += ["--model", opt("--model")]
    if make_usb.main([str(drive)] + passthrough) != 0:
        return 1

    demo = drive / "demo"
    demo.mkdir(exist_ok=True)
    (demo / "vanguard-demo.conf").write_bytes(f"SSID='{ssid}'\nPASSWORD='{password}'\n".encode("utf-8"))
    (demo / "Demo-Card.html").write_text(card(ssid, password), encoding="utf-8")
    (demo / "README-PI.txt").write_bytes(README_PI.format(ssid=ssid, password=password, address=ADDRESS,
                                                          fallback=FALLBACK).replace("\n", "\r\n").encode("utf-8"))
    print(f"\nDemo kit ready on {drive}.\n  Wi-Fi: {ssid}   password: {password}\n"
          f"  Print {demo / 'Demo-Card.html'} and follow {demo / 'README-PI.txt'} to set up the Pi.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
