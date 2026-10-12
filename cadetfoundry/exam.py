"""
Exam mode: a timed, multiple-choice test on one topic (or everything), graded on the device.

Questions and answers come from the verified study cards. Wrong choices come from choices.py: the same kind
of answer, about the same sort of thing, never a piece of the right one. Questions without a fair set are left out. The answer key stays on the server
until the exam is submitted. Each result goes into the Soldier's exam history, and missed questions
come back more often in quizzes.
"""
from __future__ import annotations

import random
import re
import time
import uuid

from cadetfoundry import choices as choice_maker, knowledge, store

SECONDS_PER_QUESTION = 45
HISTORY = "exams.jsonl"
CURRENT = "exam_current.json"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()



def start(library, topic: str = "", n: int = 10) -> dict:
    items = [(c, i, q, a) for c in library.cards if knowledge.matches(c, topic)
             for i, (q, a) in enumerate(c.quiz)]
    if not items:
        raise ValueError("No questions for that topic.")
    random.shuffle(items)
    questions, key = [], []
    for c, i, q, a in items:
        if len(questions) >= max(1, n):
            break
        choices = choice_maker.build(library, c, q, a)
        if not choices or len(choices) < 4:               # no fair set of four: typed answers and practice only
            continue
        questions.append({"q": q, "choices": choices, "topic": c.topic})
        key.append({"id": f"{c.id}#{i}", "answer": choices.index(choice_maker.right_choice(q, a)), "source": c.source,
                    "card": c.title, "full": a})
    if not questions:
        raise ValueError("No questions for that topic.")
    exam = {"id": uuid.uuid4().hex[:10], "topic": topic or "All topics", "started": time.time(),
            "limit": SECONDS_PER_QUESTION * len(questions), "questions": questions, "key": key}
    store.write_json(CURRENT, exam)
    return {k: exam[k] for k in ("id", "topic", "limit", "questions")}


def submit(exam_id: str, answers: dict) -> dict:
    exam = store.read_json(CURRENT, None)
    if not exam or exam.get("id") != exam_id:
        raise ValueError("That exam isn't open any more — start a new one.")
    store.write_json(CURRENT, {})                          # one submission per exam
    seconds = round(time.time() - exam["started"])
    late = seconds > exam["limit"] + 5                    # a few seconds' grace for the device
    results, right = [], 0
    for i, (q, k) in enumerate(zip(exam["questions"], exam["key"])):
        try:
            chose = int(answers.get(str(i)))
        except (TypeError, ValueError):
            chose = None
        ok = chose == k["answer"]
        right += ok
        store.record_answer(k["id"], ok)
        results.append({"q": q["q"], "chose": chose, "answer": k["answer"], "choices": q["choices"], "ok": ok,
                        "source": k["source"]})
    row = {"date": time.strftime("%Y-%m-%d"), "topic": exam["topic"], "right": right, "total": len(results),
           "seconds": seconds, "late": late}
    store.write_lines(HISTORY, store.read_lines(HISTORY)[-199:] + [row])
    return {**row, "results": results, "history": history()}


def history() -> dict:
    rows = store.read_lines(HISTORY)
    best: dict[str, dict] = {}
    for r in rows:
        pct = r["right"] / r["total"] if r["total"] else 0
        b = best.get(r["topic"])
        if not b or pct > b["pct"] or (pct == b["pct"] and r["seconds"] < b["seconds"]):
            best[r["topic"]] = {"pct": pct, "right": r["right"], "total": r["total"], "seconds": r["seconds"], "date": r["date"]}
    return {"recent": list(reversed(rows[-10:])), "best": best}
