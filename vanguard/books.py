"""
Books: free, public-domain reading kept on the device (books/, filled once by tools/fetch_books.py).

Three shelves: Army history (U.S. Army Center of Military History), founding documents (National Archives
transcripts), and classics (public-domain texts from Project Gutenberg, kept with their license).

Books are for reading, not for answers: Ask stays limited to official sources, so a question about rifles
never gets a passage from a novel. The Soldier's place in each book is saved per profile (books.json,
encrypted with the profile and included in backups).
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from vanguard import store

ROOT = Path(__file__).resolve().parent.parent
BOOKS_DIR = ROOT / "books"

SHELVES = ("Army history", "Founding documents", "Classics")

# Every book Cadet Foundry knows how to get. "chapters" is the pattern for a chapter heading in that book's text;
# tables of contents are skipped automatically (a heading needs real text after it).
CATALOG = [
    # Army history -- U.S. Army Center of Military History. history.army.mil blocks scripted downloads,
    # so these are saved by hand into books/ and converted by tools/fetch_books.py.
    {"id": "cmh-30-21", "shelf": "Army history", "title": "American Military History, Volume I",
     "subtitle": "The United States Army and the Forging of a Nation, 1775–1917",
     "author": "Richard W. Stewart, ed. (U.S. Army Center of Military History, CMH Pub 30-21)",
     "kind": "pdf", "file": "30-21.pdf",
     "page": "https://history.army.mil/Publications/Publications-Catalog/American-Military-History-Volume-I/",
     "url": "https://history.army.mil/portals/143/Images/Publications/catalog/30-21.pdf",
     "license": "U.S. Government work — public domain.", "chapters": r"^CHAPTER: .+$"},
    {"id": "cmh-30-22", "shelf": "Army history", "title": "American Military History, Volume II",
     "subtitle": "The United States Army in a Global Era, 1917–2008",
     "author": "Richard W. Stewart, ed. (U.S. Army Center of Military History, CMH Pub 30-22)",
     "kind": "pdf", "file": "30-22.pdf",
     "page": "https://history.army.mil/Publications/Publications-Catalog/American-Military-History-Volume-II/",
     "url": "https://history.army.mil/portals/143/Images/Publications/catalog/30-22.pdf",
     "license": "U.S. Government work — public domain.", "chapters": r"^CHAPTER: .+$"},
    # Founding documents -- National Archives transcriptions
    {"id": "declaration", "shelf": "Founding documents", "title": "The Declaration of Independence",
     "author": "Continental Congress, July 4, 1776 (National Archives transcription)", "kind": "archives",
     "url": "https://www.archives.gov/founding-docs/declaration-transcript", "license": "Public domain."},
    {"id": "constitution", "shelf": "Founding documents", "title": "The Constitution of the United States",
     "author": "Constitutional Convention, 1787 (National Archives transcription)", "kind": "archives",
     "url": "https://www.archives.gov/founding-docs/constitution-transcript", "license": "Public domain.",
     "chapters": r"^#*\s*Article\.?\s+[IVX]+\.?\s*$"},
    {"id": "bill-of-rights", "shelf": "Founding documents", "title": "The Bill of Rights",
     "author": "First Congress, 1789 (National Archives transcription)", "kind": "archives",
     "url": "https://www.archives.gov/founding-docs/bill-of-rights-transcript", "license": "Public domain.",
     "chapters": r"^#*\s*Amendment [IVX]+\s*$", "min": 40},
    {"id": "federalist", "shelf": "Founding documents", "title": "The Federalist Papers",
     "author": "Alexander Hamilton, James Madison, John Jay", "kind": "gutenberg", "pg": 1404,
     "chapters": r"^FEDERALIST No\. \d+\s*$"},
    # Classics -- public domain, from Project Gutenberg
    {"id": "art-of-war", "shelf": "Classics", "title": "The Art of War", "author": "Sun Tzu (translated by Lionel Giles, 1910)",
     "kind": "gutenberg", "pg": 132, "chapters": r"^Chapter [IVX]+\.?\s+\S.*$"},
    {"id": "on-war", "shelf": "Classics", "title": "On War", "author": "Carl von Clausewitz (translated by J. J. Graham, 1873)",
     "kind": "gutenberg", "pg": 1946, "chapters": r"^\s*CHAPTER [IVXL]+\..*$",
     "parts": r"^\s*(SKETCHES FOR )?BOOK [IVX]+\b.*$"},           # Books VII-VIII were left as sketches
    {"id": "meditations", "shelf": "Classics", "title": "Meditations", "author": "Marcus Aurelius",
     "kind": "gutenberg", "pg": 2680, "chapters": r"^THE [A-Z]+ BOOK\s*$"},
    {"id": "grant-memoirs", "shelf": "Classics", "title": "Personal Memoirs of U. S. Grant", "author": "Ulysses S. Grant",
     "kind": "gutenberg", "pg": 4367, "chapters": r"^CHAPTER [IVXL]+\..*$"},
    {"id": "red-badge", "shelf": "Classics", "title": "The Red Badge of Courage", "author": "Stephen Crane",
     "kind": "gutenberg", "pg": 73, "chapters": r"^\s*CHAPTER [IVXL]+\.?\s*$"},
    {"id": "franklin", "shelf": "Classics", "title": "Autobiography of Benjamin Franklin", "author": "Benjamin Franklin",
     "kind": "gutenberg", "pg": 20203, "chapters": r"^\s*[IVX]+\s*$"},
    {"id": "lincoln", "shelf": "Classics", "title": "Speeches & Letters of Abraham Lincoln, 1832–1865",
     "author": "Abraham Lincoln", "kind": "gutenberg", "pg": 14721},
]
for _b in CATALOG:
    if _b["kind"] == "gutenberg":
        _b.setdefault("url", f"https://www.gutenberg.org/ebooks/{_b['pg']}")
        _b.setdefault("license", "Public domain in the U.S. Project Gutenberg eBook — its license is kept in the file.")

_MIN_CHAPTER = 400            # characters of text a heading needs before the next one (skips tables of contents)
_PART_WORDS = 4000            # books without chapter headings are split into parts of about this many words
_cache: dict[str, list[dict]] = {}
_lock = threading.Lock()


def _file(book: dict) -> Path:
    return BOOKS_DIR / f"{book['id']}.txt"


def installed() -> list[dict]:
    return [b for b in CATALOG if _file(b).exists()]


def get(book_id: str) -> dict | None:
    return next((b for b in CATALOG if b["id"] == book_id), None)


def _body(text: str) -> str:
    """The book itself, without Project Gutenberg's header and license (they stay in the file on disk)."""
    m = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\*\*\*", text, re.I)
    if m:
        text = text[m.end():]
    m = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK", text, re.I)
    if m:
        text = text[:m.start()]
    return text.strip()


_ROMAN = re.compile(r"^[IVXLC]+\.?$")


def _nice(title: str) -> str:
    """'CHAPTER XIV. THE MARCH' -> 'Chapter XIV. The March'. Words in capitals are capitalized normally (also in
    mixed headings like 'Chapter I. LAYING PLANS'); Roman numerals and words in normal case are left alone."""
    title = re.sub(r"\s+", " ", title.lstrip("#")).strip()
    return " ".join(w.capitalize() if w.isupper() and len(w) > 1 and not _ROMAN.match(w) else w for w in title.split(" "))


def _toc_titles(text: str) -> dict[str, str]:
    """A contents list like 'I. Ancestry and Early Life in Boston   3' -> {'I': 'I. Ancestry and Early Life in Boston'}."""
    return {m.group(1): f"{m.group(1)}. {m.group(2).strip()}"
            for m in re.finditer(r"(?m)^\s*([IVXLC]+)\.\s+(\S.*?)\s+\d+\s*$", text[: len(text) // 8])}


def split_chapters(text: str, pattern: str | None, min_chars: int = _MIN_CHAPTER,
                   parts: str | None = None) -> list[dict]:
    """[{"title", "text"}] -- by the book's own headings, or in parts of ~4,000 words when it has none.

    Tables of contents are skipped two ways: a heading needs real text after it, and a heading that appears
    again later (the same words) is dropped where it first appears in the opening part of the book.
    `parts` marks larger divisions ("BOOK I.") whose name goes in front of each chapter title, so Chapter I
    of Book I and Chapter I of Book II can be told apart."""
    chapters = []
    if pattern:
        rx = re.compile(pattern, re.M | re.I)
        heads = list(rx.finditer(text))
        part_heads = []
        for m in (re.finditer(parts, text, re.M | re.I) if parts else []):
            name = re.search(r"BOOK\s+[IVXLC]+", m.group(0), re.I)
            name = _nice(name.group(0).upper()) if name else _nice(m.group(0))
            part_heads.append((m.start(), name + (" (sketches)" if "SKETCHES" in m.group(0).upper() else "")))
        real = [h for i, h in enumerate(heads)
                if (heads[i + 1].start() if i + 1 < len(heads) else len(text)) - h.end() >= min_chars]
        key = lambda h: re.sub(r"\W+", " ", h.group(0)).strip().lower()
        later = {}
        for h in real:
            later[key(h)] = h.start()
        # A contents entry with a title ("CHAPTER II. THE SECOND") whose chapter is headed by its number alone
        # later in the text ("CHAPTER II.") is the contents, not the chapter.
        num = lambda h: re.match(r"^\s*#*\s*(chapter\s+[ivxlc\d]+)\.?\s*(\S?)", h.group(0), re.I)
        bare_later = {}
        for h in real:
            m = num(h)
            if m and not m.group(2):
                bare_later[m.group(1).lower()] = h.start()
        early = lambda h: h.start() < len(text) * 0.15
        def contents_entry(h):
            m = num(h)
            titled_twin = m and m.group(2) and bare_later.get(m.group(1).lower(), -1) > h.start()
            return early(h) and (later[key(h)] > h.start() or titled_twin)
        real = [h for h in real if not contents_entry(h)]
        if len(real) >= 2:
            toc = _toc_titles(text)
            # A heading that is only a number ("CHAPTER I.") takes its name from the contents list, which often
            # repeats it with the title ("CHAPTER I. ANCESTRY--BIRTH--BOYHOOD.").
            number = lambda t: re.match(r"^(chapter\s+[ivxlc\d]+)\.?\s*$", t, re.I)
            for hd in heads:
                full = _nice(hd.group(0))
                m = re.match(r"^(chapter\s+[ivxlc\d]+)\.?\s+(\S.*)$", full, re.I)
                if m and hd.start() < len(text) * 0.15:
                    toc.setdefault(m.group(1).lower(), full)
            front = text[:real[0].start()].strip()
            if len(front) >= _MIN_CHAPTER:
                chapters.append({"title": "Front matter", "text": front})
            for i, h in enumerate(real):
                end = real[i + 1].start() if i + 1 < len(real) else len(text)
                # 'CHAPTER: Title' lines come already cased from tools/cmh_convert.py
                title = h.group(0)[9:].strip() if h.group(0).startswith("CHAPTER: ") else _nice(h.group(0))
                bare = number(title)
                title = toc.get(bare.group(1).lower(), title) if bare else toc.get(title.rstrip("."), title)
                part = [name for at, name in part_heads if at < h.start()]
                if part:
                    title = f"{part[-1]} · {title}"
                chapters.append({"title": title, "text": text[h.end():end].strip()})
            return chapters
    paras, part, words = re.split(r"\n\s*\n", text), [], 0
    for p in paras:
        part.append(p)
        words += len(p.split())
        if words >= _PART_WORDS:
            chapters.append({"title": f"Part {len(chapters) + 1}", "text": "\n\n".join(part).strip()})
            part, words = [], 0
    if part:
        chapters.append({"title": f"Part {len(chapters) + 1}", "text": "\n\n".join(part).strip()})
    if len(chapters) == 1:
        chapters[0]["title"] = "Full text"                   # a short document is one reading, not "Part 1"
    return chapters


def chapters(book_id: str) -> list[dict]:
    book = get(book_id)
    if not book or not _file(book).exists():
        return []
    with _lock:
        if book_id not in _cache:
            text = _body(_file(book).read_text(encoding="utf-8", errors="replace"))
            _cache[book_id] = split_chapters(text, book.get("chapters"), book.get("min", _MIN_CHAPTER), book.get("parts"))
        return _cache[book_id]


def shelf() -> dict:
    """Every book Cadet Foundry knows, whether it's on this device, and where this Soldier is in each."""
    progress = store.read_json("books.json", {})
    have = {b["id"] for b in installed()}
    out = []
    for b in CATALOG:
        row = {k: b.get(k, "") for k in ("id", "shelf", "title", "subtitle", "author", "license", "url")}
        row["installed"] = b["id"] in have
        if row["installed"]:
            row["chapters"] = [c["title"] for c in chapters(b["id"])]
            row["at"] = progress.get(b["id"], {}).get("ch")
        out.append(row)
    return {"shelves": list(SHELVES), "books": out, "missing": [b["title"] for b in CATALOG if b["id"] not in have]}


def read(book_id: str, ch: int) -> dict:
    chs = chapters(book_id)
    if not chs:
        raise ValueError("That book isn't on this device.")
    ch = max(0, min(int(ch), len(chs) - 1))
    return {"id": book_id, "title": get(book_id)["title"], "ch": ch, "of": len(chs),
            "chapter": chs[ch]["title"], "text": chs[ch]["text"]}


def save_place(book_id: str, ch: int) -> dict:
    if not get(book_id):
        raise ValueError("Unknown book.")
    progress = store.read_json("books.json", {})
    progress[book_id] = {"ch": max(0, int(ch))}
    store.write_json("books.json", progress)
    return progress[book_id]


def search(q: str, limit: int = 30) -> list[dict]:
    """Where a word or phrase appears in the books on this device, with a short snippet."""
    q = " ".join((q or "").split())
    if len(q) < 3:
        return []
    rx = re.compile(re.escape(q).replace(r"\ ", r"\s+"), re.I)
    hits = []
    for b in installed():
        for i, c in enumerate(chapters(b["id"])):
            m = rx.search(c["text"])
            if m:
                s = max(0, m.start() - 90)
                snippet = re.sub(r"\s+", " ", c["text"][s:m.end() + 90]).strip()
                hits.append({"id": b["id"], "title": b["title"], "ch": i, "chapter": c["title"], "snippet": snippet})
                if len(hits) >= limit:
                    return hits
    return hits
