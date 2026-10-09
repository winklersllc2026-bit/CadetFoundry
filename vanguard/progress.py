"""
My Progress (Phase 8): one Cadet's growth, from their class records only.

Everything here is computed from files the Cadet and their instructor can both read (store.CLASS_FILES) -- never
from private files. It runs inside the Cadet's own session, or inside an instructor's request with that Cadet's
class key (security.as_profile(pid, None, class_key)).

No invented scores: the owner's spec shows "Leadership: 87%", but there is no fair way to grade leadership as a
number, so the portfolio shows real counts and real improvement instead. Achievements are milestones, never ranks.
"""
from __future__ import annotations

import time
import uuid

from vanguard import lessons, scenarios, service, store, train
from vanguard.knowledge import CATEGORIES

RECOGNITION = "recognition.jsonl"                     # written by the instructor; the Cadet reads it
KINDS = {"award": "Award", "promotion": "Promotion", "certification": "Certification",
         "recognition": "Recognition", "comment": "Instructor comment"}
SECTIONS = {"academics": "Academics", "leadership": "Leadership", "fitness": "Fitness", "service": "Service",
            "recognition": "Recognition and achievements"}


def _known(r: dict) -> bool:
    """A quiz question the Cadet knows: answered right at least once, and right at least as often as wrong."""
    return r.get("right", 0) > 0 and r.get("right", 0) >= r.get("wrong", 0)


def academics(library, pid: str) -> dict:
    study = store.read_json("study.json", {})
    by_cat: dict[str, dict] = {}
    mastered, cards_total = [], 0
    for c in library.cards:                          # only the cards this profile may see
        if not c.quiz:
            continue
        cards_total += 1
        known = sum(1 for i in range(len(c.quiz)) if _known(study.get(f"{c.id}#{i}", {})))
        tried = sum(1 for i in range(len(c.quiz)) if f"{c.id}#{i}" in study)
        cat = by_cat.setdefault(c.category, {"name": CATEGORIES.get(c.category, c.category), "known": 0, "total": 0,
                                             "tried": 0})
        cat["known"] += known
        cat["total"] += len(c.quiz)
        cat["tried"] += tried
        if known >= max(1, round(0.8 * len(c.quiz))):
            mastered.append(c.title)
    work = store.read_json("assignments.json", {})
    mine = [a for a in lessons.all_assignments() if pid in lessons.recipients(a)]
    done = [work[a["id"]] for a in mine if (work.get(a["id"]) or {}).get("state") == "complete"]
    scored = [w for w in done if w.get("total")]
    exams = store.read_lines("exams.jsonl")
    return {"lessons_assigned": len(mine), "lessons_completed": len(done),
            "lesson_score_pct": round(100 * sum(w["score"] for w in scored) / sum(w["total"] for w in scored)) if scored else None,
            "categories": [v | {"id": k} for k, v in by_cat.items()],
            "cards_mastered": len(mastered), "cards_total": cards_total, "mastered": mastered[:50],
            "exams": len(exams), "best_exam": max((round(100 * e["right"] / e["total"]) for e in exams if e.get("total")), default=None)}


def leadership() -> dict:
    log = scenarios.my_log()
    return {"scenarios_completed": len(log), "different_scenarios": len({e["scenario"] for e in log}),
            "competencies": sorted({e["competency"] for e in log if e.get("competency")}),
            "recent": [{k: e.get(k, "") for k in ("date", "title", "decision", "reflection", "learned")} for e in log[:5]]}


def fitness() -> dict:
    rows, goals = store.read_lines(train.FITNESS), store.read_json(train.GOALS, {})
    evs = [train.stats(e, rows, goals.get(e["id"])) for e in train.events()]
    evs = [e for e in evs if e["count"]]
    pcts = [e["improvement_pct"] for e in evs if e["count"] > 1 and e.get("improvement_pct") is not None]
    return {"events": [{k: e.get(k) for k in ("name", "first", "first_date", "latest", "latest_date", "best", "count",
                                                "improvement_shown", "improvement_pct", "goal", "goal_reached")} for e in evs],
            "avg_improvement_pct": round(sum(pcts) / len(pcts)) if pcts else None,
            "goals_reached": sum(1 for e in evs if e.get("goal_reached"))}


def service_summary() -> dict:
    rows = sorted(service.entries(), key=lambda r: r["date"], reverse=True)
    return {**service.totals(rows), "recent": [{k: r.get(k, "") for k in ("date", "project", "hours", "role", "status", "reflection")}
                                               for r in rows if r.get("status") == "verified"][:5]}


def recognitions() -> list[dict]:
    return list(reversed(store.read_lines(RECOGNITION)))


def achievements(ac: dict, ld: dict, ft: dict, sv: dict) -> list[dict]:
    """Milestones the Cadet has reached -- personal, never compared with anyone (owner's spec §27-28)."""
    out = []
    add = lambda cat, title, ok: ok and out.append({"category": cat, "title": title})
    add("Leadership", "First leadership scenario", ld["scenarios_completed"] >= 1)
    add("Leadership", "Five leadership reflections", ld["scenarios_completed"] >= 5)
    add("Academic", "First lesson completed", ac["lessons_completed"] >= 1)
    add("Academic", "Ten lessons completed", ac["lessons_completed"] >= 10)
    add("Academic", "First study card mastered", ac["cards_mastered"] >= 1)
    add("Academic", "Ten study cards mastered", ac["cards_mastered"] >= 10)
    add("Fitness", "Personal fitness best", any(e["count"] > 1 and e["latest"] == e["best"] for e in ft["events"]))
    add("Fitness", "Fitness goal reached", ft["goals_reached"] >= 1)
    add("Service", "First service project verified", sv["verified_hours"] > 0)
    add("Service", "10 hours of service", sv["verified_hours"] >= 10)
    add("Service", "25 hours of service", sv["verified_hours"] >= 25)
    return out


def timeline(pid: str) -> list[dict]:
    """Month by month: what the Cadet did. Growth over time, in their own numbers."""
    months: dict[str, dict] = {}

    def bump(date: str, key: str, n: float = 1) -> None:
        if not date or len(date) < 7:
            return
        m = months.setdefault(date[:7], {"month": date[:7], "lessons": 0, "scenarios": 0, "service_hours": 0,
                                         "fitness_results": 0, "exams": 0})
        m[key] += n

    for w in store.read_json("assignments.json", {}).values():
        if w.get("state") == "complete":
            bump(w.get("completed", ""), "lessons")
    for e in scenarios.my_log():
        bump(e.get("date", ""), "scenarios")
    for r in service.entries():
        if r.get("status") == "verified":
            bump(r.get("date", ""), "service_hours", r["hours"])
    for r in store.read_lines(train.FITNESS):
        bump(r.get("date", ""), "fitness_results")
    for e in store.read_lines("exams.jsonl"):
        bump(e.get("date", ""), "exams")
    return sorted(months.values(), key=lambda m: m["month"])[-12:]


def portfolio(library, pid: str) -> dict:
    ac, ld, ft, sv = academics(library, pid), leadership(), fitness(), service_summary()
    return {"academics": ac, "leadership": ld, "fitness": ft, "service": sv, "recognition": recognitions(),
            "achievements": achievements(ac, ld, ft, sv), "timeline": timeline(pid)}


# ── the instructor's part ───────────────────────────────────────────────────
def add_recognition(kind: str, title: str, date: str = "", note: str = "") -> dict:
    """Written by the instructor into the Cadet's class records (call with that Cadet's class key)."""
    if kind not in KINDS:
        raise ValueError("Choose award, promotion, certification, recognition or comment.")
    title = " ".join(str(title or "").split())[:120]
    if not title and kind != "comment":
        raise ValueError("Give it a title.")
    row = {"id": uuid.uuid4().hex[:10], "kind": kind, "title": title, "date": str(date or time.strftime("%Y-%m-%d"))[:10],
           "note": str(note or "").strip()[:2000]}
    store.write_lines(RECOGNITION, store.read_lines(RECOGNITION)[-499:] + [row])
    return row


def remove_recognition(rid: str) -> None:
    store.write_lines(RECOGNITION, [r for r in store.read_lines(RECOGNITION) if r.get("id") != rid])


def portfolio_sections() -> list[str]:
    """Which sections the printed portfolio includes -- the instructor's choice (spec §16)."""
    s = store.config().get("portfolio_sections")
    return [x for x in SECTIONS if x in s] if isinstance(s, list) else list(SECTIONS)
