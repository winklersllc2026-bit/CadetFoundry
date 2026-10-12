"""
Install the optional faith library (needs internet once; afterwards fully offline).

    python tools/fetch_faith.py            install everything below
    python tools/fetch_faith.py kjv quran  install only some (by id)
    python tools/fetch_faith.py --list     show what's available

Every text here is in the public domain in the United States. Sources:
  * Bibles + JPS Tanakh: eBible.org verse-per-line files (public domain editions)
  * Quran (Pickthall, 1930): Tanzil.net plain-text translation file
  * Book of Mormon, Bhagavad Gita (Arnold), Dhammapada (Müller), Tao Te Ching (Legge): Project Gutenberg
    (Project Gutenberg's header/footer and trademark are removed; only the public-domain text is kept).

Output: faith/<id>.tsv (book, chapter, verse, text) and faith/catalog.json.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "faith"
sys.path.insert(0, str(ROOT))
from cadetfoundry.faith import BOOKS  # noqa: E402

UA = {"User-Agent": "Cadet Foundry faith installer"}

CATALOG = [
    # id, name, tradition, kind, source
    ("kjv", "King James Version (1769)", "Christian — Protestant", "ebible", "eng-kjv2006"),
    ("asv", "American Standard Version (1901)", "Christian — Protestant", "ebible", "eng-asv"),
    ("web", "World English Bible", "Christian — Protestant", "ebible", "engwebp"),
    ("ylt", "Young's Literal Translation", "Christian — Protestant", "ebible", "engylt"),
    ("dra", "Douay-Rheims (Challoner)", "Christian — Catholic", "ebible", "engDRA"),
    ("brenton", "Brenton Septuagint (Old Testament)", "Christian — Orthodox", "ebible", "eng-Brenton"),
    ("jps", "JPS Tanakh (1917)", "Jewish", "ebible", "engjps"),
    ("quran", "The Quran — Pickthall translation (1930)", "Muslim", "tanzil", "en.pickthall"),
    ("bom", "The Book of Mormon", "Latter-day Saint", "gutenberg_bom", "17"),
    ("gita", "Bhagavad Gita — Arnold, The Song Celestial (1885)", "Hindu", "gutenberg_gita", "2388"),
    ("dhammapada", "Dhammapada — Müller (1881)", "Buddhist", "gutenberg_dhp", "2017"),
    ("tao", "Tao Te Ching — Legge (1891)", "Taoist", "gutenberg_tao", "216"),
]


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _clean(t: str) -> str:
    # drop print-edition marks: ¶ paragraph signs, and the KJV's [brackets] around words printed in italics
    t = t.replace("¶", "").replace("[", "").replace("]", "").replace("\t", " ")
    return re.sub(r"\s+", " ", t).strip()


# eBible.org's verse files use BibleWorks-style codes for some books; map them to standard USFM.
EBIBLE_CODES = {"SOL": "SNG", "EZE": "EZK", "JOE": "JOL", "NAH": "NAM", "MAR": "MRK", "JOH": "JHN",
                "PHI": "PHP", "JAM": "JAS", "1JO": "1JN", "2JO": "2JN", "3JO": "3JN"}


def ebible(src: str) -> list[tuple]:
    z = zipfile.ZipFile(io.BytesIO(_get(f"https://ebible.org/Scriptures/{src}_vpl.zip")))
    name = next(n for n in z.namelist() if n.endswith("_vpl.txt"))
    rows = []
    for line in _decode(z.read(name)).splitlines():
        m = re.match(r"^([1-4A-Z][A-Z0-9]{2})\s+(\d+):(\d+)\s+(.*)$", line.strip())
        if m and m.group(4).strip():
            rows.append((EBIBLE_CODES.get(m.group(1), m.group(1)), int(m.group(2)), int(m.group(3)), _clean(m.group(4))))
    return rows


def tanzil(src: str) -> list[tuple]:
    raw = _decode(_get(f"https://tanzil.net/trans/?transID={src}&type=txt-2"))
    rows = []
    for line in raw.splitlines():
        p = line.split("|", 2)
        if len(p) == 3 and p[0].isdigit() and p[1].isdigit():
            rows.append(("QUR", int(p[0]), int(p[1]), _clean(p[2])))
    return rows


def _gutenberg(num: str) -> str:
    raw = _decode(_get(f"https://www.gutenberg.org/cache/epub/{num}/pg{num}.txt")).replace("\r\n", "\n")
    start = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\n", raw)
    end = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK", raw)
    return raw[start.end() if start else 0: end.start() if end else len(raw)]


BOM_ORDER = ["1NE", "2NE", "JAC", "ENO", "JAR", "OMN", "WOM", "MOS", "ALM", "HEL", "3NE", "4NE", "MRM", "ETH", "MRO"]


def gutenberg_bom(num: str) -> list[tuple]:
    text = _gutenberg(num)
    rows, book_i, cur = [], -1, None
    for para in re.split(r"\n\s*\n", text):
        m = re.match(r"^(?:4 Nephi\s+)?(\d+):(\d+)\s+(.*)$", para.strip(), re.S)   # 4 Nephi opens "4 Nephi 1:1"
        if not m:
            continue
        ch, v = int(m.group(1)), int(m.group(2))
        if ch == 1 and v == 1:
            book_i += 1
        if 0 <= book_i < len(BOM_ORDER):
            rows.append((BOM_ORDER[book_i], ch, v, _clean(m.group(3))))
    if book_i + 1 != len(BOM_ORDER):
        raise RuntimeError(f"expected {len(BOM_ORDER)} books, found {book_i + 1}")
    return rows


def _roman(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total, prev = 0, 0
    for c in reversed(s.upper()):
        v = vals[c]
        total, prev = (total - v, prev) if v < prev else (total + v, v)
    return total


def gutenberg_gita(num: str) -> list[tuple]:
    text = _gutenberg(num)
    parts = re.split(r"\n\s*CHAPTER ([IVXL]+)\s*\n", text)
    rows = []
    for i in range(1, len(parts) - 1, 2):
        ch = _roman(parts[i])
        body = parts[i + 1]
        body = re.split(r"\n\s*(HERE ENDETH|FOOTNOTES|\[FN)", body)[0]
        paras = [_clean(p) for p in re.split(r"\n\s*\n", body) if _clean(p)]
        for p in paras:
            rows.append(("GIT", ch, 0, p))
    if len({r[1] for r in rows}) != 18:
        raise RuntimeError(f"expected 18 chapters, found {len({r[1] for r in rows})}")
    return rows


def gutenberg_dhp(num: str) -> list[tuple]:
    text = _gutenberg(num)
    rows, ch = [], 0
    cur_v, cur, last_v, pairs = None, [], 0, []

    def flush():
        if cur_v is not None and cur:
            rows.append(("DHP", ch, cur_v, _clean(" ".join(cur))))

    for line in text.split("\n"):
        h = re.match(r"^\s*Chapter ([IVXL]+)\.", line)
        if h:
            flush(); cur_v, cur = None, []
            ch = _roman(h.group(1))
            continue
        # verses are numbered straight through (1-423); some come in pairs: "58, 59. As on a heap..."
        m = re.match(r"^\s*(\d{1,3})(?:\s*,\s*(\d{1,3}))?\.\s+(.*)$", line)
        if m and ch and int(m.group(1)) == last_v + 1:
            flush()
            cur_v, cur = int(m.group(1)), [m.group(3)]
            last_v = int(m.group(2)) if m.group(2) else cur_v
            if m.group(2):
                pairs.append((cur_v, last_v))
        elif cur_v is not None and line.strip():
            cur.append(line.strip())
    flush()
    for a, b in pairs:                                  # paired verses can be found under both numbers
        src = next(r for r in rows if r[2] == a)
        rows.append(("DHP", src[1], b, f"[{a}-{b}] " + src[3]))
    vs = {r[2] for r in rows}
    if len(vs) < 420:
        raise RuntimeError(f"expected 423 verses, found {len(vs)}")
    return rows


def gutenberg_tao(num: str) -> list[tuple]:
    """Legge's chapters begin either "N. 1. text..." on one line ("Ch. 1. 1." for the
    first) or a bare "N." line whose next non-empty line starts with "1.". Paragraph
    numbers "2.", "3."... inside a chapter are dropped."""
    text = _gutenberg(num).replace("Ch. 1. 1. ", "1. 1. ", 1)
    lines = text.split("\n")
    starts, ch, para = [], 0, 0                         # (line index, chapter, text after the numbers)
    for i, l in enumerate(lines):
        inline = re.match(r"^\s*(\d{1,2})\.\s+1\.(?:\s+(.*))?$", l)
        num = re.match(r"^\s*(\d{1,2})\.(?:\s+(.*))?$", l)
        if inline and int(inline.group(1)) == ch + 1:
            ch, para = ch + 1, 1                        # "N. 1. text" -- chapter N, paragraph 1
            starts.append((i, ch, inline.group(2) or ""))
        elif num:
            n = int(num.group(1))
            if n == para + 1 and para > 0:              # next paragraph of the current chapter
                para = n
            elif n == ch + 1:                           # "N." or "N. text" -- a chapter without numbered paragraphs
                ch, para = n, 0
                starts.append((i, ch, num.group(2) or ""))
            elif n == para + 1:
                para = n
    rows = []
    for k, (i, n, first) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        body = first + "\n" + "\n".join(lines[i + 1:end])
        body = re.sub(r"(?m)^\s*\d{1,2}\.(\s|$)", " ", body)          # paragraph numbers
        rows.append(("TAO", n, 0, _clean(body)))
    if len({r[1] for r in rows}) != 81:
        raise RuntimeError(f"expected 81 chapters, found {len({r[1] for r in rows})}")
    return rows


KINDS = {"ebible": ebible, "tanzil": tanzil, "gutenberg_bom": gutenberg_bom, "gutenberg_gita": gutenberg_gita,
         "gutenberg_dhp": gutenberg_dhp, "gutenberg_tao": gutenberg_tao}


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for tid, name, trad, *_ in CATALOG:
            print(f"{tid:11} {name}  [{trad}]")
        return 0
    wanted = [a for a in argv if not a.startswith("-")]
    OUT.mkdir(exist_ok=True)
    try:
        catalog = json.loads((OUT / "catalog.json").read_text(encoding="utf-8"))
    except Exception:
        catalog = []
    by_id = {c["id"]: c for c in catalog}
    failed = []
    for tid, name, trad, kind, src in CATALOG:
        if wanted and tid not in wanted:
            continue
        print(f"{name} … ", end="", flush=True)
        try:
            rows = KINDS[kind](src)
            rows = [r for r in rows if r[0] in BOOKS]
            if len(rows) < 50:
                raise RuntimeError(f"only {len(rows)} passages read")
            with (OUT / f"{tid}.tsv").open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\", lineterminator="\n")
                for r in rows:
                    w.writerow(r)
            books = sorted({r[0] for r in rows}, key=list(BOOKS).index)
            by_id[tid] = {"id": tid, "name": name, "tradition": trad, "books": books, "passages": len(rows),
                          "license": "Public domain (United States)", "source": f"{kind}:{src}"}
            print(f"ok — {len(rows):,} passages, {len(books)} books")
        except Exception as e:
            failed.append(tid)
            print(f"FAILED ({e})")
    (OUT / "catalog.json").write_text(json.dumps(list(by_id.values()), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nInstalled {len(by_id)} texts into {OUT}" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
