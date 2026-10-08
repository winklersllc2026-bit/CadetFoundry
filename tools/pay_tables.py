"""
Build vanguard/data/pay_tables.json from the official DFAS pay table pages.

    python tools/pay_tables.py EM.html WO.html BAS.html [CO.html CO_FE.html]

DFAS blocks automated downloads, so save the pages from a browser (File > Save Page As):
  https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/Basic-Pay/EM/   (enlisted)
  https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/Basic-Pay/WO/   (warrant officers)
  https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/Basic-Pay/CO/   (officers, optional)
  https://www.dfas.mil/Military-Members/payentitlements/Pay-Tables/bas/            (BAS)
Each table keeps the "Effective ..." date printed on its page, and Vanguard shows it.
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "vanguard" / "data" / "pay_tables.json"


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self.row = []
            self.tables[-1].append(self.row)
        elif tag in ("td", "th") and self.row is not None:
            self.cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r"\s+", " ", self.cell).strip())
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data


def _money(v: str) -> float | None:
    v = v.replace("$", "").replace(",", "").strip()
    try:
        x = float(v)
    except ValueError:
        return None
    return x if x > 0 else None          # "0" or blank = grade not reached at those years


def _text(raw: str) -> str:
    raw = re.sub(r"(?s)<(script|style).*?</\1>", "", raw)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", raw)))


def parse_basic(raw: str) -> tuple[dict, str, dict]:
    """-> ({grade: {years_over: monthly}}, effective date, notes)"""
    p = _Tables()
    p.feed(raw)
    grades: dict[str, dict[int, float]] = {}
    for table in p.tables:
        head = next((r for r in table if r and r[0].lower().startswith("pay grade")), None)
        if not head:
            continue
        years = [0 if h.lower().startswith("2 or less") else int(re.sub(r"\D", "", h)) for h in head[1:]]
        for row in table:
            m = re.match(r"([EWO]-\d+E?)", row[0]) if row else None
            if not m:
                continue
            for y, v in zip(years, row[1:]):
                amount = _money(v)
                if amount:
                    grades.setdefault(m.group(1), {})[y] = amount
    text = _text(raw)
    eff = re.search(r"Effective ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    notes = {}
    e1 = re.search(r"E-1 with less than 4 months of active duty is \$([\d,]+\.\d\d)", text)
    if e1:
        notes["E-1_under_4_months"] = float(e1.group(1).replace(",", ""))
    return grades, (eff.group(1) if eff else ""), notes


def parse_bas(raw: str) -> dict:
    p = _Tables()
    p.feed(raw)
    for table in p.tables:
        head = [h.upper() for h in table[0]] if table else []
        if "OFFICERS" in head and "ENLISTED" in head:
            row = table[1]                     # newest year first
            return {"effective": row[0], "officer": _money(row[head.index("OFFICERS")]),
                    "enlisted": _money(row[head.index("ENLISTED")])}
    raise SystemExit("couldn't find the BAS table")


def main(paths: list[str]) -> int:
    data = {"source": "DFAS pay tables (dfas.mil, Military Members > Pay Tables)", "basic": {}, "effective": {},
            "notes": {}, "bas": None}
    for path in paths:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
        if "Basic Allowance for Subsistence" in raw and "ENLISTED" in raw.upper():
            data["bas"] = parse_bas(raw)
            continue
        grades, eff, notes = parse_basic(raw)
        if not grades:
            print(f"skipped {path}: no basic pay table found")
            continue
        for g, row in grades.items():
            data["basic"][g] = {str(y): v for y, v in sorted(row.items())}
            data["effective"][g] = eff
        data["notes"].update(notes)
    for g in ("E-1", "E-4", "E-9"):
        if data["basic"] and g in data["basic"]:
            vals = list(data["basic"][g].values())
            if vals != sorted(vals):
                raise SystemExit(f"{g}: pay doesn't rise with years -- the page didn't parse cleanly")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=0), encoding="utf-8")
    print(f"wrote {OUT}: {len(data['basic'])} grades; BAS {data['bas']['effective'] if data['bas'] else 'missing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
