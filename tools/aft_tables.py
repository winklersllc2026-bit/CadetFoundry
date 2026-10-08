"""
Build recruit/data/aft_tables.json from the official Army Fitness Test score tables.

    python tools/aft_tables.py AFT_Scoring_Scales_250601.pdf

The PDF is published at army.mil (www.army.mil/e2/downloads/rv7/aft/), which blocks
automated downloads -- save it from a browser. Needs `pdftotext` (poppler) on the
setup machine only; Recruit itself reads the small JSON this writes.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "recruit" / "data" / "aft_tables.json"

AGES = ["17-21", "22-26", "27-31", "32-36", "37-41", "42-46", "47-51", "52-56", "57-61", "62+"]
# id, heading text in the PDF, unit, higher_is_better
EVENTS = [
    ("MDL", "Max Deadlift", "lbs", True),
    ("HRP", "Hand-release Push-up", "reps", True),
    ("SDC", "Sprint / Drag / Carry", "time", False),
    ("PLK", "Plank", "time", True),
    ("2MR", "Two-Mile Run", "time", False),
]


def secs(v: str) -> int:
    m, s = v.split(":")
    return int(m) * 60 + int(s)


def parse(text: str) -> dict:
    tables: dict = {e[0]: {} for e in EVENTS}
    current = None
    for line in text.splitlines():
        for eid, head, _unit, _hib in EVENTS:
            if head in line and "Score Tables" not in line:
                current = eid
        if "Alternate Events" in line:
            current = None
        tok = line.split()
        if current and len(tok) == 22 and tok[0].isdigit() and tok[0] == tok[-1]:
            unit = next(e[2] for e in EVENTS if e[0] == current)
            vals = [None if v == "---" else (secs(v) if unit == "time" else int(v)) for v in tok[1:21]]
            tables[current][int(tok[0])] = vals
    return tables


def check(tables: dict) -> None:
    for eid, _head, _unit, hib in EVENTS:
        rows = tables[eid]
        if 100 not in rows or 0 not in rows or 60 not in rows:
            raise SystemExit(f"{eid}: missing the 100, 60 or 0 row")
        for col in range(20):
            seq = [rows[p][col] for p in sorted(rows, reverse=True) if rows[p][col] is not None]
            ok = all(a >= b for a, b in zip(seq, seq[1:])) if hib else all(a <= b for a, b in zip(seq, seq[1:]))
            if not ok:
                raise SystemExit(f"{eid}: column {col} isn't in order -- the PDF didn't parse cleanly")


def main(argv: list[str]) -> int:
    pdf = Path(argv[0])
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    approved = re.search(r"Approved:\s*([^E]+?)\s+Effective:\s*(.+)", text)
    tables = parse(text)
    check(tables)
    data = {
        "title": "Army Fitness Test Score Tables",
        "approved": approved.group(1).strip() if approved else "",
        "effective": approved.group(2).strip() if approved else "",
        "source": "U.S. Army, AFT Scoring Scales (army.mil/e2/downloads/rv7/aft/AFT_Scoring_Scales_250601.pdf)",
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "ages": AGES,
        "columns": "for each age group: [M|C, F] -- M|C is the male column, also used for the combat standard",
        "events": {eid: {"name": head, "unit": unit, "higher_is_better": hib,
                         "rows": {str(p): tables[eid][p] for p in sorted(tables[eid], reverse=True)}}
                   for eid, head, unit, hib in EVENTS},
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} -- " + ", ".join(f"{e}: {len(tables[e])} rows" for e in tables))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
