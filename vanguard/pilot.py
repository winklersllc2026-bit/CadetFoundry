"""
Pilot tools (Phase 10, owner's spec §32-33): make a JROTC pilot measurable.

  * Pilot setup: school, program, instructor, dates, planned Cadets, metrics (program/pilot.json).
  * Snapshots of the class numbers (reports.dashboard) at the start and about weekly, so the report shows CHANGE
    over the pilot (program/pilot_snapshots.json).
  * Cadet feedback: a short survey the instructor opens. Anonymous -- answers are stored without any name or id;
    whether a Cadet has answered is kept in that Cadet's own private file (pilot_feedback.json), never with the answers.
  * Instructor feedback: satisfaction, minutes saved per week, and "would you use this next semester?" (spec §50).
  * The end-of-pilot report: every number comes from real records; what Vanguard can't measure is said plainly.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

from vanguard import lessons, store

METRICS = {"engagement": "Engagement (Cadets active each week)", "lessons": "Lesson completion",
           "academics": "Academic performance", "leadership": "Leadership scenario participation",
           "fitness": "Fitness improvement", "service": "Service participation",
           "workload": "Instructor workload", "feedback": "Cadet and instructor feedback"}
SURVEY = [
    ("learn", "Vanguard helped me learn the material."),
    ("lead", "The leadership scenarios helped me think about how to lead."),
    ("progress", "Seeing my progress motivated me."),
    ("easy", "Vanguard was easy to use."),
    ("again", "I'd like to keep using Vanguard."),
]
SCALE = {1: "Strongly disagree", 2: "Disagree", 3: "Not sure", 4: "Agree", 5: "Strongly agree"}
_lock = threading.Lock()


def _path(name: str):
    return store.DATA / "program" / name


def _read(name: str, default):
    try:
        return json.loads(_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(name: str, data) -> None:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def _date(v, label: str) -> str:
    v = str(v or "").strip()
    if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError(f"{label} as YYYY-MM-DD.")
    return v


# ── setup ───────────────────────────────────────────────────────────────────
def config() -> dict:
    return _read("pilot.json", {})


def save_config(data: dict) -> dict:
    start, end = _date(data.get("start"), "Start date"), _date(data.get("end"), "End date")
    if start and end and end < start:
        raise ValueError("The end date is before the start date.")
    planned = str(data.get("cadets_planned") or "").strip()
    if planned and (not planned.isdigit() or not 1 <= int(planned) <= 500):
        raise ValueError("Planned Cadets: a number from 1 to 500.")
    metrics = [m for m in METRICS if m in (data.get("metrics") or [])] if isinstance(data.get("metrics"), list) else list(METRICS)
    cfg = {"school": " ".join(str(data.get("school") or "").split())[:100],
           "program": " ".join(str(data.get("program") or "Army JROTC").split())[:60],
           "instructor": " ".join(str(data.get("instructor") or "").split())[:80],
           "start": start, "end": end, "cadets_planned": int(planned) if planned else None, "metrics": metrics,
           "notes": str(data.get("notes") or "").strip()[:2000], "survey_open": bool(config().get("survey_open"))}
    with _lock:
        _write("pilot.json", cfg)
    return cfg


def set_survey(open_: bool) -> dict:
    with _lock:
        cfg = config()
        if not cfg:
            raise ValueError("Set up the pilot first.")
        cfg["survey_open"] = bool(open_)
        _write("pilot.json", cfg)
    return cfg


# ── snapshots ───────────────────────────────────────────────────────────────
SNAP_KEYS = ("cadets", "active", "lesson_completion_pct", "avg_lesson_score_pct", "avg_fitness_improvement_pct",
             "service_hours", "scenarios", "cards_mastered")


def snapshots() -> list[dict]:
    return _read("pilot_snapshots.json", [])


def take_snapshot(dash: dict, force: bool = False) -> dict | None:
    """Record today's class numbers. Without force, only if the last one is a week old (or there is none)."""
    snaps = snapshots()
    today = time.strftime("%Y-%m-%d")
    if snaps and not force:
        last = snaps[-1]["date"]
        if time.mktime(time.strptime(today, "%Y-%m-%d")) - time.mktime(time.strptime(last, "%Y-%m-%d")) < 7 * 86400:
            return None
    shared = [r for r in dash["rows"] if r.get("shared")]
    snap = {"date": today, **{k: dash.get(k) for k in SNAP_KEYS if k in dash},
            "cards_mastered": sum(r.get("cards_mastered", 0) for r in shared)}
    with _lock:
        snaps = [s for s in snapshots() if s["date"] != today] + [snap]
        _write("pilot_snapshots.json", snaps[-60:])
    return snap


# ── feedback ────────────────────────────────────────────────────────────────
def survey_status() -> dict:
    """For the signed-in Cadet: is the survey open, and have they answered? (their own private flag)"""
    cfg = config()
    done = bool(store.read_json("pilot_feedback.json", {}).get("done"))
    return {"open": bool(cfg.get("survey_open")), "done": done,
            "questions": [{"id": k, "q": q} for k, q in SURVEY], "scale": SCALE}


def submit_survey(answers: dict, comment: str) -> None:
    st = survey_status()
    if not st["open"]:
        raise ValueError("The survey isn't open right now.")
    if st["done"]:
        raise ValueError("You've already answered — thank you!")
    clean = {}
    for k, _q in SURVEY:
        try:
            v = int(answers.get(k))
        except (TypeError, ValueError):
            raise ValueError("Answer every question (1 to 5).") from None
        if v not in SCALE:
            raise ValueError("Answer every question (1 to 5).")
        clean[k] = v
    row = {"date": time.strftime("%Y-%m-%d"), **clean, "comment": str(comment or "").strip()[:1000]}   # no name, no id
    with _lock:
        rows = _read("feedback_cadets.json", [])
        rows.append(row)
        _write("feedback_cadets.json", rows)
        store.write_json("pilot_feedback.json", {"done": time.strftime("%Y-%m-%d")})


def add_instructor_feedback(satisfaction, minutes_saved, use_again, comment="") -> dict:
    try:
        sat = int(satisfaction)
    except (TypeError, ValueError):
        raise ValueError("Satisfaction from 1 to 5.") from None
    if not 1 <= sat <= 5:
        raise ValueError("Satisfaction from 1 to 5.")
    mins = str(minutes_saved or "").strip()
    if mins and (not mins.lstrip("-").isdigit() or not -600 <= int(mins) <= 600):
        raise ValueError("Minutes saved per week: a number (negative if it cost you time).")
    if use_again not in ("yes", "maybe", "no"):
        raise ValueError("Would you use it next semester: yes, maybe or no.")
    row = {"id": uuid.uuid4().hex[:8], "date": time.strftime("%Y-%m-%d"), "satisfaction": sat,
           "minutes_saved": int(mins) if mins else None, "use_again": use_again, "comment": str(comment or "").strip()[:2000]}
    with _lock:
        rows = _read("feedback_instructor.json", [])
        rows.append(row)
        _write("feedback_instructor.json", rows)
    return row


def feedback_summary() -> dict:
    cad, ins = _read("feedback_cadets.json", []), _read("feedback_instructor.json", [])
    avg = {k: round(sum(r[k] for r in cad) / len(cad), 1) if cad else None for k, _q in SURVEY}
    latest = ins[-1] if ins else None
    mins = [r["minutes_saved"] for r in ins if r.get("minutes_saved") is not None]
    return {"cadet_responses": len(cad), "averages": avg, "questions": dict(SURVEY),
            "cadet_comments": [r["comment"] for r in cad if r.get("comment")],
            "instructor": ins, "latest_instructor": latest,
            "avg_minutes_saved": round(sum(mins) / len(mins)) if mins else None}


# ── the report ──────────────────────────────────────────────────────────────
def report(dash: dict) -> dict:
    cfg, snaps, fb = config(), snapshots(), feedback_summary()
    first = snaps[0] if snaps else None
    weeks = None
    if cfg.get("start"):
        end = cfg.get("end") or time.strftime("%Y-%m-%d")
        end = min(end, time.strftime("%Y-%m-%d"))
        days = (time.mktime(time.strptime(end, "%Y-%m-%d")) - time.mktime(time.strptime(cfg["start"], "%Y-%m-%d"))) / 86400
        weeks = max(0, round(days / 7, 1))
    shared = [r for r in dash["rows"] if r.get("shared")]
    now = {k: dash.get(k) for k in SNAP_KEYS if k in dash}
    now["cards_mastered"] = sum(r.get("cards_mastered", 0) for r in shared)
    change = {}
    if first:
        for k in ("avg_lesson_score_pct", "cards_mastered", "service_hours", "scenarios"):
            if first.get(k) is not None and now.get(k) is not None:
                change[k] = round(now[k] - first[k], 1)
    in_window = [a for a in lessons.all_assignments()
                 if not cfg.get("start") or a.get("created", "") >= cfg["start"]]
    return {"config": cfg, "metric_names": METRICS, "weeks": weeks, "now": now, "baseline": first, "change": change,
            "lessons_assigned": len(in_window), "snapshots": snaps, "feedback": fb,
            "engagement": [{"date": s["date"], "active": s.get("active"), "cadets": s.get("cadets")} for s in snaps],
            "cannot_measure": [] if first else ["Change over the pilot needs a starting snapshot — take one at the start."]}
