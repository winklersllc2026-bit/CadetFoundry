"""
Board prep: a mock board from the verified study cards, answer grading, and Soldier's Creed recitation.

Grading: with an AI model, the model compares the Soldier's answer to the reference answer from the card.
Without one, a word check: how many of the reference answer's key words the Soldier said. Either way the
reference answer and its source are shown, and the Soldier can overrule the grade.
"""
from __future__ import annotations

import difflib
import json
import re

from recruit import engine

# Checked word for word against army.mil/values/soldiers.html (archived Sep 2025) -- see cards/soldiers_creed.md.
SOLDIERS_CREED = """I am an American Soldier.
I am a warrior and a member of a team.
I serve the people of the United States, and live the Army Values.
I will always place the mission first.
I will never accept defeat.
I will never quit.
I will never leave a fallen comrade.
I am disciplined, physically and mentally tough, trained and proficient in my warrior tasks and drills.
I always maintain my arms, my equipment and myself.
I am an expert and I am a professional.
I stand ready to deploy, engage, and destroy, the enemies of the United States of America in close combat.
I am a guardian of freedom and the American way of life.
I am an American Soldier."""

_STOP = set("a an the and or of to in on at for with by is are be it its as that this your you their from "
            "not no yes than then into each every any".split())


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:[-/][a-z0-9]+)*", (text or "").lower())


def keywords(text: str) -> list[str]:
    return [w for w in dict.fromkeys(_words(text)) if w not in _STOP and (len(w) > 2 or w.isdigit() or "/" in w)]


def word_grade(answer: str, reference: str) -> dict:
    """Share of the reference answer's key words that appear in the Soldier's answer."""
    keys = keywords(reference)
    said = set(_words(answer))
    hit = [k for k in keys if k in said or k.rstrip("s") in said or k + "s" in said]
    score = len(hit) / len(keys) if keys else 0.0
    return {"verdict": "go" if score >= 0.6 else "partial" if score >= 0.3 else "nogo",
            "score": round(score, 2), "missing": [k for k in keys if k not in hit], "how": "words"}


_JUDGE = ("You grade answers at a U.S. Army promotion board practice session. Compare the Soldier's answer with "
          "the reference answer. The answer is correct if it has the same meaning, even in different words. Reply "
          "with JSON only: {\"verdict\": \"go\" | \"partial\" | \"nogo\", \"why\": \"one short sentence\"}.")


def grade(question: str, reference: str, answer: str) -> dict:
    answer = (answer or "").strip()[:2000]
    if not answer:
        return {"verdict": "nogo", "score": 0.0, "missing": keywords(reference), "how": "words", "why": "No answer given."}
    base = word_grade(answer, reference)
    raw = engine.quick([{"role": "system", "content": _JUDGE},
                        {"role": "user", "content": f"Question: {question[:500]}\nReference answer: {reference[:800]}\n"
                                                    f"Soldier's answer: {answer}"}], 120)
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        j = json.loads(m.group(0)) if m else {}
    except ValueError:
        j = {}
    if j.get("verdict") in ("go", "partial", "nogo"):
        return {**base, "verdict": j["verdict"], "why": str(j.get("why", ""))[:200], "how": "ai"}
    return base


def recite(said: str) -> dict:
    """Compare a recitation with the creed word by word: [{"w": word, "ok": bool}], plus extra/wrong words."""
    want, got = _words(SOLDIERS_CREED), _words(said)
    sm = difflib.SequenceMatcher(a=want, b=got, autojunk=False)
    marks, wrong = [False] * len(want), []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                marks[i] = True
        elif tag in ("replace", "insert"):
            wrong.extend(got[j1:j2])
    lines, k = [], 0
    for line in SOLDIERS_CREED.splitlines():
        shown = re.findall(r"[A-Za-z0-9]+", line)          # same words as _words(), original capitals
        lines.append([{"w": w, "ok": marks[k + i]} for i, w in enumerate(shown)])
        k += len(shown)
    right = sum(marks)
    return {"lines": lines, "right": right, "total": len(want), "extra": wrong[:20],
            "perfect": right == len(want) and not wrong}
