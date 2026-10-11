"""
Pilot tools (Phase 10, owner's spec §32-33): make a JROTC pilot measurable.

  * Pilot setup: school, program, instructor, dates, planned Cadets, metrics (program/pilot.json).
  * Snapshots of the class numbers (reports.dashboard) at the start and about weekly, so the report shows CHANGE
    over the pilot (program/pilot_snapshots.json).
  * Cadet feedback: a short survey the instructor opens. Anonymous -- answers are stored without any name or id;
    whether a Cadet has answered is kept in that Cadet's own private file (pilot_feedback.json), never with the answers.

At rest (security review, 2026-10-11): the pilot setup (school, instructor, notes), the snapshots and the instructor's
feedback are sealed with the program data key (vault.program_data_key) -- only an instructor session with the Class
PIN opens them. Each Cadet survey answer is sealed TO the program public key (vault.seal_to) by the Cadet's own
session, which can write an answer but never read one back; answers are stored in random order. Only "is the survey
open?" is plain (program/pilot_survey.json): a Cadet's screen needs it. Files from older versions (plain JSON) are
read as they are and sealed the next time an instructor opens the pilot -- nothing is lost.
  * Instructor feedback: satisfaction, minutes saved per week, and "would you use this next semester?" (spec §50).
  * The end-of-pilot report: every number comes from real records; what Vanguard can't measure is said plainly.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

import secrets

from vanguard import lessons, security, store, vault

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


def _atomic(name: str, raw: bytes) -> None:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)                            # a crash leaves the old file or the new one, never half of one


def _read_plain(name: str, default):
    try:
        return json.loads(_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _read(priv: bytes | None, name: str, default):
    """An instructor-only pilot file. Sealed with the program data key; a plain file from an older version is read
    as it is and sealed now (the migration: idempotent, and the plain copy is replaced, not left beside it).
    Without the program key nothing is returned -- not even an older plain file."""
    if not priv:
        return default
    try:
        raw = _path(name).read_bytes()
    except OSError:
        return default
    if vault.is_sealed(raw):
        try:
            return json.loads(vault.open_sealed(vault.program_data_key(priv), raw, name).decode("utf-8"))
        except (vault.VaultError, ValueError):   # sealed with an older program key (the Class PIN was reset)
            return default
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        return default
    if priv and vault.AVAILABLE:
        _write(priv, name, data)                  # migrate the older plain file
    return data


def _write(priv: bytes | None, name: str, data) -> None:
    raw = json.dumps(data).encode("utf-8")
    if priv and vault.AVAILABLE:
        raw = vault.seal(vault.program_data_key(priv), raw, name)
    _atomic(name, raw)


# ── the Cadet survey: answers sealed to the instructor ──────────────────────
def _survey_rows_raw() -> dict:
    """{"plain": [...], "sealed": [box, ...]} -- an older version wrote a plain list of rows."""
    data = _read_plain("feedback_cadets.json", None)
    if isinstance(data, list):
        return {"plain": data, "sealed": []}
    if isinstance(data, dict) and isinstance(data.get("sealed"), list):
        return {"plain": [], "sealed": data["sealed"]}
    return {"plain": [], "sealed": []}


def _seal_rows(rows: list[dict]) -> list:
    pub = security.program_public()
    if not pub or not vault.AVAILABLE:
        raise ValueError("The survey isn't set up on this device yet.")
    return [vault.seal_to(pub, json.dumps(r).encode("utf-8"), "pilot survey") for r in rows]


def _add_survey_row(row: dict) -> None:
    cur = _survey_rows_raw()
    boxes = cur["sealed"] + _seal_rows(cur["plain"])          # older plain answers get sealed on the way
    boxes.insert(secrets.randbelow(len(boxes) + 1), _seal_rows([row])[0])   # random order: no "who answered when"
    _atomic("feedback_cadets.json", json.dumps({"sealed": boxes}).encode("utf-8"))


def _survey_rows(priv: bytes) -> list[dict]:
    cur = _survey_rows_raw()
    rows = list(cur["plain"])
    for box in cur["sealed"]:
        try:
            rows.append(json.loads(vault.open_from(priv, box, "pilot survey").decode("utf-8")))
        except (vault.VaultError, ValueError):
            pass                                  # sealed to an older program key: can't be read any more
    if cur["plain"] and vault.AVAILABLE and security.program_public():
        try:                                      # migrate an older plain file
            _atomic("feedback_cadets.json", json.dumps({"sealed": cur["sealed"] + _seal_rows(cur["plain"])}).encode("utf-8"))
        except ValueError:
            pass
    return rows


def _survey_open() -> bool:
    flag = _read_plain("pilot_survey.json", None)
    if isinstance(flag, dict):
        return bool(flag.get("open"))
    old = _read_plain("pilot.json", {})            # an older version kept the flag in the (then plain) setup file
    return bool(isinstance(old, dict) and old.get("survey_open"))


def _date(v, label: str) -> str:
    v = str(v or "").strip()
    if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError(f"{label} as YYYY-MM-DD.")
    return v


# ── setup ───────────────────────────────────────────────────────────────────
def config(priv: bytes | None) -> dict:
    if priv and _read_plain("pilot_survey.json", None) is None:
        # migrating an older plain setup file: keep its "survey open" flag before the file is sealed
        _atomic("pilot_survey.json", json.dumps({"open": _survey_open()}).encode("utf-8"))
    cfg = _read(priv, "pilot.json", {})
    if not cfg:
        return {}
    cfg.pop("survey_open", None)                 # (older versions kept the flag here)
    return {**cfg, "survey_open": _survey_open()}


def save_config(priv: bytes, data: dict) -> dict:
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
           "notes": str(data.get("notes") or "").strip()[:2000]}
    with _lock:
        if _read_plain("pilot_survey.json", None) is None:     # keep the flag from an older (plain) setup file
            _atomic("pilot_survey.json", json.dumps({"open": _survey_open()}).encode("utf-8"))
        _write(priv, "pilot.json", cfg)
    return {**cfg, "survey_open": _survey_open()}


def set_survey(priv: bytes, open_: bool) -> dict:
    with _lock:
        cfg = config(priv)
        if not cfg:
            raise ValueError("Set up the pilot first.")
        _atomic("pilot_survey.json", json.dumps({"open": bool(open_)}).encode("utf-8"))
    return {**cfg, "survey_open": bool(open_)}


# ── snapshots ───────────────────────────────────────────────────────────────
SNAP_KEYS = ("cadets", "active", "lesson_completion_pct", "avg_lesson_score_pct", "avg_fitness_improvement_pct",
             "service_hours", "scenarios", "cards_mastered")


def snapshots(priv: bytes) -> list[dict]:
    return _read(priv, "pilot_snapshots.json", [])


def take_snapshot(priv: bytes, dash: dict, force: bool = False) -> dict | None:
    """Record today's class numbers. Without force, only if the last one is a week old (or there is none)."""
    snaps = snapshots(priv)
    today = time.strftime("%Y-%m-%d")
    if snaps and not force:
        last = snaps[-1]["date"]
        if time.mktime(time.strptime(today, "%Y-%m-%d")) - time.mktime(time.strptime(last, "%Y-%m-%d")) < 7 * 86400:
            return None
    shared = [r for r in dash["rows"] if r.get("shared")]
    snap = {"date": today, **{k: dash.get(k) for k in SNAP_KEYS if k in dash},
            "cards_mastered": sum(r.get("cards_mastered", 0) for r in shared)}
    with _lock:
        snaps = [s for s in snapshots(priv) if s["date"] != today] + [snap]
        _write(priv, "pilot_snapshots.json", snaps[-60:])
    return snap


# ── feedback ────────────────────────────────────────────────────────────────
def survey_status() -> dict:
    """For the signed-in Cadet: is the survey open, and have they answered? (their own private flag)"""
    done = bool(store.read_json("pilot_feedback.json", {}).get("done"))
    return {"open": _survey_open(), "done": done,
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
        _add_survey_row(row)                         # sealed to the instructor: this session can't read it back
        store.write_json("pilot_feedback.json", {"done": time.strftime("%Y-%m-%d")})


def add_instructor_feedback(priv: bytes, satisfaction, minutes_saved, use_again, comment="") -> dict:
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
        rows = _read(priv, "feedback_instructor.json", [])
        rows.append(row)
        _write(priv, "feedback_instructor.json", rows)
    return row


def feedback_summary(priv: bytes) -> dict:
    cad, ins = _survey_rows(priv), _read(priv, "feedback_instructor.json", [])
    avg = {k: round(sum(r[k] for r in cad) / len(cad), 1) if cad else None for k, _q in SURVEY}
    latest = ins[-1] if ins else None
    mins = [r["minutes_saved"] for r in ins if r.get("minutes_saved") is not None]
    return {"cadet_responses": len(cad), "averages": avg, "questions": dict(SURVEY),
            "cadet_comments": [r["comment"] for r in cad if r.get("comment")],
            "instructor": ins, "latest_instructor": latest,
            "avg_minutes_saved": round(sum(mins) / len(mins)) if mins else None}


# ── the report ──────────────────────────────────────────────────────────────
def report(priv: bytes, dash: dict) -> dict:
    cfg, snaps, fb = config(priv), snapshots(priv), feedback_summary(priv)
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
            "metrics": metrics(priv, dash), "class_feedback": class_feedback(priv)[-20:],
            "daily_questions": DAILY_QUESTIONS,
            "lessons_assigned": len(in_window), "snapshots": snaps, "feedback": fb,
            "engagement": [{"date": s["date"], "active": s.get("active"), "cadets": s.get("cadets")} for s in snaps],
            "cannot_measure": [] if first else ["Change over the pilot needs a starting snapshot — take one at the start."]}


# ── Pilot mode: what's stored, and ending the pilot ─────────────────────────
PILOT_FILES = ("pilot.json", "pilot_snapshots.json", "feedback_cadets.json", "feedback_instructor.json",
               "pilot_survey.json", "feedback_daily.json")


def stored(priv: bytes) -> dict:
    """What this device holds right now, in counts -- for the instructor's "What's stored" panel. No names."""
    from vanguard import engine, instructor, profiles
    every = profiles.all_profiles()
    count = lambda kind: sum(1 for p in every if p["kind"] == kind)   # noqa: E731
    size = 0
    for f in store.DATA.rglob("*"):
        try:
            size += f.stat().st_size if f.is_file() else 0
        except OSError:
            pass
    return {"folder": str(store.DATA), "size_mb": round(size / 2 ** 20, 1),
            "cadets": count("cadet"), "guardians": count("guardian"), "instructors": count("instructor"),
            "units": len(instructor.roster(priv)["units"]), "lessons": len(lessons.all_lessons()),
            "assignments": len(lessons.all_assignments()), "snapshots": len(snapshots(priv)),
            "survey_answers": len(_survey_rows_raw()["sealed"]) + len(_survey_rows_raw()["plain"]),
            "instructor_feedback": len(_read(priv, "feedback_instructor.json", [])) + len(_read(priv, "feedback_daily.json", [])),
            "online_ai": engine.online_ready(), "pilot_mode": bool(store.config().get("pilot_mode"))}


def end(priv: bytes) -> dict:
    """End the pilot: permanently remove every Cadet and guardian profile (private files and class records), the
    assignments, the roster's Cadets, pending joins, live answers, the pilot's setup, snapshots and feedback, and
    program safety copies that could still hold any of it. Kept: instructor profiles, the Class PIN, the instructor's
    own lessons, scenarios, projects and units (with NEW join codes -- the old ones were shared with the class)."""
    import shutil
    from vanguard import instructor, live_quiz, profiles, scenarios
    gone = [p for p in profiles.all_profiles() if p["kind"] in ("cadet", "guardian")]
    for p in gone:
        security.end_sessions(p["id"])
        profiles.delete(p["id"])
    assignments = lessons.all_assignments()
    for a in assignments:
        lessons.delete_assignment(a["id"])
    instructor.forget_cadets(priv)
    scenarios.live_stop()
    live_quiz.stop()
    with _lock:
        for name in PILOT_FILES:
            _path(name).unlink(missing_ok=True)
    copies = sorted(store.DATA.glob("program.before-restore-*"))
    for d in copies:                              # a restore's safety copy can hold the same records
        shutil.rmtree(d, ignore_errors=True)
    return {"cadets": sum(1 for p in gone if p["kind"] == "cadet"),
            "guardians": sum(1 for p in gone if p["kind"] == "guardian"),
            "assignments": len(assignments), "safety_copies": len(copies),
            "remaining_profiles": [{"name": p["name"], "kind": p["kind"]} for p in profiles.all_profiles()]}


# ── after class: the instructor's quick feedback (batch 3, owner 2026-10-11) ─
# Product feedback only: how useful Vanguard was today, and four optional questions. No Cadet is named or counted
# here, and nothing leaves this device -- it's sealed with the program data key like the rest of the pilot.
DAILY = "feedback_daily.json"
DAILY_QUESTIONS = {"goal": "What were you trying to accomplish today?", "worked": "What worked?",
                   "confusing": "What was confusing?", "change": "What would you change?"}


def add_class_feedback(priv: bytes, useful, again="", **answers) -> dict:
    try:
        useful = int(useful)
    except (TypeError, ValueError):
        raise ValueError("How useful was Vanguard today: 1 to 5.") from None
    if not 1 <= useful <= 5:
        raise ValueError("How useful was Vanguard today: 1 to 5.")
    if again not in ("", "yes", "maybe", "no"):
        raise ValueError("Would you use Vanguard again: yes, maybe or no.")
    row = {"id": uuid.uuid4().hex[:8], "date": time.strftime("%Y-%m-%d"), "at": round(time.time(), 3),
           "useful": useful, "again": again,
           **{k: str(answers.get(k) or "").strip()[:1000] for k in DAILY_QUESTIONS}}
    with _lock:
        rows = _read(priv, DAILY, [])
        rows.append(row)
        _write(priv, DAILY, rows[-500:])
    return row


def class_feedback(priv: bytes) -> list[dict]:
    return _read(priv, DAILY, [])


def metrics(priv: bytes, dash: dict) -> dict:
    """The pilot's headline numbers, all from records on this device. They describe use, not learning gains."""
    shared = [r for r in dash["rows"] if r.get("shared")]
    assigned = sum(r["lessons_assigned"] for r in shared)
    completed = sum(r["lessons_completed"] for r in shared)
    daily = class_feedback(priv)
    ratings = [r["useful"] for r in daily]
    # the latest answer wins: by date, then by the moment it was given (weekly feedback rows only have a date)
    answers = [(r["date"], r.get("at", 0), i, r["again"]) for i, r in enumerate(daily) if r.get("again")]
    answers += [(r["date"], 0, i, r["use_again"]) for i, r in enumerate(_read(priv, "feedback_instructor.json", []))
                if r.get("use_again")]
    survey = feedback_summary(priv)
    return {"cadets": dash["cadets"], "active": dash["active"], "active_days": dash.get("active_days"),
            "assignments": assigned, "assignments_completed": completed,
            "assignments_pct": round(100 * completed / assigned) if assigned else None,
            "cadets_with_scenario": sum(1 for r in shared if r.get("scenarios")), "scenarios": dash["scenarios"],
            "avg_lesson_score_pct": dash.get("avg_lesson_score_pct"),
            "rating": round(sum(ratings) / len(ratings), 1) if ratings else None, "rating_days": len(ratings),
            "would_continue": max(answers)[3] if answers else None,
            "cadet_keep_using": survey["averages"].get("again"), "cadet_responses": survey["cadet_responses"]}
