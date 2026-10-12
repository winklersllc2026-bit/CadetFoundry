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

from cadetfoundry import engine

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


_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
        "seventeen eighteen nineteen".split()
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
        "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
        "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "thirtieth": 30}


def _num(w: str) -> str:
    """Number words as digits, so "seven" matches "7" and "nineteenth" matches "19th" (both become "19")."""
    if w in _ONES:
        return str(_ONES.index(w))
    if w in _TENS:
        return str(_TENS[w])
    if w in _ORD:
        return str(_ORD[w])
    m = re.fullmatch(r"(\d+)(?:st|nd|rd|th)", w)     # "19th" == "nineteenth" == "XIX" == "19"
    if m:
        return m.group(1)
    tens, _, unit = w.partition("-")                 # "twenty-seven", "twenty-sixth"
    if tens in _TENS and unit:
        if unit in _ONES[1:10]:
            return str(_TENS[tens] + _ONES.index(unit))
        if unit in _ORD and _ORD[unit] < 10:
            return str(_TENS[tens] + _ORD[unit])
    return w


def _roman(text: str) -> str:
    """"Article I" / "Amendment XIX" -> "Article 1" / "Amendment 19", only right after those words."""
    val = {"i": 1, "v": 5, "x": 10, "l": 50}

    def one(m):
        r, n = m.group(2).lower(), 0
        for k, a in enumerate(r):
            n += -val[a] if k + 1 < len(r) and val[r[k + 1]] > val[a] else val[a]
        return f"{m.group(1)} {n}"
    return re.sub(r"\b(article|amendment|section|title)\s+([ivxl]+)\b", one, text or "", flags=re.I)


def word_grade(answer: str, reference: str) -> dict:
    """Share of the reference answer's key words that appear in the Soldier's answer."""
    keys = list(dict.fromkeys(_num(k) for k in keywords(_roman(reference))))
    said = {_num(w) for w in _words(_roman(answer))}
    hit = [k for k in keys if k in said or k.rstrip("s") in said or k + "s" in said]
    score = len(hit) / len(keys) if keys else 0.0
    return {"verdict": "go" if score >= 0.6 else "partial" if score >= 0.3 else "nogo",
            "score": round(score, 2), "missing": [k for k in keys if k not in hit], "how": "words"}


_JUDGE = ("You grade answers at a practice board for a JROTC Cadet studying military knowledge. Compare the Cadet's answer with "
          "the reference answer. The answer is correct if it has the same meaning, even in different words. Reply "
          "with JSON only: {\"verdict\": \"go\" | \"partial\" | \"nogo\", \"why\": \"one short sentence\"}.")


_YESNO = re.compile(r"^\s*(yes|no)\b", re.I)


def quiz_grade(question: str, reference: str, answer: str, use_ai: bool = True) -> dict:
    """A Cadet's typed answer to a study-card quiz question, graded on the device -- never self-reported.
    {"verdict": "right" | "close" | "wrong", "correct": bool, "why": str}. Only "right" counts as right."""
    answer = (answer or "").strip()[:1000]
    if not answer:
        return {"verdict": "wrong", "correct": False, "why": "No answer given."}
    ref_yn, ans_yn = _YESNO.match(reference), _YESNO.match(answer)
    if ref_yn:                                       # "No — the AFT has no sit-up event...": the yes/no decides
        ok = bool(ans_yn) and ans_yn.group(1).lower() == ref_yn.group(1).lower()
        return {"verdict": "right" if ok else "wrong", "correct": ok, "how": "yes/no",
                "why": "" if ok else f"The answer starts with \"{ref_yn.group(1).capitalize()}\"."}
    head = re.split(r"\s[—–-]\s|;", reference, maxsplit=1)[0]        # "Three — legislative, ..." -> "Three"
    if not keywords(_roman(head)):                   # too short for key words ("S" for Sierra): must match exactly
        said, want = ([_num(w) for w in _words(_roman(t))] for t in (answer, head))
        ok = said == want or (want == ["you"] and said in (["me"], ["myself"], ["i"], ["i", "am"], ["yourself"])) \
            or bool(keywords(reference)) and word_grade(answer, reference)["verdict"] == "go"
        return {"verdict": "right" if ok else "wrong", "correct": ok, "how": "exact", "why": ""}
    asked = set(_words(question))                    # "Which amendment...?" -> "19th" is enough for "The 19th Amendment"
    core = " ".join(w for w in _words(_roman(head)) if w not in asked)
    words = max((word_grade(answer, r) for r in {reference, head, core} if keywords(r)), key=lambda g: g["score"],
                default={"score": 0.0, "verdict": "nogo"})
    verdict = {"go": "right", "partial": "close", "nogo": "wrong"}[words["verdict"]]
    if keywords(core) and core != head and word_grade(answer, core)["score"] == 0 \
            and word_grade(answer, reference)["verdict"] != "go":   # the full answer in other words still counts
        verdict = "wrong"                            # "the 26th amendment" for "The 19th Amendment": the key part is wrong
    out = {"verdict": verdict, "correct": verdict == "right", "how": "words", "why": ""}
    if use_ai and verdict != "right":                # the offline AI may recognize the same meaning in other words
        g = grade(question, reference, answer)
        if g.get("how") == "ai":
            v = {"go": "right", "partial": "close", "nogo": "wrong"}.get(g.get("verdict"), verdict)
            out = {"verdict": v, "correct": v == "right", "how": "ai", "why": g.get("why", "")}
    return out


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
