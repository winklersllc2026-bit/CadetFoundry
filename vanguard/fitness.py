"""
Army Fitness Test (AFT) scorer, using the official score tables exactly as published
(AFT Scoring Scales, approved 15 May 2025, effective 1 June 2025 -- vanguard/data/aft_tables.json,
built from the army.mil PDF by tools/aft_tables.py).

Pass standards (Army announcement, 21 April 2025): at least 60 points in every event, and a
total of at least 350 for Soldiers in combat specialties (combat standard: sex-neutral,
age-normed -- the M|C column) or 300 for combat-enabling specialties (general standard).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

TABLES = Path(__file__).resolve().parent / "data" / "aft_tables.json"
EVENT_ORDER = ["MDL", "HRP", "SDC", "PLK", "2MR"]
EVENT_HELP = {
    "MDL": "3-repetition maximum deadlift (pounds)",
    "HRP": "Hand-release push-ups in 2 minutes",
    "SDC": "Sprint / drag / carry time (m:ss)",
    "PLK": "Plank time (m:ss)",
    "2MR": "Two-mile run time (mm:ss)",
}
MIN_EVENT = 60
MIN_TOTAL = {"combat": 350, "general": 300}
STANDARD_NOTE = ("Combat standard: Soldiers in combat specialties — sex-neutral, at least 60 per event and 350 total. "
                 "General standard: combat-enabling specialties — scored by sex and age, at least 60 per event and 300 total.")


@lru_cache(maxsize=1)
def tables() -> dict:
    return json.loads(TABLES.read_text(encoding="utf-8"))


def age_index(age: int) -> int:
    if age < 17:
        raise ValueError("The AFT score tables start at age 17.")
    bounds = [21, 26, 31, 36, 41, 46, 51, 56, 61]
    return next((i for i, hi in enumerate(bounds) if age <= hi), 9)


def parse_raw(event: str, value) -> int:
    """Pounds/reps as whole numbers; times as m:ss (or plain seconds) -> seconds."""
    s = str(value).strip()
    if not s:
        raise ValueError("empty")
    if tables()["events"][event]["unit"] == "time":
        if ":" in s:
            m, sec = s.split(":", 1)
            if not (m.strip().isdigit() and sec.strip().isdigit()) or int(sec) >= 60:
                raise ValueError(f"{event}: write the time as m:ss")
            return int(m) * 60 + int(sec)
        if not s.isdigit():
            raise ValueError(f"{event}: write the time as m:ss")
        return int(s)
    if not s.isdigit():
        raise ValueError(f"{event}: enter a whole number")
    return int(s)


def score_event(event: str, raw: int, age: int, sex: str, standard: str = "general") -> int:
    """Highest point value whose requirement the performance meets; '---' cells are skipped."""
    ev = tables()["events"][event]
    col = age_index(age) * 2 + (0 if standard == "combat" or sex.upper() == "M" else 1)
    for pts, row in ev["rows"].items():                      # stored 100 -> 0
        need = row[col]
        if need is None:
            continue
        if (raw >= need) if ev["higher_is_better"] else (raw <= need):
            return int(pts)
    return 0


def score_test(raw: dict, age: int, sex: str, standard: str = "general") -> dict:
    standard = "combat" if standard == "combat" else "general"
    sex = "F" if str(sex).upper().startswith("F") else "M"
    events, errors = [], []
    for e in EVENT_ORDER:
        if str(raw.get(e, "")).strip() == "":
            continue
        try:
            v = parse_raw(e, raw[e])
            events.append({"event": e, "name": tables()["events"][e]["name"], "raw": raw[e],
                           "points": score_event(e, v, age, sex, standard)})
        except ValueError as ex:
            errors.append(str(ex))
    total = sum(x["points"] for x in events)
    complete = len(events) == len(EVENT_ORDER)
    failed = [x["event"] for x in events if x["points"] < MIN_EVENT]
    weakest = min(events, key=lambda x: x["points"])["event"] if events else None
    return {
        "events": events, "errors": errors, "total": total, "complete": complete,
        "standard": standard, "min_total": MIN_TOTAL[standard], "min_event": MIN_EVENT,
        "failed_events": failed, "weakest": weakest,
        "passed": complete and not failed and total >= MIN_TOTAL[standard],
        "age_group": tables()["ages"][age_index(age)],
        "source": f"AFT score tables (approved {tables()['approved']}, effective {tables()['effective']})",
        "note": STANDARD_NOTE,
    }


# ── Training plan from the Soldier's own logged tests ──────────────────────
# FM 7-22, table 6-2: each H2F drill and the physical component it trains (as published).
DRILLS_BY_COMPONENT = {
    "Muscular strength": ["Suspension Training Drill 1 and 2", "Climbing Drill 1 and 2", "Medicine Ball Drill 1 and 2",
                          "Landmine Drill 1 and 2"],
    "Muscular endurance": ["Preparation Drill", "Four for the Core", "Shoulder Stability Drill", "Hip Stability Drill",
                           "Recovery Drill", "Preventive Maintenance Checks and Services"],
    "Power": ["Strength Training Circuit", "Free Weight Core and Assistive"],
    "Anaerobic endurance": ["Conditioning Drill 1-3", "30:60s and 60:120s", "Guerilla Drill", "300 Meter Shuttle Run",
                            "Hill Repeats"],
    "Aerobic endurance": ["Military Movement Drill 1 and 2", "Running Drill 1-7", "Release Run", "Terrain Run", "Foot March"],
}
SHORT_NAMES = {"MDL": "deadlift", "HRP": "hand-release push-ups", "SDC": "sprint-drag-carry", "PLK": "plank",
               "2MR": "two-mile run"}
_LOGGED = re.compile(r"\b(MDL|HRP|SDC|PLK|2MR) (\S+) = (\d+)")


def history(log_rows: list[dict]) -> list[dict]:
    """AFT results saved to the logbook by the scorer ("AFT (...): MDL 250 = 81, HRP 40 = 83, ..."), oldest first."""
    tests = []
    for r in log_rows:
        text = r.get("text", "")
        if not text.startswith("AFT"):
            continue
        events = {e: {"raw": raw, "points": int(p)} for e, raw, p in _LOGGED.findall(text)}
        if events:
            tests.append({"date": r.get("date", ""), "events": events, "total": sum(v["points"] for v in events.values())})
    return sorted(tests, key=lambda t: t["date"])


def plan(log_rows: list[dict]) -> dict:
    tests = history(log_rows)
    if not tests:
        return {"tests": [], "message": "Score a test above and save it to your logbook — your plan builds from it."}
    last, prev = tests[-1], (tests[-2] if len(tests) > 1 else None)
    rows = []
    for e in EVENT_ORDER:
        if e not in last["events"]:
            continue
        pts = last["events"][e]["points"]
        change = pts - prev["events"][e]["points"] if prev and e in prev["events"] else None
        rows.append({"event": e, "name": EVENT_HELP[e], "raw": last["events"][e]["raw"], "points": pts,
                     "change": change, "below_min": pts < MIN_EVENT})
    weakest = min(rows, key=lambda r: r["points"])
    target = min(100, max(MIN_EVENT, weakest["points"] + 10))
    name = SHORT_NAMES[weakest["event"]]
    goal = {"event": weakest["event"], "name": name,
            "short": f"In 3 months, I will raise my {name} from {weakest['points']} to {target} points.",
            # modeled on FM 7-22 table 9-4's sample SMART goal ("Run faster")
            "steps": f"Every week, I will do one to two training sessions aimed at my {name}, with a 5–10-minute "
                     "warm-up and a 10–15-minute cool-down, and refuel after every workout. Then I'll retest."}
    return {"tests": tests, "latest": last["date"], "rows": rows, "weakest": weakest["event"], "goal": goal,
            "drills": DRILLS_BY_COMPONENT, "min_event": MIN_EVENT,
            "source": "Goal-setting: FM 7-22 para 9-41 and table 9-4 (SMART goals). Drills: FM 7-22 table 6-2."}
