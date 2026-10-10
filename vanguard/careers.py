"""
Military jobs explorer, every service -- official summaries saved by tools/fetch_library.py from each service's own
recruiting site: goarmy.com (library/_jobs.json), airforce.com, navy.com, spaceforce.com and marines.com
(library/_jobs_<service>.json). Works offline once downloaded. Nothing here is written by hand.

Air Force job pages also list their minimum ASVAB line scores; a Cadet who types in their own official scores sees
which of those jobs they meet. Other services' pages don't publish requirements, so their jobs never claim a match.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SERVICE_FILES = {"army": "_jobs.json", "navy": "_jobs_navy.json", "air_force": "_jobs_air_force.json",
                 "space_force": "_jobs_space_force.json", "marine_corps": "_jobs_marine_corps.json"}
SOURCES = {"army": "goarmy.com", "navy": "navy.com", "air_force": "airforce.com", "space_force": "spaceforce.com",
           "marine_corps": "marines.com"}
LINE_SCORES = ("Mechanical", "Administrative", "General", "Electronics")      # the Air Force's MAGE areas
_cache: dict = {}


def _load_one(library_dir: Path, service: str) -> dict:
    f = library_dir / SERVICE_FILES[service]
    try:
        mt = f.stat().st_mtime
    except OSError:
        return {"jobs": []}
    hit = _cache.get(f)
    if not hit or hit[0] != mt:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"jobs": []}
        for j in data.get("jobs", []):              # the Army file predates these fields
            j.setdefault("service", service)
            j.setdefault("kind", "")
            j.setdefault("asvab", [])
            j.setdefault("asvab_text", "")
            j.setdefault("asvab_any", False)
            j.setdefault("url", "")
            j.setdefault("group", "")
            if j.get("code") and j["title"].endswith(f"({j['code']})"):    # "Air Traffic Control (1C131)"
                j["title"] = j["title"][: -len(j["code"]) - 2].strip()
        hit = _cache[f] = (mt, data)
    return hit[1]


def load(library_dir: Path) -> dict:
    """Army jobs only (kept for older callers)."""
    return _load_one(library_dir, "army")


def all_jobs(library_dir: Path) -> tuple[list[dict], dict]:
    jobs, fetched = [], {}
    for svc in SERVICE_FILES:
        data = _load_one(library_dir, svc)
        if data.get("jobs"):
            jobs += data["jobs"]
            fetched[svc] = data.get("fetched", "")
    return jobs, fetched


def meets(job: dict, scores: dict) -> bool | None:
    """True/False when the job lists ASVAB line-score minimums and the Cadet gave the scores it needs; else None."""
    reqs = job.get("asvab") or []
    if not reqs or not scores:
        return None
    given = [r for r in reqs if scores.get(r["area"]) is not None]
    if not given:
        return None                                   # the score this job needs wasn't entered
    passed = [scores[r["area"]] >= r["min"] for r in given]
    if job.get("asvab_any"):                          # "A or B": one is enough
        return True if any(passed) else (False if len(given) == len(reqs) else None)
    return False if not all(passed) else (True if len(given) == len(reqs) else None)


# Everyday words -> the words job titles use.
SYNONYMS = {
    "cook": ("culinary", "food"), "chef": ("culinary",), "food": ("culinary",),
    "mechanic": ("repairer", "maintainer", "mechanic", "maintenance"), "doctor": ("physician", "medical"),
    "nurse": ("nurse", "nursing"), "lawyer": ("paralegal", "judge", "legal"),
    "police": ("military police", "security forces"), "pilot": ("aviator", "aviation", "pilot"),
    "computers": ("computer", "information technology", "cyber"), "it": ("information technology",),
    "hacker": ("cyber",), "mp": ("military police",), "truck": ("motor transport", "vehicle"),
    "driver": ("motor transport", "operator"), "spy": ("intelligence",), "medical": ("medic", "health", "corpsman"),
    "dog": ("working dog",), "music": ("band", "musician"), "photo": ("photographer", "visual"),
    "money": ("finance",), "space": ("space", "satellite"), "ship": ("ship", "boat", "naval"),
    "planes": ("aircraft", "aviation"),
}


def search(library_dir: Path, q: str = "", area: str = "", limit: int = 60, service: str = "",
           scores: dict | None = None, only_meets: bool = False) -> dict:
    jobs, fetched = all_jobs(library_dir)
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j["service"]] = counts.get(j["service"], 0) + 1
    if service:
        jobs = [j for j in jobs if j["service"] == service]
    areas = sorted({j["area"] for j in jobs})
    q = (q or "").strip().lower()
    hits = []
    for j in jobs:
        if area and j["area"] != area:
            continue
        ok = meets(j, scores or {})
        if only_meets and ok is not True:
            continue
        if q:
            code = (j.get("code") or "").lower()
            hay = f"{j['title']} {j['summary']} {j['area']} {j.get('group', '')}".lower()
            if code and (code == q or code.startswith(q) and len(q) >= 2):
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
        hits.append((score, j, ok))
    hits.sort(key=lambda x: (-x[0], x[1]["service"] != "army", x[1].get("code") or "ZZZ", x[1]["title"]))
    return {"total": len(jobs), "areas": areas, "services": counts, "fetched": fetched.get("army", ""),
            "fetched_by": fetched, "sources": SOURCES, "line_scores": LINE_SCORES,
            "jobs": [{**j, "meets": ok} for _s, j, ok in hits[:limit]]}
