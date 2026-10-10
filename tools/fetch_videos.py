"""
Save the official DVIDS videos listed in vanguard/data/videos.json onto this device, so they play offline.

    python tools/fetch_videos.py --key YOUR_DVIDS_API_KEY      (or set DVIDS_API_KEY)
    python tools/fetch_videos.py --list                        what would be saved, and what already is

DVIDS (dvidshub.net, the Defense Department's media service) gives each public-domain video in several sizes. An
API key is free: sign up at https://api.dvidshub.net. Vanguard takes a classroom-size copy (720p or smaller) to
keep the drive small. Needs internet once; files go into videos/ (not tracked in git; make_usb.py copies them).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vanguard import videos  # noqa: E402

UA = {"User-Agent": "Vanguard video installer (offline classroom app)"}


def _pick(files: list[dict]) -> dict | None:
    """The best mp4 no wider than 1280 px and about 1.5 Mbps -- clear on a projector, small on a USB drive."""
    mp4 = [f for f in files if str(f.get("src", "")).endswith(".mp4") and int(f.get("width") or 0) <= 1280]
    if not mp4:
        return None
    return min(mp4, key=lambda f: (abs(int(f.get("bitrate") or 0) - 1500), -int(f.get("width") or 0)))


def main(argv: list[str]) -> int:
    entries = [v for v in videos.catalog() if v["kind"] == "dvids"]
    if "--list" in argv:
        for v in entries:
            f = videos.file_for(v)
            print(("✓ " if f else "  ") + f"{v['id']}  {v['title']}" + (f"  ({f.stat().st_size / 2**20:.0f} MB)" if f else ""))
        return 0
    key = os.environ.get("DVIDS_API_KEY", "")
    if "--key" in argv:
        key = argv[argv.index("--key") + 1]
    if not key:
        print("A free DVIDS API key is needed: sign up at https://api.dvidshub.net, then run\n"
              "  python tools/fetch_videos.py --key YOUR_KEY")
        return 1
    videos.VIDEOS.mkdir(parents=True, exist_ok=True)
    total, failed = 0, []
    for v in entries:
        dest = videos.VIDEOS / f"{v['id']}.mp4"
        if dest.exists():
            continue
        try:
            q = urllib.parse.urlencode({"id": f"video:{v['dvids_id']}", "api_key": key})
            with urllib.request.urlopen(urllib.request.Request(f"https://api.dvidshub.net/asset?{q}", headers=UA), timeout=60) as r:
                asset = json.loads(r.read())["results"]
            f = _pick(asset.get("files") or [])
            if not f:
                raise ValueError("no mp4 file offered")
            tmp = dest.with_suffix(".part")
            with urllib.request.urlopen(urllib.request.Request(f["src"], headers=UA), timeout=300) as r, open(tmp, "wb") as out:
                while chunk := r.read(1 << 20):
                    out.write(chunk)
            tmp.replace(dest)
            total += dest.stat().st_size
            print(f"✓ {v['title']} ({dest.stat().st_size / 2**20:.0f} MB, {f.get('width')}x{f.get('height')})")
        except Exception as e:
            failed.append(v["id"])
            print(f"✗ {v['title']}: {e}")
        time.sleep(0.5)
    print(f"\nSaved {total / 2**20:.0f} MB into {videos.VIDEOS}." + (f" Not saved: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
