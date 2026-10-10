"""
Instructor analytics and reports (Phase 9).

Built from each Cadet's class records through their class key (instructor.class_key) -- never private files. The
dashboard answers "how is my class doing?" in a few numbers (owner's spec §18); the per-Cadet rows are the
drill-down and the CSV export. Exports happen only when the instructor asks (spec §25, §41).
"""
from __future__ import annotations

import csv
import io
import time

from vanguard import instructor, lessons, profiles, progress, security, service, store

ACTIVE_DAYS = 14


def _units_under(roster: dict, unit: str) -> set[str]:
    wanted, frontier = {unit}, [unit]
    while frontier:
        parent = frontier.pop()
        for u in roster["units"]:
            if u["parent"] == parent and u["id"] not in wanted:
                wanted.add(u["id"])
                frontier.append(u["id"])
    return wanted


def _last_active(pid: str) -> str:
    """The latest date of any class-record activity (inside that Cadet's class-key context)."""
    dates = []
    study = store.read_json("study.json", {})
    stamps = [r.get("last", 0) for r in study.values() if r.get("last")]
    if stamps:
        dates.append(time.strftime("%Y-%m-%d", time.localtime(max(stamps))))
    for w in store.read_json("assignments.json", {}).values():
        dates += [w.get("completed", ""), w.get("started", "")]
    dates += [e.get("date", "") for e in store.read_lines("scenarios.jsonl")]
    dates += [e.get("logged", "") or e.get("date", "") for e in store.read_lines("service.jsonl")]
    dates += [e.get("date", "") for e in store.read_lines("fitness.jsonl")]
    dates += [e.get("date", "") for e in store.read_lines("exams.jsonl")]
    dates = [d for d in dates if d]
    return max(dates) if dates else ""


def cadet_rows(priv: bytes, library, unit: str = "", owner: str = "") -> list[dict]:
    """unit: one unit and its sub-units. owner: an instructor's profile id -- "My Cadets" (their units)."""
    r = instructor.roster(priv)
    keep = _units_under(r, unit) if unit else None
    if owner:
        keep = set().union(*[_units_under(r, u["id"]) for u in r["units"] if u.get("owner") == owner]) or set()
    names = {u["id"]: u["name"] for u in r["units"]}
    today = time.strftime("%Y-%m-%d")
    cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - ACTIVE_DAYS * 86400))
    rows = []
    for p in profiles.all_profiles():
        if p["kind"] != "cadet":
            continue
        meta = r["cadets"].get(p["id"], {})
        if keep is not None and meta.get("unit") not in keep:
            continue
        row = {"id": p["id"], "name": p["name"], "unit": names.get(meta.get("unit", ""), ""), "let": meta.get("let"),
               "shared": True}
        ck, status = instructor.class_key(priv, p["id"])
        if status == "waiting":
            rows.append({**row, "shared": False})
            continue
        with security.as_profile(p["id"], None, ck):
            pf = progress.portfolio(library, p["id"])
            work = store.read_json("assignments.json", {})
            mine = [a for a in lessons.all_assignments() if p["id"] in lessons.recipients(a)]
            overdue = sum(1 for a in mine if a.get("due") and a["due"] < today
                          and (work.get(a["id"]) or {}).get("state") != "complete")
            last = _last_active(p["id"])
            pending = sum(1 for e in service.entries() if e.get("status") == "pending")
        ac, ft, sv = pf["academics"], pf["fitness"], pf["service"]
        rows.append({**row, "lessons_assigned": ac["lessons_assigned"], "lessons_completed": ac["lessons_completed"],
                     "lessons_overdue": overdue, "lesson_score_pct": ac["lesson_score_pct"],
                     "cards_mastered": ac["cards_mastered"], "scenarios": pf["leadership"]["scenarios_completed"],
                     "fitness_improvement_pct": ft["avg_improvement_pct"], "service_hours": sv["verified_hours"],
                     "service_pending": pending, "last_active": last, "active": bool(last and last >= cutoff)})
    return rows


def dashboard(priv: bytes, library, unit: str = "", owner: str = "") -> dict:
    rows = cadet_rows(priv, library, unit, owner)
    shared = [x for x in rows if x["shared"]]
    assigned = sum(x["lessons_assigned"] for x in shared)
    completed = sum(x["lessons_completed"] for x in shared)
    scores = [x["lesson_score_pct"] for x in shared if x["lesson_score_pct"] is not None]
    fit = [x["fitness_improvement_pct"] for x in shared if x["fitness_improvement_pct"] is not None]
    return {"unit": unit, "cadets": len(rows), "waiting_to_share": len(rows) - len(shared),
            "active": sum(1 for x in shared if x["active"]), "active_days": ACTIVE_DAYS,
            "lesson_completion_pct": round(100 * completed / assigned) if assigned else None,
            "avg_lesson_score_pct": round(sum(scores) / len(scores)) if scores else None,
            "avg_fitness_improvement_pct": round(sum(fit) / len(fit)) if fit else None,
            "service_hours": sum(x["service_hours"] for x in shared),
            "scenarios": sum(x["scenarios"] for x in shared),
            "service_pending": sum(x["service_pending"] for x in shared),
            "lessons_overdue": sum(x["lessons_overdue"] for x in shared),
            "rows": rows}


CSV_COLUMNS = [("name", "Cadet"), ("unit", "Unit"), ("let", "LET"), ("lessons_completed", "Lessons completed"),
               ("lessons_assigned", "Lessons assigned"), ("lessons_overdue", "Lessons overdue"),
               ("lesson_score_pct", "Lesson score %"), ("cards_mastered", "Study cards mastered"),
               ("scenarios", "Leadership scenarios"), ("fitness_improvement_pct", "Fitness improvement %"),
               ("service_hours", "Service hours (verified)"), ("service_pending", "Service entries waiting"),
               ("last_active", "Last active")]


def to_csv(rows: list[dict]) -> str:
    """The class as a spreadsheet. Cells starting with = + - @ are prefixed so a spreadsheet never runs them."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([label for _k, label in CSV_COLUMNS])
    for r in rows:
        cells = []
        for k, _label in CSV_COLUMNS:
            v = r.get(k)
            v = "" if v is None else str(v)
            if not r.get("shared") and k not in ("name", "unit", "let"):
                v = "waiting to share" if k == "lessons_completed" else ""
            cells.append("'" + v if v[:1] in ("=", "+", "-", "@") else v)
        w.writerow(cells)
    return out.getvalue()
