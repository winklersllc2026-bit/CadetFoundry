"""Live in-class pop quiz (Phase 11): the instructor puts one question on the projector and every Cadet answers on their
own device at the same time, like the classroom scenario vote.

Owner's rules carried over from every other quiz: the Cadet's answer is graded here, never self-reported; the answer is
never sent to a Cadet's screen before the instructor reveals it; and a wrong answer is never a mark against anyone.

* One question at a time, from a study card (so a right answer also counts in the Cadet's study progress) or written
  by the instructor on the spot.
* Practice (multiple choice) or Challenge (typed). One answer per Cadet -- no changing it after seeing neighbors.
* Cadets see only "answer received" until the reveal; then their own result and the answer.
* The projector shows counts only (how many answered, how many right). Like the scenario vote, it never shows who
  answered what.

State lives in this program's memory only, never on disk (security review, 2026-10-11): the answers are tied to
profile ids for one-answer-each and each Cadet's own result, and a live question only lasts a class period. If
Cadet Foundry closes, the live question ends. A live_quiz.json left by an older version is read once and deleted.
"""
from __future__ import annotations

import json
import random
import threading
import time
import uuid
from pathlib import Path

from cadetfoundry import board, exam, store

_lock = threading.Lock()


_STATE: dict = {}                                     # the live question, in memory only
_legacy_checked = False


def _legacy_path() -> Path:
    return store.DATA / "program" / "live_quiz.json"


def _read() -> dict:
    """The live question (a copy). The first call takes over a live_quiz.json an older version left on disk."""
    global _legacy_checked
    if not _legacy_checked:
        _legacy_checked = True
        path = _legacy_path()
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(old, dict) and old and not _STATE:
                _STATE.update(old)
        except (OSError, ValueError):
            pass
        path.unlink(missing_ok=True)
    return json.loads(json.dumps(_STATE)) if _STATE else {}


def _write(state: dict) -> None:
    _STATE.clear()
    _STATE.update(json.loads(json.dumps(state)))


def _clean(s, n: int) -> str:
    return " ".join(str(s or "").split())[:n]


def start(brain, qid: str = "", q: str = "", a: str = "", choices: list | None = None, mode: str = "typed") -> dict:
    """Start a live question. Either a study-card question id (``card#index``) or the instructor's own question and
    answer. ``mode`` is "mc" (four choices) or "typed". Starting a new question replaces the old one."""
    mode = "mc" if mode == "mc" else "typed"
    if qid:
        item = brain.quiz_item(_clean(qid, 80))
        if not item:
            raise LookupError("That question isn't available.")
        q, a, qid = item["q"], item["a"], item["id"]
        if mode == "mc":
            choices = brain.for_screen([item], "mc")[0].get("choices") or []
    else:
        q, a = _clean(q, 300), _clean(a, 300)
        if not q or not a:
            raise ValueError("Write the question and its answer.")
        if mode == "mc":
            wrong = [_clean(c, 200) for c in (choices or []) if _clean(c, 200)]
            wrong = [c for c in dict.fromkeys(wrong) if exam._norm(c) != exam._norm(a)][:5]
            if len(wrong) < 1:
                raise ValueError("For multiple choice, add at least one wrong choice.")
            choices = wrong + [a]
            random.shuffle(choices)
        qid = "live-" + uuid.uuid4().hex[:8]
    state = {"id": qid, "q": q, "a": a, "mode": mode, "choices": choices if mode == "mc" else [],
             "started": time.time(), "revealed": False, "answers": {}}
    with _lock:
        _write(state)
    return state


def reveal(on: bool = True) -> None:
    with _lock:
        state = _read()
        if state:
            state["revealed"] = bool(on)
            _write(state)


def stop() -> None:
    with _lock:
        _read()                                  # (removes an older version's file too)
        _STATE.clear()


def answer(pid: str, text: str = "", choice: str | None = None, use_ai: bool = False) -> dict:
    """Grade one Cadet's answer. One answer each; the result is shown to them after the reveal."""
    with _lock:
        state = _read()
        if not state:
            raise LookupError("There's no live question right now.")
        if state["revealed"]:
            raise ValueError("Answers are closed — the answer has been shown.")
        if pid in state["answers"]:
            raise ValueError("You already answered this one.")
        if state["mode"] == "mc":
            if choice not in state["choices"]:
                raise ValueError("Pick one of the choices.")
            ok = exam._norm(choice) == exam._norm(state["a"])
            g = {"verdict": "right" if ok else "wrong", "correct": ok, "choice": state["choices"].index(choice)}
        else:
            text = _clean(text, 500)
            if not text:
                raise ValueError("Type an answer first.")
            r = board.quiz_grade(state["q"], state["a"], text, use_ai=use_ai)
            g = {"verdict": r["verdict"], "correct": r["correct"]}
        state["answers"][pid] = g
        _write(state)
    if not state["id"].startswith("live-"):              # a study-card question also counts in study progress
        store.record_answer(state["id"], g["correct"])
    return g


def for_cadet(pid: str) -> dict:
    state = _read()
    if not state:
        return {}
    mine = state["answers"].get(pid)
    out = {"id": state["id"], "q": state["q"], "mode": state["mode"], "choices": state["choices"],
           "answered": mine is not None, "revealed": state["revealed"]}
    if state["revealed"]:
        out["answer"] = state["a"]
        if mine:
            out["verdict"] = mine["verdict"]
    return out


def for_instructor() -> dict:
    """Counts only -- never who answered what."""
    state = _read()
    if not state:
        return {}
    marks = list(state["answers"].values())
    out = {"id": state["id"], "q": state["q"], "a": state["a"], "mode": state["mode"], "choices": state["choices"],
           "revealed": state["revealed"], "answered": len(marks),
           "right": sum(m["verdict"] == "right" for m in marks), "close": sum(m["verdict"] == "close" for m in marks)}
    if state["mode"] == "mc":
        counts = [0] * len(state["choices"])
        for m in marks:
            if 0 <= m.get("choice", -1) < len(counts):
                counts[m["choice"]] += 1
        out["counts"] = counts
    return out
