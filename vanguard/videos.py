"""
Official military videos (0.2). The list is vanguard/data/videos.json:

  * DVIDS videos -- U.S. government works marked public domain on dvidshub.net. tools/fetch_videos.py saves them
    into videos/ once (it needs a free DVIDS API key), and then they play on the device with no internet and no
    tracking. Until then a Cadet sees the official DVIDS page link instead.
  * YouTube videos -- links only, each from the service's own channel. They open YouTube and need internet;
    Vanguard never embeds YouTube (an embedded player would connect every device to Google).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = Path(__file__).parent / "data" / "videos.json"
VIDEOS = Path(os.environ.get("VANGUARD_VIDEOS") or (ROOT / "videos")).resolve()


def catalog() -> list[dict]:
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))["videos"]
    except (OSError, ValueError, KeyError):
        return []


def file_for(v: dict) -> Path | None:
    """The saved file of a DVIDS video, if it's on this device."""
    if v.get("kind") != "dvids":
        return None
    f = VIDEOS / f"{v['id']}.mp4"
    return f if f.is_file() else None


def listing() -> dict:
    out = []
    for v in catalog():
        f = file_for(v)
        out.append({**v, "local": bool(f), "src": f"/videos/{v['id']}.mp4" if f else "",
                    "mb": round(f.stat().st_size / 2**20) if f else None})
    return {"videos": out, "saved": sum(1 for v in out if v["local"]),
            "dvids": sum(1 for v in out if v["kind"] == "dvids")}


def path_for_request(name: str) -> Path | None:
    """/videos/<id>.mp4 -> the file, only for ids in the catalog (never a path from the request)."""
    m = re.fullmatch(r"(dvids-\d{1,9})\.mp4", name or "")
    if not m:
        return None
    v = next((x for x in catalog() if x["id"] == m.group(1)), None)
    return file_for(v) if v else None
