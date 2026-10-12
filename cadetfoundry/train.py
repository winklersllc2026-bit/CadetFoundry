"""
Train (Phase 6): fitness measured against yourself.

  * The instructor chooses the program's events (program/fitness_events.json). Until then, Cadet Foundry suggests a few
    common ones. No physical standard is built in -- the owner's spec: personal improvement, not pass/fail.
  * Results go in the Cadet's class records (fitness.jsonl), from the Cadet or from the instructor on test day.
  * Goals are the Cadet's own (goals.json, also a class record).
  * Stats: first, previous, latest, personal best, improvement since the first result, and the trend.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

from cadetfoundry import store

UNITS = {"reps": "reps", "time": "time (m:ss)", "lbs": "pounds", "inches": "inches", "laps": "laps"}
SUGGESTED = [
    {"id": "pushups", "name": "Push-ups", "unit": "reps", "better": "higher", "description": "As many as you can with good form."},
    {"id": "curlups", "name": "Curl-ups", "unit": "reps", "better": "higher", "description": "As many as you can with good form."},
    {"id": "plank", "name": "Plank", "unit": "time", "better": "higher", "description": "Hold with a straight body line."},
    {"id": "mile", "name": "One-mile run", "unit": "time", "better": "lower", "description": "Your time for one mile."},
]
FITNESS, GOALS = "fitness.jsonl", "goals.json"
_lock = threading.Lock()


# ── events (the instructor's choice) ────────────────────────────────────────
def _path():
    return store.DATA / "program" / "fitness_events.json"


def events() -> list[dict]:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [dict(e, suggested=True) for e in SUGGESTED]


def _save_events(rows: list[dict]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps([{k: v for k, v in e.items() if k != "suggested"} for e in rows]), encoding="utf-8")
    tmp.replace(path)


def add_event(name, unit, better, description="") -> dict:
    name = " ".join(str(name or "").split())[:40]
    if not name:
        raise ValueError("Name the event.")
    if unit not in UNITS:
        raise ValueError("Choose a unit: " + ", ".join(UNITS.values()) + ".")
    if better not in ("higher", "lower"):
        raise ValueError("Choose whether higher or lower is better.")
    with _lock:
        rows = events()
        if len(rows) >= 30:
            raise ValueError("Up to 30 events.")
        if any(e["name"].lower() == name.lower() for e in rows):
            raise ValueError("There's already an event with that name.")
        ev = {"id": uuid.uuid4().hex[:8], "name": name, "unit": unit, "better": better,
              "description": str(description or "").strip()[:200]}
        _save_events(rows + [ev])
    return ev


def remove_event(eid: str) -> None:
    """Hides the event from Train; Cadets' past results are kept in their records."""
    with _lock:
        _save_events([e for e in events() if e["id"] != eid])


def event(eid: str) -> dict:
    ev = next((e for e in events() if e["id"] == eid), None)
    if not ev:
        raise LookupError("No such event.")
    return ev


# ── values ──────────────────────────────────────────────────────────────────
def parse_value(unit: str, raw) -> float:
    s = str(raw if raw is not None else "").strip()
    if unit == "time":
        t = s.lower().replace(" ", "")
        # "1m30s", "1min30sec", "20s", "20sec" -> m:ss; a plain number is seconds
        w = re.fullmatch(r"(?:(\d{1,3})(?:m|min|mins|minutes?))?(?:(\d{1,4})(?:s|sec|secs|seconds?))?", t)
        if w and (w.group(1) or w.group(2)):
            mins, secs = int(w.group(1) or 0), int(w.group(2) or 0)
            if w.group(1) and secs >= 60:
                raise ValueError("Seconds go up to 59.")
            return float(mins * 60 + secs)
        m = re.fullmatch(r"(?:(\d{1,2}):)?(\d{0,3}):(\d{2})|(\d{1,5})", t)     # ":20" is 20 seconds
        if not m:
            raise ValueError("Write the time as m:ss — for example 1:45, 0:20 or :20 (or 20s).")
        if m.group(4):
            return float(m.group(4))
        h, mins, secs = int(m.group(1) or 0), int(m.group(2) or 0), int(m.group(3))
        if secs >= 60:
            raise ValueError("Seconds go up to 59.")
        return float(h * 3600 + mins * 60 + secs)
    try:
        v = float(s)
    except ValueError:
        raise ValueError("Enter a number.") from None
    if v < 0 or v > 100000:
        raise ValueError("That number doesn't look right.")
    return round(v, 2)


def show_value(unit: str, v: float | None) -> str:
    if v is None:
        return ""
    if unit == "time":
        v = int(round(v))
        h, rest = divmod(v, 3600)
        return f"{h}:{rest // 60:02d}:{rest % 60:02d}" if h else f"{rest // 60}:{rest % 60:02d}"
    return f"{v:g}"


# ── a Cadet's results and goals (inside that Cadet's session, or with their class key) ──
def _clean_date(date: str) -> str:
    date = str(date or "").strip() or time.strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("Date as YYYY-MM-DD.")
    # a day of slack: a phone's date can run ahead of the laptop's near midnight or across time zones
    if date > time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400)):
        raise ValueError("That date is in the future.")
    return date


def add_result(eid: str, raw, date: str = "", note: str = "", by: str = "self") -> dict:
    ev = event(eid)
    row = {"id": uuid.uuid4().hex[:10], "event": eid, "value": parse_value(ev["unit"], raw), "date": _clean_date(date),
           "note": str(note or "").strip()[:200], "by": by}
    with _lock:
        store.write_lines(FITNESS, store.read_lines(FITNESS)[-1999:] + [row])
    return row


def delete_result(rid: str) -> None:
    """A Cadet can remove their own entries; results the instructor recorded stay."""
    with _lock:
        rows = store.read_lines(FITNESS)
        if not any(r["id"] == rid and r.get("by") == "self" for r in rows):
            raise LookupError("You can only remove results you entered yourself.")
        store.write_lines(FITNESS, [r for r in rows if r["id"] != rid])


def set_goal(eid: str, raw, by_date: str = "") -> dict:
    ev = event(eid)
    with _lock:
        goals = store.read_json(GOALS, {})
        if str(raw or "").strip() == "":
            goals.pop(eid, None)
        else:
            if by_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", by_date):
                raise ValueError("Goal date as YYYY-MM-DD.")
            goals[eid] = {"target": parse_value(ev["unit"], raw), "by": by_date, "set": time.strftime("%Y-%m-%d")}
        store.write_json(GOALS, goals)
    return goals


def stats(ev: dict, rows: list[dict], goal: dict | None = None) -> dict:
    """Personal-improvement numbers for one event. Positive improvement always means better, whatever the
    direction. No pass/fail anywhere."""
    # by date; results on the same day stay in the order they were entered (the file's order)
    rows = sorted((r for r in rows if r["event"] == ev["id"]), key=lambda r: r["date"])
    unit, higher = ev["unit"], ev["better"] == "higher"
    out = {"event": ev["id"], "name": ev["name"], "unit": unit, "better": ev["better"], "count": len(rows),
           "history": [{"id": r["id"], "date": r["date"], "value": r["value"], "shown": show_value(unit, r["value"]),
                        "by": r.get("by", "self"), "note": r.get("note", "")} for r in rows]}
    if rows:
        first, latest = rows[0]["value"], rows[-1]["value"]
        best = max(r["value"] for r in rows) if higher else min(r["value"] for r in rows)
        gain = (latest - first) if higher else (first - latest)
        out.update({"first": show_value(unit, first), "first_date": rows[0]["date"], "latest": show_value(unit, latest),
                    "latest_date": rows[-1]["date"], "best": show_value(unit, best), "latest_is_best": latest == best,
                    "improvement": gain, "improvement_shown": ("+" if gain > 0 else "−" if gain < 0 else "±")
                    + show_value(unit, abs(gain)), "improvement_pct": round(gain / first * 100) if first else None})
        if len(rows) > 1:
            prev = rows[-2]["value"]
            out["previous"] = show_value(unit, prev)
            out["since_previous"] = (latest - prev) if higher else (prev - latest)
    if goal:
        out["goal"] = show_value(unit, goal["target"])
        out["goal_by"] = goal.get("by", "")
        if rows:
            out["goal_reached"] = (latest >= goal["target"]) if higher else (latest <= goal["target"])
    return out


def my_train() -> dict:
    rows, goals = store.read_lines(FITNESS), store.read_json(GOALS, {})
    return {"events": [stats(e, rows, goals.get(e["id"])) | {"description": e.get("description", ""),
                                                            "suggested": bool(e.get("suggested"))} for e in events()],
            "units": UNITS}
