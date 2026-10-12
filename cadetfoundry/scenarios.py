"""
Leadership scenarios (Phase 5): a situation, choices, what happened, and a reflection for the leadership log.

No scores and no "right answer" verdicts (owner's spec: "Here's what happened. Here's another way to approach it.
What would you do next time?"). Scenarios are about everyday Cadet leadership -- never combat.

  * Practice scenarios ship in cadetfoundry/scenarios/*.md, labeled as Cadet Foundry practice material, not curriculum.
  * Instructors write their own in the same format (program/scenarios.json).
  * A Cadet's completed scenarios go to their leadership log, scenarios.jsonl -- a class record the instructor can
    read (store.CLASS_FILES).
  * Classroom mode: the instructor runs a live, anonymous vote on one scenario (program/live.json).

Format:

    Title: Two Cadets arguing
    Competency: Conflict resolution
    Situation:
    You're the squad leader...
    Choice: Tell them both to knock it off.
    Outcome: ...
    Strengths: ...
    Weaknesses: ...
    Choice: ...
    Principles:
    - Listen before you decide
    Other approaches:
    ...
    Reflection: What would you do differently next time?
    Notice: (instructor only) what Cadets should notice
    Discussion:
    - (instructor only) a question for the class
    Follow-up: (instructor only) an optional activity

Notice, Discussion and Follow-up are the instructor's debrief: shown on the instructor's own screens, never sent to a
Cadet and never put on the projector.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path

from cadetfoundry import store

BUILTIN_DIR = Path(__file__).resolve().parent / "scenarios"
DEFAULT_REFLECTION = "What would you do differently next time?"
_FIELDS = ("title", "competency", "situation", "choice", "outcome", "strengths", "weaknesses", "principles",
           "other approaches", "reflection", "notice", "discussion", "follow-up")
_lock = threading.Lock()


def parse(text: str) -> dict:
    """The scenario format above -> dict. Raises ValueError with a plain message."""
    sc = {"title": "", "competency": "", "situation": "", "choices": [], "principles": [], "alternatives": "",
          "reflection": "", "notice": "", "discussion": [], "follow_up": ""}
    field, buf = None, []

    def flush():
        val = "\n".join(buf).strip()
        if field is None:
            if val:
                raise ValueError("Start with 'Title:'.")
        elif field in ("title", "competency", "situation", "reflection", "notice"):
            sc[field] = val
        elif field == "follow-up":
            sc["follow_up"] = val
        elif field == "discussion":
            sc["discussion"] = [re.sub(r"^[-*•]\s*", "", x).strip() for x in val.splitlines() if x.strip()][:8]
        elif field == "other approaches":
            sc["alternatives"] = val
        elif field == "principles":
            sc["principles"] = [re.sub(r"^[-*•]\s*", "", x).strip() for x in val.splitlines() if x.strip()]
        elif field == "choice":
            sc["choices"].append({"text": val, "outcome": "", "strengths": "", "weaknesses": ""})
        elif field in ("outcome", "strengths", "weaknesses"):
            if not sc["choices"]:
                raise ValueError(f"'{field.title()}:' must come after a 'Choice:'.")
            sc["choices"][-1][field] = val
        buf.clear()

    for line in (text or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"^\s*(%s)\s*:\s*(.*)$" % "|".join(_FIELDS), line, re.I)
        if m:
            flush()
            field = m.group(1).lower()
            if m.group(2).strip():
                buf.append(m.group(2).strip())
        else:
            buf.append(line)
    flush()
    if not sc["title"] or not sc["situation"]:
        raise ValueError("A scenario needs a Title and a Situation.")
    if not 2 <= len(sc["choices"]) <= 4:
        raise ValueError("A scenario needs 2 to 4 choices.")
    for i, c in enumerate(sc["choices"], 1):
        if not c["text"] or not c["outcome"]:
            raise ValueError(f"Choice {i} needs its text and an Outcome.")
    for k, n in (("title", 100), ("competency", 60), ("situation", 3000), ("alternatives", 3000), ("reflection", 300),
                 ("notice", 1000), ("follow_up", 1000)):
        sc[k] = sc[k][:n]
    sc["reflection"] = sc["reflection"] or DEFAULT_REFLECTION
    return sc


def to_text(sc: dict) -> str:
    out = [f"Title: {sc['title']}", f"Competency: {sc['competency']}", "Situation:", sc["situation"]]
    for c in sc["choices"]:
        out += [f"Choice: {c['text']}", f"Outcome: {c['outcome']}"]
        if c["strengths"]:
            out.append(f"Strengths: {c['strengths']}")
        if c["weaknesses"]:
            out.append(f"Weaknesses: {c['weaknesses']}")
    if sc["principles"]:
        out += ["Principles:"] + [f"- {p}" for p in sc["principles"]]
    if sc["alternatives"]:
        out += ["Other approaches:", sc["alternatives"]]
    out.append(f"Reflection: {sc['reflection']}")
    if sc.get("notice"):
        out.append(f"Notice: {sc['notice']}")
    if sc.get("discussion"):
        out += ["Discussion:"] + [f"- {q}" for q in sc["discussion"]]
    if sc.get("follow_up"):
        out.append(f"Follow-up: {sc['follow_up']}")
    return "\n".join(out)


# ── where scenarios come from ───────────────────────────────────────────────
_builtin_cache: dict = {}


def builtins() -> list[dict]:
    if not _builtin_cache:
        for f in sorted(BUILTIN_DIR.glob("*.md")):
            sc = parse(f.read_text(encoding="utf-8"))
            _builtin_cache[f.stem] = {**sc, "id": f.stem, "origin": "practice"}
    return list(_builtin_cache.values())


def _path(name: str) -> Path:
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


def custom() -> list[dict]:
    return _read("scenarios.json", [])


def all_scenarios() -> list[dict]:
    return builtins() + custom()


def get(sid: str) -> dict:
    sc = next((s for s in all_scenarios() if s["id"] == sid), None)
    if not sc:
        raise LookupError("No such scenario.")
    return sc


def save_custom(sid: str, text: str) -> dict:
    sc = parse(text)
    with _lock:
        rows = custom()
        old = next((s for s in rows if s["id"] == sid), None) if sid else None
        if old:
            old.update(sc)
            sc = old
        else:
            if len(rows) >= 200:
                raise ValueError("Up to 200 instructor scenarios.")
            sc = {**sc, "id": "i-" + uuid.uuid4().hex[:10], "origin": "instructor"}
            rows.append(sc)
        _write("scenarios.json", rows)
    return sc


def delete_custom(sid: str) -> None:
    with _lock:
        _write("scenarios.json", [s for s in custom() if s["id"] != sid])


# ── what a Cadet sees ───────────────────────────────────────────────────────
def summary(sc: dict) -> dict:
    return {"id": sc["id"], "title": sc["title"], "competency": sc["competency"], "origin": sc["origin"]}


def for_cadet(sc: dict) -> dict:
    """The situation and the choices -- outcomes only after choosing."""
    return {**summary(sc), "situation": sc["situation"], "choices": [c["text"] for c in sc["choices"]],
            "reflection": sc["reflection"]}


def explain(sc: dict, choice: int) -> dict:
    if not isinstance(choice, int) or not 0 <= choice < len(sc["choices"]):
        raise ValueError("Pick one of the choices.")
    c = sc["choices"][choice]
    return {"choice": choice, "decision": c["text"], "outcome": c["outcome"], "strengths": c["strengths"],
            "weaknesses": c["weaknesses"], "principles": sc["principles"], "alternatives": sc["alternatives"]}


def debrief(sc: dict) -> dict:
    """The instructor's debrief: principles, what to notice, discussion questions, a follow-up. Instructor only."""
    return {"principles": sc["principles"], "notice": sc.get("notice", ""), "discussion": sc.get("discussion", []),
            "follow_up": sc.get("follow_up", ""), "alternatives": sc["alternatives"]}


def all_outcomes(sc: dict) -> list[dict]:
    return [{"decision": c["text"], "outcome": c["outcome"], "strengths": c["strengths"], "weaknesses": c["weaknesses"]}
            for c in sc["choices"]]


# ── the leadership log (the active Cadet's class records) ───────────────────
LOG = "scenarios.jsonl"


def log_entry(sc: dict, choice: int, reasoning: str, reflection: str, learned: str) -> dict:
    ex = explain(sc, choice)
    if not (reflection or "").strip():
        raise ValueError("Write your reflection first: " + sc["reflection"])
    entry = {"id": uuid.uuid4().hex[:10], "date": time.strftime("%Y-%m-%d"), "scenario": sc["id"], "title": sc["title"],
             "competency": sc["competency"], "situation": sc["situation"][:600], "decision": ex["decision"],
             "reasoning": (reasoning or "").strip()[:2000], "outcome": ex["outcome"],
             "reflection": reflection.strip()[:2000], "learned": (learned or "").strip()[:2000]}
    with _lock:
        store.write_lines(LOG, store.read_lines(LOG)[-499:] + [entry])
    return entry


def my_log() -> list[dict]:
    return list(reversed(store.read_lines(LOG)))


# ── classroom mode: one live, anonymous vote ────────────────────────────────
# The vote lives in this program's memory only, never on disk (security review, 2026-10-11): votes are tied to
# profile ids (one vote each, and each Cadet sees their own), and a vote only lasts a class period. A live.json left
# by an older version is read once and deleted.
_LIVE: dict = {}
_live_checked = False


def live() -> dict:
    global _live_checked
    if not _live_checked:
        _live_checked = True
        old = _read("live.json", {})
        if isinstance(old, dict) and old and not _LIVE:
            _LIVE.update(old)
        _path("live.json").unlink(missing_ok=True)
    return json.loads(json.dumps(_LIVE)) if _LIVE else {}


def _live_write(state: dict) -> None:
    _LIVE.clear()
    _LIVE.update(json.loads(json.dumps(state)))


def live_start(sid: str) -> dict:
    sc = get(sid)
    state = {"scenario": sc["id"], "started": time.time(), "revealed": False, "votes": {}}
    with _lock:
        _live_write(state)
    return state


def live_reveal(on: bool = True) -> None:
    with _lock:
        state = live()
        if state:
            state["revealed"] = bool(on)
            _live_write(state)


def live_stop() -> None:
    with _lock:
        live()                                   # (removes an older version's file too)
        _LIVE.clear()


def live_vote(pid: str, choice: int) -> None:
    with _lock:
        state = live()
        if not state:
            raise LookupError("There's no classroom vote right now.")
        sc = get(state["scenario"])
        if not isinstance(choice, int) or not 0 <= choice < len(sc["choices"]):
            raise ValueError("Pick one of the choices.")
        state["votes"][pid] = choice                     # one vote per Cadet; changing it replaces it
        _live_write(state)


def live_for_cadet(pid: str) -> dict:
    state = live()
    if not state:
        return {}
    try:
        sc = get(state["scenario"])
    except LookupError:
        return {}
    return {"scenario": for_cadet(sc), "my_vote": state["votes"].get(pid), "revealed": state["revealed"]}


def live_for_instructor() -> dict:
    """Counts only -- who voted for what is never shown."""
    state = live()
    if not state:
        return {}
    sc = get(state["scenario"])
    counts = [0] * len(sc["choices"])
    for v in state["votes"].values():
        if 0 <= v < len(counts):
            counts[v] += 1
    out = {"scenario": for_cadet(sc), "counts": counts, "votes": sum(counts), "revealed": state["revealed"]}
    if state["revealed"]:
        out["guidance"] = {"outcomes": all_outcomes(sc), "principles": sc["principles"], "alternatives": sc["alternatives"]}
    return out
