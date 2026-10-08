"""
Daily habits: the Daily 10 (with a streak), the private check-in, leave balance,
a simple budget, and faith reading plans. All stored on this device.
"""
from __future__ import annotations

import datetime as dt
import random
import uuid

from vanguard import store

# ── Daily 10 ────────────────────────────────────────────────────────────────

def _today() -> dt.date:
    return dt.date.today()


def daily_questions(brain, n: int = 10) -> list[dict]:
    """Same 10 questions all day (seeded by the date), weighted toward ones missed before."""
    state = random.getstate()
    random.seed(_today().isoformat())
    try:
        return brain.quiz("", n)
    finally:
        random.setstate(state)


def daily_status() -> dict:
    d = store.read_json("daily.json", {})
    days = sorted(d)
    streak, day = 0, _today()
    if day.isoformat() not in d:
        day -= dt.timedelta(days=1)            # today not done yet -- streak counts through yesterday
    while day.isoformat() in d:
        streak += 1
        day -= dt.timedelta(days=1)
    best, run, prev = 0, 0, None
    for s in days:
        cur = dt.date.fromisoformat(s)
        run = run + 1 if prev and (cur - prev).days == 1 else 1
        best, prev = max(best, run), cur
    return {"done_today": _today().isoformat() in d, "today_score": d.get(_today().isoformat()),
            "streak": streak, "best": best, "days": len(d)}


def daily_done(right: int, total: int) -> dict:
    d = store.read_json("daily.json", {})
    d[_today().isoformat()] = {"right": int(right), "total": int(total)}
    store.write_json("daily.json", d)
    return daily_status()


# ── Drill times (report drills) ─────────────────────────────────────────────

def drill_time(drill: str, seconds: float, perfect: bool) -> dict:
    """Record a drill time; only all-correct runs count toward the personal best."""
    t = store.read_json("drill_times.json", {})
    d = t.setdefault(drill[:40], {"best": None, "runs": 0})
    d["runs"] += 1
    new_best = perfect and (d["best"] is None or seconds < d["best"])
    if new_best:
        d["best"] = round(float(seconds), 1)
    store.write_json("drill_times.json", t)
    return {"best": d["best"], "new_best": new_best, "runs": d["runs"]}


# ── Daily check-in ──────────────────────────────────────────────────────────

def checkins() -> list[dict]:
    return sorted(store.read_lines("checkins.jsonl"), key=lambda r: r["date"], reverse=True)


def add_checkin(mood: int, stress: int, sleep: float, note: str = "") -> dict:
    rows = [r for r in store.read_lines("checkins.jsonl") if r["date"] != _today().isoformat()]
    row = {"date": _today().isoformat(), "mood": max(1, min(5, int(mood))), "stress": max(1, min(5, int(stress))),
           "sleep": max(0.0, min(24.0, float(sleep))), "note": (note or "")[:1000]}
    store.write_lines("checkins.jsonl", rows + [row])
    return {"row": row, "concern": concern()}


def concern() -> str | None:
    """A gentle nudge when the last few check-ins trend hard. Never shared with anyone."""
    recent = checkins()[:5]
    if len(recent) < 3:
        return None
    low = sum(1 for r in recent[:3] if r["mood"] <= 2 or r["stress"] >= 4)
    short_sleep = sum(1 for r in recent[:3] if r["sleep"] < 5)
    if low >= 3:
        return ("Your last few check-ins have been rough. That happens to a lot of Soldiers, and you don't have to carry "
                "it alone — talk to your battle buddy, a chaplain, or behavioral health. If it ever feels like too much, "
                "call 988 and press 1 (or text 838255), any time.")
    if short_sleep >= 3:
        return ("You've been short on sleep for several days. Sleep is part of readiness (FM 7-22) — if it keeps up, "
                "let your leadership or sick call know.")
    return None


# ── Sleep (from the check-ins) ──────────────────────────────────────────────
# FM 7-22 (2020, ch. 11): most Soldiers need 7 to 9 hours every 24 hours (11-3); regularly getting less than
# 7-8 builds a sleep debt (11-11).
SLEEP_TARGET = 7.0


def sleep_summary() -> dict:
    rows = checkins()[:14]
    week = [r for r in rows if (_today() - dt.date.fromisoformat(r["date"])).days < 7]
    hours = [r["sleep"] for r in week]
    return {
        "nights": len(week),
        "avg7": round(sum(hours) / len(hours), 1) if hours else None,
        "short7": sum(1 for h in hours if h < SLEEP_TARGET),
        "debt7": round(sum(max(0.0, SLEEP_TARGET - h) for h in hours), 1),
        "target": SLEEP_TARGET,
        "series": [{"date": r["date"], "sleep": r["sleep"]} for r in reversed(rows)],
    }


# ── My people: support contacts the Soldier enters once (shown with crisis help) ─────
SUPPORT_ROLES = ("Battle buddy", "Leader", "Chaplain", "Behavioral Health", "Family", "Friend", "Other")


def support() -> list[dict]:
    return store.read_json("support.json", [])


def save_support(rows) -> list[dict]:
    clean = []
    for r in (rows or [])[:12]:
        if not isinstance(r, dict) or not (str(r.get("name", "")).strip() or str(r.get("phone", "")).strip()):
            continue
        role = str(r.get("role", "Other"))
        clean.append({"role": role if role in SUPPORT_ROLES else "Other", "name": str(r.get("name", ""))[:60].strip(),
                      "phone": str(r.get("phone", ""))[:30].strip(), "note": str(r.get("note", ""))[:80].strip()})
    store.write_json("support.json", clean)
    return clean


# ── Where am I in Basic? ─────────────────────────────────────────────────────
# goarmy.com/army-life/basic-training (U.S. Army, read Oct 2026): four phases over 10 weeks.
BCT_SOURCE = "U.S. Army, Basic Combat Training (goarmy.com/army-life/basic-training)"
BCT_PHASES = [
    ("Yellow", 1, 2, "Adapt to Army life: discipline, teamwork, Army programs and traditions.",
     ["Learn the Army Values", "Begin physical and tactical military training",
      "Build confidence and teamwork on obstacle courses and other terrain"]),
    ("Red", 3, 4, "Train to handle weapons and equipment, and other hands-on Soldier skills.",
     ["Begin familiarization and training with your assigned weapon", "Learn hand-to-hand combat and life-saving skills",
      "Your first field exercise: The Hammer"]),
    ("White", 5, 7, "Rifle training, and working effectively within your small team.",
     ["Basic rifle marksmanship, maintenance and target engagement", "Prioritize multiple targets; more hand-to-hand combat",
      "A two-day, two-night field training exercise: The Anvil"]),
    ("Blue", 8, 10, "Refine and apply everything — your final rite of passage from civilian to Soldier.",
     ["Advanced weaponry such as machine guns and grenades", "More rifle marksmanship and maneuvering",
      "A multiple-day field exercise: The Forge — fitness, Soldier skills and survival"]),
]
BCT_DAY = ["Wake up at 4:30 a.m.; in formation by 5:00", "Physical training (PT) 5:00–6:30 a.m., then breakfast",
           "Train with your Drill Sergeants; lunch at noon, more training, then dinner",
           "Evening: clean the barracks, some personal time", "Lights out at 9:00 p.m. — expect 7 to 8 hours of sleep"]


def bct() -> dict:
    st = store.read_json("bct.json", {"start": ""})
    out = {"start": st.get("start", ""), "phases": BCT_PHASES, "day": BCT_DAY, "source": BCT_SOURCE,
           "week": None, "phase": None, "next": None}
    try:
        start = dt.date.fromisoformat(out["start"])
    except ValueError:
        return out
    days = (_today() - start).days
    out["week"] = days // 7 + 1 if days >= 0 else 0          # 0 = not started yet
    out["days_to_start"] = -days if days < 0 else 0
    for i, (name, first, last, *_rest) in enumerate(BCT_PHASES):
        if first <= out["week"] <= last:
            out["phase"] = i
            out["next"] = i + 1 if i + 1 < len(BCT_PHASES) else None
    if out["week"] == 0:
        out["next"] = 0
    return out


def save_bct(start: str) -> dict:
    store.write_json("bct.json", {"start": str(start or "")[:10]})
    return bct()


# ── PCS / first duty station checklist ──────────────────────────────────────
# From Military OneSource (DoD), "Plan Your Next Military PCS" MilLife Guide (militaryonesource.mil, read Oct 2026).
PCS_SOURCE = "Military OneSource, Plan Your Next Military PCS (militaryonesource.mil)"
PCS_ITEMS = [
    ("Plan the move", [
        ("orders", "Get your orders. Keep the original with you at all times and make more than one copy."),
        ("pmm", "Build a custom moving checklist with Plan My Move (Military OneSource) — on a computer with internet."),
        ("tmo", "Contact your installation transportation office about shipping your household goods (Defense Personal Property System)."),
        ("mfsc", "Visit your Military and Family Support Center — newcomer briefings, relocation help, and the loan closet."),
        ("install", "Look up your new installation with the MilitaryINSTALLATIONS tool: contacts, housing, schools, maps."),
        ("family", "Talk with your family about the move — openly and often, especially with kids."),
        ("milestones", "Break the move into tasks with deadlines, and plan for delays."),
    ]),
    ("Hand-carry these documents (in one binder)", [
        ("doc_orders", "Orders — original plus copies."),
        ("doc_id", "ID for each family member: military IDs, driver's licenses, Social Security cards, passports; birth, marriage and naturalization certificates."),
        ("doc_vehicle", "Vehicle title or lease, inspection, registration and insurance."),
        ("doc_money", "Financial information: checks, recent bank statements, credit and debit cards."),
        ("doc_housing", "Housing papers: the household inventory list from the movers, lease or mortgage paperwork."),
        ("doc_legal", "Legal documents: wills, powers of attorney, custody or adoption papers, divorce papers."),
        ("doc_school", "School records for children (transcripts, report cards, any IEP)."),
        ("doc_medical", "Medical, dental and vaccination records."),
        ("doc_backup", "Back up important files (flash drive, external drive)."),
    ]),
    ("Carry with you", [
        ("meds", "Medication for each family member."),
        ("phone", "Phones and chargers."),
        ("valuables", "Valuables and anything you can't replace."),
        ("box", "A first-days box: toilet paper, soap, cleaners, sheets and towels, an air mattress, snacks — deliveries can run late."),
    ]),
    ("Money", [
        ("budget", "Make a PCS budget and plan for out-of-pocket costs (free financial counseling through Military OneSource)."),
        ("dla", "Ask your finance or transportation office whether you're eligible for a Dislocation Allowance."),
    ]),
]


def pcs() -> dict:
    st = store.read_json("pcs.json", {"report_date": "", "done": [], "custom": []})
    days = None
    if st.get("report_date"):
        try:
            days = (dt.date.fromisoformat(st["report_date"]) - _today()).days
        except ValueError:
            pass
    return {**st, "days": days, "groups": PCS_ITEMS, "source": PCS_SOURCE}


def save_pcs(data: dict) -> dict:
    st = store.read_json("pcs.json", {"report_date": "", "done": [], "custom": []})
    if "report_date" in data:
        st["report_date"] = str(data["report_date"] or "")[:10]
    if "toggle" in data:
        k = str(data["toggle"])[:40]
        st["done"] = [x for x in st["done"] if x != k] if k in st["done"] else st["done"] + [k]
    if str(data.get("add", "")).strip() and len(st["custom"]) < 40:
        st["custom"].append({"id": "c" + uuid.uuid4().hex[:6], "text": str(data["add"]).strip()[:200]})
    if data.get("remove"):
        st["custom"] = [c for c in st["custom"] if c["id"] != data["remove"]]
        st["done"] = [x for x in st["done"] if x != data["remove"]]
    store.write_json("pcs.json", st)
    return pcs()


# ── Leave ───────────────────────────────────────────────────────────────────
# Active-duty members earn 2.5 days of leave for each month of active service (10 U.S.C. § 701(a)).

def leave() -> dict:
    return store.read_json("leave.json", {"start": "", "starting_balance": 0, "used": []})


def save_leave(data: dict) -> dict:
    lv = leave()
    if "start" in data:
        lv["start"] = str(data["start"])[:10]
    if "starting_balance" in data:
        lv["starting_balance"] = float(data["starting_balance"] or 0)
    if data.get("add"):
        a = data["add"]
        lv["used"].append({"id": uuid.uuid4().hex[:8], "from": str(a.get("from", ""))[:10], "to": str(a.get("to", ""))[:10],
                           "days": float(a.get("days") or 0), "kind": str(a.get("kind", "Ordinary leave"))[:40]})
    if data.get("delete"):
        lv["used"] = [u for u in lv["used"] if u["id"] != data["delete"]]
    store.write_json("leave.json", lv)
    return leave_summary()


def leave_summary() -> dict:
    lv = leave()
    earned, months = 0.0, 0
    if lv.get("start"):
        try:
            s = dt.date.fromisoformat(lv["start"])
            t = _today()
            months = max(0, (t.year - s.year) * 12 + (t.month - s.month) - (1 if t.day < s.day else 0))
            earned = months * 2.5
        except ValueError:
            pass
    used = sum(u["days"] for u in lv["used"])
    return {**lv, "months": months, "earned": earned, "used_total": used,
            "balance": round(float(lv.get("starting_balance") or 0) + earned - used, 1)}


# ── Budget ──────────────────────────────────────────────────────────────────

def budget() -> dict:
    return store.read_json("budget.json", {"income": [], "expenses": [], "goal": ""})


def save_budget(data: dict) -> dict:
    clean = lambda rows: [{"name": str(r.get("name", ""))[:60], "amount": round(float(r.get("amount") or 0), 2)}
                          for r in (rows or [])[:60] if str(r.get("name", "")).strip()]
    b = {"income": clean(data.get("income")), "expenses": clean(data.get("expenses")), "goal": str(data.get("goal", ""))[:200]}
    store.write_json("budget.json", b)
    return b


# ── Faith reading plans ─────────────────────────────────────────────────────

PLANS = [
    # id, name, text id needed, list of (book, chapter) per day
    ("psalms", "Psalms — one a day (150 days)", "bible", [("PSA", c) for c in range(1, 151)]),
    ("proverbs", "Proverbs — a chapter a day (31 days)", "bible", [("PRO", c) for c in range(1, 32)]),
    ("gospels", "The four Gospels (89 days)", "bible",
     [("MAT", c) for c in range(1, 29)] + [("MRK", c) for c in range(1, 17)] +
     [("LUK", c) for c in range(1, 25)] + [("JHN", c) for c in range(1, 22)]),
    ("torah_genesis", "Genesis (50 days)", "bible", [("GEN", c) for c in range(1, 51)]),
    ("quran", "The Quran — a surah a day (114 days)", "quran", [("QUR", c) for c in range(1, 115)]),
    ("gita", "Bhagavad Gita — a chapter a day (18 days)", "gita", [("GIT", c) for c in range(1, 19)]),
    ("dhammapada", "Dhammapada — a chapter a day (26 days)", "dhammapada", [("DHP", c) for c in range(1, 27)]),
    ("tao", "Tao Te Ching — a chapter a day (81 days)", "tao", [("TAO", c) for c in range(1, 82)]),
    ("bom", "Book of Mormon — 1 Nephi (22 days)", "bom", [("1NE", c) for c in range(1, 23)]),
]


def plans(faith) -> list[dict]:
    progress = store.read_json("faith_plans.json", {})
    out = []
    for pid, name, need, days in PLANS:
        book = days[0][0]
        if not faith.texts_with(book):
            continue
        p = progress.get(pid, {})
        out.append({"id": pid, "name": name, "days": len(days), "started": bool(p),
                    "done": len(p.get("done", [])), "next": next((i for i in range(len(days)) if i not in p.get("done", [])), None)})
    return out


def plan_day(faith, pid: str, day: int | None, preferred: list[str]) -> dict:
    plan = next((p for p in PLANS if p[0] == pid), None)
    if not plan:
        return {"error": "No such plan."}
    progress = store.read_json("faith_plans.json", {}).get(pid, {"done": []})
    if day is None:
        day = next((i for i in range(len(plan[3])) if i not in progress.get("done", [])), 0)
    day = max(0, min(len(plan[3]) - 1, day))
    book, ch = plan[3][day]
    texts = faith.texts_with(book)
    t = next((x for x in texts if x["id"] in preferred), texts[0] if texts else None)
    if not t:
        return {"error": "That text isn't installed."}
    verses = faith.passage(t["id"], book, ch, 0, 0)
    return {"plan": plan[1], "day": day, "days": len(plan[3]), "text": t["name"], "verses": verses,
            "done": day in progress.get("done", [])}


def plan_mark(pid: str, day: int) -> dict:
    progress = store.read_json("faith_plans.json", {})
    p = progress.setdefault(pid, {"started": _today().isoformat(), "done": []})
    if day not in p["done"]:
        p["done"].append(int(day))
    store.write_json("faith_plans.json", progress)
    return {"done": len(p["done"])}
