"""
Build cadetfoundry/data/les_fields.json (the LES decoder) from DFAS's own guides:

    tools/pay_source/DFAS_Army_reading_your_LES.txt    (active duty)
    tools/pay_source/DFAS_ResNG_reading_your_LES.txt   (Reserve and National Guard)

Copied from dfas.mil > Military Members > Pay & Entitlements > About Pay.
Each block keeps DFAS's wording; Cadet Foundry's own notes are kept separate and labeled.

    python tools/les_fields.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "pay_source"
OUT = ROOT / "cadetfoundry" / "data" / "les_fields.json"

SECTIONS = [  # (first block, last block, name)
    (1, 9, "Identification"), (10, 24, "Pay summary"), (25, 32, "Leave"), (33, 38, "Federal taxes"),
    (39, 43, "FICA (Social Security and Medicare)"), (44, 49, "State taxes"), (50, 62, "Pay data"),
    (63, 75, "Thrift Savings Plan (TSP)"), (76, 78, "Remarks and year to date"),
]

# Cadet Foundry's notes -- not DFAS text, shown under the DFAS explanation and labeled as Cadet Foundry's.
NOTES = {
    2: "Your LES shows your Social Security Number. Don't post, text or share a photo of it.",
    23: "DFAS's guide was written before the Blended Retirement System. Soldiers who entered service on or after "
        "January 1, 2018 are under BRS (Summary of the Thrift Savings Plan, TSPBK08) — see the TSP calculator.",
    24: "DFAS's guide was written before the Blended Retirement System; newer Soldiers will see BRS here.",
    26: "Track your own leave in Cadet Foundry's leave tracker (2.5 days a month).",
    50: "DFAS's guide still uses the older names BAQ and VHA. They were replaced by BAH (Basic Allowance for Housing); "
        "blocks 50 to 58 hold your housing allowance information.",
    52: "VHA is an older name — today this is your BAH (housing allowance) information.",
    55: "VHA is an older name — today this is your BAH (housing allowance) information.",
    63: "The TSP calculator in Cadet Foundry shows how your contribution percentage adds up with the BRS match.",
}

LINE = re.compile(r"^(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s+(.+?):\s*(.*)$")


def parse(path: Path) -> dict[int, tuple[str, str]]:
    out: dict[int, tuple[str, str]] = {}
    text = path.read_text(encoding="utf-8")
    for q, r in (("’", "'"), ("“", '"'), ("”", '"')):   # curly quotes differ between the two guides
        text = text.replace(q, r)
    for raw in text.splitlines():
        m = LINE.match(raw.strip())
        if not m:
            continue
        first, last = int(m.group(1)), int(m.group(2) or m.group(1))
        label = re.sub(r"^[+\-=]\s*", "", m.group(3)).strip()
        for n in range(first, last + 1):
            out[n] = (label, m.group(4).strip())
    missing = [n for n in range(1, 79) if n not in out]
    if missing:
        raise SystemExit(f"{path.name}: blocks missing {missing}")
    return out


def main() -> None:
    active = parse(SRC / "DFAS_Army_reading_your_LES.txt")
    reserve = parse(SRC / "DFAS_ResNG_reading_your_LES.txt")
    fields = []
    for n in range(1, 79):
        section = next(name for a, b, name in SECTIONS if a <= n <= b)
        f = {"n": n, "label": active[n][0], "section": section, "active": active[n][1]}
        if reserve[n][1] != active[n][1]:
            f["reserve"] = reserve[n][1]
        if n in NOTES:
            f["note"] = NOTES[n]
        fields.append(f)
    data = {"source": "DFAS, How to read an active duty Army LES / How to read a Reserve and National Guard LES "
                      "(dfas.mil, Pay & Entitlements > About Pay), DFAS Form 702",
            "sections": [{"from": a, "to": b, "name": name} for a, b, name in SECTIONS],
            "fields": fields}
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {OUT.name}: {len(fields)} blocks, {sum('reserve' in f for f in fields)} differ for Reserve/Guard")


if __name__ == "__main__":
    main()
