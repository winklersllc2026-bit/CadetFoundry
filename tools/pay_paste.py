"""
Update recruit/data/pay_tables.json from DFAS pay tables copied out of a browser.

DFAS blocks scripts, but copying the page works: open the table on dfas.mil,
select all, copy, paste into a text file, then

    python tools/pay_paste.py pasted.txt [more.txt ...]

Works for Basic Pay (enlisted, warrant officer, officer) and the BAS page.
Each grade keeps the "Effective ..." date printed above its table.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "recruit" / "data" / "pay_tables.json"

GRADE = re.compile(r"^\s*([EWO]-\d{1,2}E?)\b", re.M)
MONEY = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")


def _columns(header: str) -> list[int]:
    cols = [0] if re.search(r"2\s+or\s+less", header, re.I) else []
    return cols + [int(n) for n in re.findall(r"Over\s+(\d+)", header, re.I)]


def parse_basic(text: str) -> tuple[dict, dict, dict]:
    """-> ({grade: {years: pay}}, {grade: effective}, notes)"""
    basic: dict[str, dict[str, float]] = {}
    effective: dict[str, str] = {}
    eff = ""
    # each table starts at "Pay Grade"; the effective date is in the title above it
    for part in re.split(r"(?=Pay Grade)", text):
        m = re.search(r"Effective\s+([A-Z][a-z]+ \d{1,2}, \d{4})", part)
        if m:
            eff = m.group(1)
        if not part.startswith("Pay Grade"):
            continue
        first = GRADE.search(part)
        if not first:
            continue
        cols = _columns(part[:first.start()])
        rows = list(GRADE.finditer(part))
        for i, g in enumerate(rows):
            end = rows[i + 1].start() if i + 1 < len(rows) else len(part)
            body = part[g.end():end].split("NOTES")[0]
            body = re.sub(r"\(Notes?[^)]*\)", " ", body)
            vals = [float(v.replace(",", "")) for v in MONEY.findall(body)]
            if not vals or len(vals) > len(cols):
                continue
            # blank cells are always on the left (e.g. E-9 under 10 years), so right-align
            row = basic.setdefault(g.group(1), {})
            for y, v in zip(cols[len(cols) - len(vals):], vals):
                row[str(y)] = v
            if eff:
                effective[g.group(1)] = eff
    notes = {}
    m = re.search(r"less than 4 months of active duty is \$(" + MONEY.pattern + ")", text)
    if m:
        notes["E-1_under_4_months"] = float(m.group(1).replace(",", ""))
    return basic, effective, notes


def parse_bas(text: str) -> dict:
    if not re.search(r"Basic Allowance for Subsistence|\bBAS\b", text):
        return {}
    # the DFAS page is a history: "January 1, 2026  $328.48  $476.95  $953.90" (officers, enlisted, BAS II)
    rows = re.findall(r"^\s*([A-Z][a-z]+)\s?(\d{1,2}), (\d{4})[^$\n]*\$(" + MONEY.pattern + r")\s+\$(" + MONEY.pattern + ")",
                      text, re.M)
    if not rows:
        return {}
    month, day, year, officer, enlisted = max(rows, key=lambda r: int(r[2]))
    return {"effective": f"{month} {day}, {year}", "officer": float(officer.replace(",", "")),
            "enlisted": float(enlisted.replace(",", ""))}


def main(paths: list[str]) -> None:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    for p in paths:
        text = Path(p).read_text(encoding="utf-8")
        basic, effective, notes = parse_basic(text)
        if basic:
            for g, row in basic.items():
                data["basic"][g] = dict(sorted(row.items(), key=lambda kv: int(kv[0])))
            data["effective"].update(effective)
            data["notes"].update(notes)
            print(f"{p}: {len(basic)} grades ({', '.join(basic)}), effective {sorted(set(effective.values()))}")
        else:
            bas = parse_bas(text)
            if bas:
                data["bas"] = {**data.get("bas", {}), **bas}
                print(f"{p}: BAS {bas}")
            else:
                print(f"{p}: no pay table found")
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"saved {OUT}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
