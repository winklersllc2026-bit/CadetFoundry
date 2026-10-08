"""
Army jobs (MOS) explorer -- official summaries from goarmy.com, saved into
library/_jobs.json by tools/fetch_library.py. Works offline once downloaded.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_cache: dict = {"mtime": None, "data": {"jobs": []}}


def _file(library_dir: Path) -> Path:
    return library_dir / "_jobs.json"


def load(library_dir: Path) -> dict:
    f = _file(library_dir)
    try:
        mt = f.stat().st_mtime
    except OSError:
        return {"jobs": []}
    if _cache["mtime"] != mt:
        try:
            _cache["data"] = json.loads(f.read_text(encoding="utf-8"))
            _cache["mtime"] = mt
        except (OSError, ValueError):
            return {"jobs": []}
    return _cache["data"]


# Everyday words -> the words Army job titles use.
SYNONYMS = {
    "cook": ("culinary", "food"), "chef": ("culinary",), "food": ("culinary",),
    "mechanic": ("repairer", "maintainer", "mechanic"), "doctor": ("physician", "medical"),
    "nurse": ("nurse", "nursing"), "lawyer": ("paralegal", "judge", "legal"), "police": ("military police",),
    "pilot": ("aviator", "aviation"), "computers": ("computer", "information technology", "cyber"),
    "it": ("information technology",), "hacker": ("cyber",), "mp": ("military police",),
    "truck": ("motor transport", "vehicle"), "driver": ("motor transport", "operator"),
    "spy": ("intelligence",), "medical": ("medic", "health"), "dog": ("working dog",),
    "music": ("band", "musician"), "photo": ("photographer", "visual"), "money": ("finance",),
}


def search(library_dir: Path, q: str = "", area: str = "", limit: int = 60) -> dict:
    data = load(library_dir)
    jobs = data.get("jobs", [])
    areas = sorted({j["area"] for j in jobs})
    q = (q or "").strip().lower()
    hits = []
    for j in jobs:
        if area and j["area"] != area:
            continue
        if q:
            code = j["code"].lower()
            hay = f"{j['title']} {j['summary']} {j['area']} {j['group']}".lower()
            if code == q or code.startswith(q) and len(q) >= 2:
                score = 100
            else:
                words = [w for w in re.findall(r"[a-z0-9]+", q) if len(w) > 1]
                words += [s for w in words for s in SYNONYMS.get(w, ())]
                title = j["title"].lower()
                title_words = set(re.findall(r"[a-z0-9]+", title))
                # a whole-word title match ("medic" in "Combat Medic") beats a partial one ("medic" in "Medical")
                score = sum((20 if w in title_words else 6 if w in title else 0) +
                            (3 if re.search(rf"\b{re.escape(w)}\b", hay) else 1 if w in hay else 0) for w in words)
                if not score:
                    continue
        else:
            score = 0
        hits.append((score, j))
    hits.sort(key=lambda x: (-x[0], x[1]["code"] or "ZZZ"))
    return {"total": len(jobs), "areas": areas, "fetched": data.get("fetched", ""),
            "jobs": [j for _s, j in hits[:limit]]}
