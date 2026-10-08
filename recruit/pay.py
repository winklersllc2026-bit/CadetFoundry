"""
Monthly pay estimate from the official DFAS tables (recruit/data/pay_tables.json, built by tools/pay_tables.py).

Basic pay is looked up by grade and cumulative years of service ("2 or less", "Over 2", ... "Over 40").
BAS comes from the same tables. BAH depends on duty location and dependents, so the Soldier enters it
(from their LES or the DoD BAH calculator). Nothing here is taxed or rounded the way DFAS does --
it's an estimate to plan with; the LES is the real number.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

TABLES = Path(__file__).resolve().parent / "data" / "pay_tables.json"


@lru_cache(maxsize=1)
def tables() -> dict:
    try:
        return json.loads(TABLES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def grades() -> list[str]:
    order = {"E": 0, "W": 1, "O": 2}
    return sorted(tables().get("basic", {}), key=lambda g: (order.get(g[0], 3), g.endswith("E"), int(g[2:].rstrip("E"))))


def basic_pay(grade: str, years: float, months: int | None = None) -> float:
    row = tables().get("basic", {}).get(grade)
    if not row:
        raise ValueError(f"{grade} isn't in the pay tables.")
    if grade == "E-1" and months is not None and months < 4 and "E-1_under_4_months" in tables().get("notes", {}):
        return tables()["notes"]["E-1_under_4_months"]
    over = [int(y) for y in row]                       # 0 = "2 or less", N = "Over N"
    col = max((y for y in over if y == 0 or years > y), default=None)
    if col is None:                                     # e.g. E-9 with under 10 years: not on the table
        raise ValueError(f"The table has no {grade} pay for {years:g} years of service.")
    return row[str(col)]


def estimate(grade: str, years: float, months: int | None = None, bah: float = 0.0) -> dict:
    t = tables()
    base = basic_pay(grade, years, months)
    bas = (t.get("bas") or {}).get("officer" if grade[0] in "OW" else "enlisted") or 0.0
    bah = max(0.0, float(bah or 0))
    return {
        "grade": grade, "years": years, "basic": round(base, 2), "bas": round(bas, 2), "bah": round(bah, 2),
        "total": round(base + bas + bah, 2),
        "basic_effective": t.get("effective", {}).get(grade, ""),
        "bas_effective": (t.get("bas") or {}).get("effective", ""),
        "source": t.get("source", ""),
    }


LES = Path(__file__).resolve().parent / "data" / "les_fields.json"


@lru_cache(maxsize=1)
def les_fields() -> dict:
    """The 78 numbered blocks of the LES, in DFAS's words (built by tools/les_fields.py)."""
    try:
        return json.loads(LES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"fields": [], "sections": []}


_RANKS = {"pv1": "E-1", "private": "E-1", "pv2": "E-2", "private second class": "E-2", "pfc": "E-3",
          "private first class": "E-3", "spc": "E-4", "specialist": "E-4", "cpl": "E-4", "corporal": "E-4",
          "sgt": "E-5", "sergeant": "E-5", "ssg": "E-6", "staff sergeant": "E-6", "sfc": "E-7",
          "sergeant first class": "E-7", "msg": "E-8", "master sergeant": "E-8", "1sg": "E-8", "first sergeant": "E-8",
          "sgm": "E-9", "sergeant major": "E-9", "csm": "E-9", "command sergeant major": "E-9",
          "2lt": "O-1", "second lieutenant": "O-1", "1lt": "O-2", "first lieutenant": "O-2", "cpt": "O-3",
          "captain": "O-3", "maj": "O-4", "major": "O-4", "ltc": "O-5", "lieutenant colonel": "O-5",
          "col": "O-6", "colonel": "O-6"}
_PAY_WORDS = re.compile(r"\b(pay|paid|make|makes|making|earn|earns|salary|income|money|base pay|basic pay)\b", re.I)


def pay_answer(question: str) -> dict | None:
    """'What does an E-4 with 3 years make?' -> the exact 2026 table numbers, as a checked answer.
    Only for questions about pay that name a grade or rank; anything else returns None."""
    q = question.lower()
    if not _PAY_WORDS.search(q) or "bah" in q and "basic" not in q:
        return None
    m = re.search(r"\b([ewo])\s*-?\s*(\d{1,2})(e)?\b", q)
    grade = f"{m.group(1).upper()}-{int(m.group(2))}{'E' if m.group(3) else ''}" if m else None
    if not grade:
        for name in sorted(_RANKS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(name)}\b", q):
                grade = _RANKS[name]
                break
    if not grade or grade not in tables().get("basic", {}):
        return None
    y = re.search(r"(\d+(?:\.\d+)?)\s*(?:\+\s*)?(years?|yrs?|yos|months?)\b", q)
    years = (float(y.group(1)) / 12 if y.group(2).startswith("month") else float(y.group(1))) if y else 0.0
    try:
        e = estimate(grade, years, round(years * 12) if y and y.group(2).startswith("month") else None)
    except ValueError as err:
        return {"answer": str(err), "source": tables().get("source", "DFAS pay tables")}
    served = f"with {y.group(1)} {y.group(2)} of service" if y else "with 2 years of service or less"
    answer = (f"An {grade} {served} gets **${e['basic']:,.2f} a month** basic pay (effective {e['basic_effective']}), "
              f"plus **${e['bas']:,.2f}** BAS for food = **${e['total']:,.2f}** a month before taxes. "
              f"BAH (housing) depends on where you're stationed and dependents -- check your LES. "
              f"Pay rises with years of service inside the same grade; a new grade only comes with a promotion.")
    return {"answer": answer, "source": tables().get("source", "DFAS pay tables")}
