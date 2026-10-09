"""
The instructor's edits to the built-in study-card quiz questions, for this program (owner's request, Phase 9):
change a question's wording or answer, or hide it. Stored in program/quiz_overrides.json; quizzes, the Daily 10 and
grading all use the edited version. The study card itself (its source text) is never changed.
"""
from __future__ import annotations

import json
import threading

from vanguard import store

_lock = threading.Lock()


def _path():
    return store.DATA / "program" / "quiz_overrides.json"


def overrides() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def apply(qid: str, q: str, a: str) -> tuple[str, str] | None:
    """(question, answer) as this program uses it, or None if the instructor hid it."""
    o = overrides().get(qid)
    if not o:
        return q, a
    if o.get("hidden"):
        return None
    return o.get("q") or q, o.get("a") or a


def save(qid: str, q: str = "", a: str = "", hidden: bool = False) -> dict:
    q, a = " ".join(str(q or "").split())[:300], " ".join(str(a or "").split())[:500]
    with _lock:
        rows = overrides()
        rows[qid] = {k: v for k, v in (("q", q), ("a", a), ("hidden", bool(hidden))) if v}
        if not rows[qid]:
            rows.pop(qid)
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows), encoding="utf-8")
        tmp.replace(path)
    return rows.get(qid, {})


def reset(qid: str) -> None:
    save(qid)
