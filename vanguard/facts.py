"""
Answers Cadet Foundry gives straight from its own data -- the DFAS pay tables, the AFT score tables, the DFAS LES guide
and the Army job list -- so a number or a job description never depends on a small AI model restating it.

Each answer is {"question", "answer", "source"}; "final": True means the answer is complete and no AI text follows
(a pay grade that doesn't exist, a manual Cadet Foundry doesn't have).
"""
from __future__ import annotations

import re
from pathlib import Path

from vanguard import careers, fitness, pay


def _mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


# ── Army Fitness Test ────────────────────────────────────────────────────────
_EVENTS = [("MDL", r"dead ?lift|\bmdl\b"), ("HRP", r"push[- ]?ups?|\bhrp\b"), ("SDC", r"sprint|drag|carry|\bsdc\b"),
           ("PLK", r"plank"), ("2MR", r"\brun\b|two[- ]mile|\b2[- ]?mile|\b2mr\b")]


def _need(event: str, points: int, col: int) -> int | None:
    """What it takes to score at least `points`: the first published row at or above it ('---' rows skipped)."""
    rows = fitness.tables()["events"][event]["rows"]
    for p in range(points, 101):
        cell = rows.get(str(p), [None] * 20)[col]
        if cell is not None:
            return cell
    return None


def aft_answer(question: str) -> dict | None:
    """'What's the AFT run time for a 20-year-old male to get 100 points?' -> the score table's numbers."""
    q = question.lower()
    if not re.search(r"\b(aft|fitness test|points?|score)\b", q):
        return None
    event = next((e for e, pat in _EVENTS if re.search(pat, q)), None)
    if not event or not re.search(r"\b(points?|score|need|minimum|min|max|pass|time|standard|how (many|much|fast|long|heavy))\b", q):
        return None
    t = fitness.tables()
    ev = t["events"][event]
    pts = re.search(r"\b(100|[1-9]\d)\s*(?:points?|pts)\b", q)
    wanted = [int(pts.group(1))] if pts else [60, 100]
    age_m = (re.search(r"\b(1[7-9]|[2-9]\d)[- ]?(?:years?|yrs?)?[- ]?old\b", q) or re.search(r"\bage\s*(1[7-9]|[2-9]\d)\b", q)
             or re.search(r"\b(1[7-9]|[2-9]\d)\s*(?:yo|y/o)\b", q))
    age = int(age_m.group(1)) if age_m else 18
    group = t["ages"][fitness.age_index(age)]
    female = bool(re.search(r"\b(female|woman|women|girl|she|her)\b", q))
    male = bool(re.search(r"\b(male|man|men|guy|he|his)\b", q))
    combat = "combat" in q
    unit = ev["unit"]

    def show(v: int) -> str:
        if unit == "time":
            return _mmss(v) + (" or faster" if not ev["higher_is_better"] else " or longer")
        return f"{v} {'lbs' if unit == 'lbs' else 'reps'} or more"

    lines = []
    for p in wanted:
        cols = []
        if combat or male or not female:
            cols.append(("combat standard (sex-neutral)" if combat else "male", fitness.age_index(age) * 2))
        if female and not combat or not (male or female or combat):
            cols.append(("female", fitness.age_index(age) * 2 + 1))
        parts = [f"{name} **{show(v)}**" for name, c in cols for v in [_need(event, p, c)] if v is not None]
        lines.append(f"- **{p} points:** " + ("; ".join(parts) if parts else "not on the table for this group"))
    who = f"age {group}" + ("" if age_m else " (tell me your age for your own column)")
    answer = (f"**{ev['name']}, {who}** — from the official AFT score tables:\n" + "\n".join(lines) +
              f"\n\nTo pass: at least **{fitness.MIN_EVENT} points in every event**, and **{fitness.MIN_TOTAL['combat']}** total "
              f"for combat specialties or **{fitness.MIN_TOTAL['general']}** for everyone else. "
              "The Log tab's AFT scorer scores a whole test.")
    return {"question": question, "answer": answer, "source": f"AFT Scoring Scales (effective {t['effective']})"}


# ── Pay ──────────────────────────────────────────────────────────────────────
def pay_facts(question: str) -> dict | None:
    q = question.lower()
    src = pay.tables().get("source", "DFAS pay tables")
    if re.search(r"\bbas\b|basic allowance for subsistence|subsistence allowance", q):
        b = pay.tables().get("bas") or {}
        return {"question": question, "source": src,
                "answer": (f"BAS (Basic Allowance for Subsistence, money for food) is a flat monthly rate, effective "
                           f"{b.get('effective', '')}: **${b.get('enlisted', 0):,.2f}** for enlisted Soldiers and "
                           f"**${b.get('officer', 0):,.2f}** for officers. It doesn't depend on rank or location. "
                           "Soldiers who eat in the dining facility may have meal costs taken back out — your LES shows it.")}
    m = re.search(r"\b([ewo])\s*-?\s*(\d{1,2})\b", q)
    if m and pay._PAY_WORDS.search(q):
        grade = f"{m.group(1).upper()}-{int(m.group(2))}"
        if grade not in pay.tables().get("basic", {}) and grade + "E" not in pay.tables().get("basic", {}):
            return {"question": question, "source": src, "final": True,
                    "answer": (f"There's no {grade} pay grade. Enlisted grades run **E-1 to E-9**, warrant officers "
                               "**W-1 to W-5**, and officers **O-1 to O-10**.")}
    a = pay.pay_answer(question)
    return {"question": question, **a} if a else None


# ── LES ──────────────────────────────────────────────────────────────────────
def les_answer(question: str) -> dict | None:
    q = question.upper()
    if not re.search(r"\b(LES|LEAVE AND EARNINGS)\b", q):
        return None
    data = pay.les_fields()
    num = re.search(r"\b(?:BLOCK|BOX)\s*#?\s*(\d{1,2})\b", q)
    field = None
    if num:
        field = next((f for f in data["fields"] if f["n"] == int(num.group(1))), None)
    else:
        hits = [f for f in data["fields"] if len(f["label"]) >= 3 and f["label"] != "TOTAL" and f["label"] != "RESERVED"
                and re.search(rf"(?<![A-Z]){re.escape(f['label'])}(?![A-Z])", q)]
        field = max(hits, key=lambda f: len(f["label"]), default=None)
    if not field and re.search(r"\bFICA\b|\bSOC\.? ?SEC\b|SOCIAL SECURITY|\bMEDICARE\b", q):
        blocks = [f for f in data["fields"] if f["section"].startswith("FICA")]
        lines = "\n".join(f"- **Block {f['n']}, {f['label']}:** {f['active']}" for f in blocks)
        return {"question": question, "source": "DFAS, How to read an Army LES",
                "answer": ("**FICA** (Federal Insurance Contributions Act) is the Social Security and Medicare tax taken "
                           "from your pay. **FICA-SOC SEC** is the Social Security part; **FICA-MEDICARE** is the "
                           "Medicare part. Neither is federal income tax, which has its own section (Federal taxes).\n\n"
                           f"Your LES shows them in the FICA section:\n{lines}")}
    if not field:
        return None
    answer = f"**Block {field['n']}, {field['label']}** ({field['section']}): {field['active']}"
    if field.get("reserve"):
        answer += f"\n\nReserve and National Guard LES: {field['reserve']}"
    if field.get("note"):
        answer += f"\n\n{field['note']}"
    return {"question": question, "answer": answer, "source": "DFAS, How to read an Army LES"}


# ── Army jobs ────────────────────────────────────────────────────────────────
_JOB_STOP = {"what", "which", "jobs", "job", "mos", "mo", "are", "is", "like", "being", "a", "an", "the", "do", "does",
             "army", "in", "for", "me", "can", "i", "be", "similar", "to", "there", "any", "with", "work", "as", "who"}


def _clean(s: str) -> str:
    return (s or "").replace("�", "’").replace("Ã¢â‚¬â„¢", "’")


def job_answer(question: str, library_dir: Path | None) -> dict | None:
    if not library_dir:
        return None
    q = question.strip()
    code = re.search(r"\b(\d{2}[A-Z])\b", q.upper())
    src = "GoArmy.com Army job descriptions"
    if code and re.search(r"\b(what|who|tell|about|do|does|is)\b", q, re.I):
        jobs = careers.search(library_dir, code.group(1).lower(), limit=1, service="army")["jobs"]
        if jobs and jobs[0]["code"].upper() == code.group(1):
            j = jobs[0]
            return {"question": question, "source": src,
                    "answer": f"**{j['code']} {j['title']}** ({j['area']}): {_clean(j['summary'])}"}
    if re.search(r"\b(jobs?|mos)\b", q, re.I) and re.search(r"\b(like|similar|for|as|being|involve|with)\b", q, re.I):
        words = [w for w in re.findall(r"[a-z]+", q.lower()) if w not in _JOB_STOP and len(w) > 2]
        if not words:
            return None
        jobs = careers.search(library_dir, " ".join(words), limit=5, service="army")["jobs"]
        if not jobs:
            return None
        lines = "\n".join(f"- **{j['code']} {j['title']}** — {_clean(j['summary'])}" for j in jobs)
        return {"question": question, "source": src,
                "answer": f"Army jobs that match \"{' '.join(words)}\":\n{lines}\n\nThe Study tab's job explorer has all 263."}
    return None


def direct_answer(question: str, library_dir: Path | None = None) -> dict | None:
    for fn in (pay_facts, aft_answer, les_answer):
        a = fn(question)
        if a:
            return a
    return job_answer(question, library_dir)
