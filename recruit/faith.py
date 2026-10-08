"""
Optional faith library: public-domain scriptures from several traditions.

Texts are installed by tools/fetch_faith.py into faith/ as simple tab-separated
files (book, chapter, verse, text) plus faith/catalog.json. Nothing here is
required -- each Soldier chooses what (if anything) to use.

References understood: "John 3:16", "Jn 3:16-18", "Psalm 23", "1 Cor 13:4-7",
"Quran 2:255" / "Surah 2:255", "1 Nephi 3:7", "Gita 2", "Dhammapada 183", "Tao 8".
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

FAITH_DIR = Path(__file__).parent.parent / "faith"

# code -> (display name, aliases). Bible codes are the standard USFM ones used by eBible.org.
BOOKS: dict[str, tuple[str, tuple[str, ...]]] = {
    "GEN": ("Genesis", ("gen", "gn", "ge")), "EXO": ("Exodus", ("exod", "ex", "exo")),
    "LEV": ("Leviticus", ("lev", "lv", "le")), "NUM": ("Numbers", ("num", "nm", "nu")),
    "DEU": ("Deuteronomy", ("deut", "dt", "deu")), "JOS": ("Joshua", ("josh", "jos")),
    "JDG": ("Judges", ("judg", "jdg", "jg")), "RUT": ("Ruth", ("ru", "rth")),
    "1SA": ("1 Samuel", ("1 sam", "1sam", "1 sm", "1sa")), "2SA": ("2 Samuel", ("2 sam", "2sam", "2 sm", "2sa")),
    "1KI": ("1 Kings", ("1 kgs", "1kgs", "1 ki", "1ki")), "2KI": ("2 Kings", ("2 kgs", "2kgs", "2 ki", "2ki")),
    "1CH": ("1 Chronicles", ("1 chr", "1chr", "1 ch")), "2CH": ("2 Chronicles", ("2 chr", "2chr", "2 ch")),
    "EZR": ("Ezra", ("ezr",)), "NEH": ("Nehemiah", ("neh", "ne")), "EST": ("Esther", ("esth", "est")),
    "JOB": ("Job", ("jb",)), "PSA": ("Psalms", ("psalm", "ps", "psa", "pss")), "PRO": ("Proverbs", ("prov", "pr", "pro", "prv")),
    "ECC": ("Ecclesiastes", ("eccl", "ecc", "qoh")), "SNG": ("Song of Songs", ("song of solomon", "song", "sos", "canticles")),
    "ISA": ("Isaiah", ("isa", "is")), "JER": ("Jeremiah", ("jer", "je")), "LAM": ("Lamentations", ("lam", "la")),
    "EZK": ("Ezekiel", ("ezek", "eze", "ezk")), "DAN": ("Daniel", ("dan", "dn", "da")), "HOS": ("Hosea", ("hos", "ho")),
    "JOL": ("Joel", ("jl",)), "AMO": ("Amos", ("am", "amo")), "OBA": ("Obadiah", ("obad", "ob")),
    "JON": ("Jonah", ("jon", "jnh")), "MIC": ("Micah", ("mic", "mi")), "NAM": ("Nahum", ("nah", "na")),
    "HAB": ("Habakkuk", ("hab",)), "ZEP": ("Zephaniah", ("zeph", "zep")), "HAG": ("Haggai", ("hag", "hg")),
    "ZEC": ("Zechariah", ("zech", "zec")), "MAL": ("Malachi", ("mal",)),
    "MAT": ("Matthew", ("matt", "mt", "mat")), "MRK": ("Mark", ("mk", "mrk", "mar")), "LUK": ("Luke", ("lk", "luk")),
    "JHN": ("John", ("jn", "jhn", "joh")), "ACT": ("Acts", ("ac", "act")), "ROM": ("Romans", ("rom", "ro")),
    "1CO": ("1 Corinthians", ("1 cor", "1cor", "1 co")), "2CO": ("2 Corinthians", ("2 cor", "2cor", "2 co")),
    "GAL": ("Galatians", ("gal", "ga")), "EPH": ("Ephesians", ("eph",)), "PHP": ("Philippians", ("phil", "php")),
    "COL": ("Colossians", ("col",)), "1TH": ("1 Thessalonians", ("1 thess", "1thess", "1 th")),
    "2TH": ("2 Thessalonians", ("2 thess", "2thess", "2 th")), "1TI": ("1 Timothy", ("1 tim", "1tim", "1 ti")),
    "2TI": ("2 Timothy", ("2 tim", "2tim", "2 ti")), "TIT": ("Titus", ("tit",)), "PHM": ("Philemon", ("philem", "phm")),
    "HEB": ("Hebrews", ("heb",)), "JAS": ("James", ("jas", "jm")), "1PE": ("1 Peter", ("1 pet", "1pet", "1 pe")),
    "2PE": ("2 Peter", ("2 pet", "2pet", "2 pe")), "1JN": ("1 John", ("1 jn", "1jn", "1 jo")),
    "2JN": ("2 John", ("2 jn", "2jn")), "3JN": ("3 John", ("3 jn", "3jn")), "JUD": ("Jude", ("jud",)),
    "REV": ("Revelation", ("rev", "re", "revelations", "apocalypse")),
    # Deuterocanonical books (Catholic / Orthodox Bibles)
    "TOB": ("Tobit", ("tob", "tb")), "JDT": ("Judith", ("jdt", "jdth")), "WIS": ("Wisdom", ("wis", "wisdom of solomon")),
    "SIR": ("Sirach", ("sir", "ecclesiasticus", "ecclus")), "BAR": ("Baruch", ("bar",)),
    "1MA": ("1 Maccabees", ("1 macc", "1macc", "1 ma")), "2MA": ("2 Maccabees", ("2 macc", "2macc", "2 ma")),
    # Other scriptures
    "1NE": ("1 Nephi", ("1 ne", "1ne", "1 nephi")), "2NE": ("2 Nephi", ("2 ne", "2ne")), "JAC": ("Jacob", ("jac",)),
    "ENO": ("Enos", ("enos",)), "JAR": ("Jarom", ("jarom",)), "OMN": ("Omni", ("omni",)),
    "WOM": ("Words of Mormon", ("w of m", "wom")), "MOS": ("Mosiah", ("mosiah",)), "ALM": ("Alma", ("alma",)),
    "HEL": ("Helaman", ("hel",)), "3NE": ("3 Nephi", ("3 ne", "3ne")), "4NE": ("4 Nephi", ("4 ne", "4ne")),
    "MRM": ("Mormon", ("morm", "mormon")), "ETH": ("Ether", ("ether",)), "MRO": ("Moroni", ("moro", "moroni")),
    "QUR": ("Quran", ("quran", "qur'an", "koran", "surah", "sura")),
    "GIT": ("Bhagavad Gita", ("gita", "bhagavad gita", "bg")),
    "DHP": ("Dhammapada", ("dhammapada", "dhp")),
    "TAO": ("Tao Te Ching", ("tao", "tao te ching", "daodejing", "ttc")),
}
_ALIAS = {}
for code, (name, aliases) in BOOKS.items():
    for a in (name.lower(), code.lower(), *aliases):
        _ALIAS[re.sub(r"\s+", " ", a)] = code

_REF = re.compile(r"(?i)\b((?:[1-4]\s?)?[A-Za-z][A-Za-z' ]{0,22}?)\.?\s+(\d{1,3})(?::(\d{1,3})(?:\s*[-–]\s*(\d{1,3}))?)?\b")


def parse_ref(text: str) -> tuple[str, int, int, int] | None:
    """'John 3:16-18' -> ('JHN', 3, 16, 18). Verse 0 = whole chapter."""
    for m in _REF.finditer(text or ""):
        name = re.sub(r"\s+", " ", m.group(1).strip().lower())
        code = _ALIAS.get(name) or _ALIAS.get(name.replace(" ", ""))
        if not code:
            # allow "the gospel of john", "book of psalms" style
            for k in sorted(_ALIAS, key=len, reverse=True):
                if name.endswith(" " + k):
                    code = _ALIAS[k]
                    break
        if not code:
            continue
        ch = int(m.group(2))
        v1 = int(m.group(3) or 0)
        v2 = int(m.group(4) or v1)
        return code, ch, v1, max(v1, v2)
    return None


def find_refs(text: str, limit: int = 3) -> list[tuple[str, int, int, int]]:
    out, seen = [], set()
    for m in _REF.finditer(text or ""):
        r = parse_ref(m.group(0))
        if r and r not in seen:
            seen.add(r)
            out.append(r)
        if len(out) >= limit:
            break
    return out


class Faith:
    def __init__(self, folder: Path = FAITH_DIR):
        self.folder = folder
        self._cache: dict[str, dict] = {}
        self.catalog = self._catalog()

    def _catalog(self) -> list[dict]:
        try:
            cat = json.loads((self.folder / "catalog.json").read_text(encoding="utf-8"))
        except Exception:
            return []
        return [t for t in cat if (self.folder / f"{t['id']}.tsv").exists()]

    def reload(self) -> None:
        self._cache.clear()
        self.catalog = self._catalog()

    def _load(self, tid: str) -> dict:
        """{book: {chapter: [(verse, text), ...]}}"""
        if tid not in self._cache:
            data: dict = {}
            with (self.folder / f"{tid}.tsv").open(encoding="utf-8", newline="") as f:
                for book, ch, v, text in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                    data.setdefault(book, {}).setdefault(int(ch), []).append((int(v), text))
            self._cache[tid] = data
        return self._cache[tid]

    def info(self, tid: str) -> dict | None:
        return next((t for t in self.catalog if t["id"] == tid), None)

    def texts_with(self, book: str) -> list[dict]:
        return [t for t in self.catalog if book in t.get("books", [])]

    def passage(self, tid: str, book: str, ch: int, v1: int, v2: int) -> list[dict]:
        chap = self._load(tid).get(book, {}).get(ch, [])
        name = BOOKS.get(book, (book,))[0]
        if book == "DHP" and v1 == 0:          # "Dhammapada 183" means verse 183 (numbered straight through)
            hits = [(c, v, t) for c, vs in self._load(tid).get(book, {}).items() for v, t in vs if v == ch]
            return [{"ref": f"{name} {v}", "text": t} for c, v, t in hits]
        rows = [(v, t) for v, t in chap if v1 == 0 or v1 <= v <= v2]
        if not rows and chap and all(v == 0 for v, _t in chap):
            rows = chap                         # texts without verse numbers (e.g. Arnold's Gita): whole chapter
        return [{"ref": f"{name} {ch}" + (f":{v}" if v else ""), "text": t} for v, t in rows[:200]]

    def lookup(self, ref: str, ids: list[str], compare: bool = False) -> dict:
        r = parse_ref(ref)
        if not r:
            return {"error": "I couldn't read that reference. Try e.g. John 3:16, Psalm 23, Quran 2:255, 1 Nephi 3:7."}
        book, ch, v1, v2 = r
        texts = self.texts_with(book)
        if not texts:
            return {"error": f"{BOOKS[book][0]} isn't in any installed text."}
        if not compare:
            chosen = [t for t in texts if t["id"] in ids] or texts[:1]
            texts = chosen[:1]
        return {"ref": ref, "results": [{"id": t["id"], "name": t["name"], "tradition": t["tradition"],
                                         "verses": self.passage(t["id"], book, ch, v1, v2)} for t in texts]}

    def search(self, words: str, ids: list[str], limit: int = 40) -> dict:
        terms = [w for w in re.findall(r"[a-z']{3,}", (words or "").lower())]
        if not terms:
            return {"error": "Type at least one word to search for."}
        texts = [t for t in self.catalog if t["id"] in ids] or self.catalog[:1]
        results = []
        for t in texts[:1]:
            hits = []
            for book, chaps in self._load(t["id"]).items():
                for ch, verses in chaps.items():
                    for v, text in verses:
                        low = text.lower()
                        if all(term in low for term in terms):
                            hits.append({"ref": f"{BOOKS.get(book, (book,))[0]} {ch}" + (f":{v}" if v else ""),
                                         "text": text})
                            if len(hits) >= limit:
                                break
            results.append({"id": t["id"], "name": t["name"], "tradition": t["tradition"], "verses": hits})
        return {"ref": words, "results": results}

    def context_for(self, text: str, preferred: list[str]) -> str:
        """Exact text of scripture referenced in a chat message, for the AI to work from."""
        blocks = []
        for book, ch, v1, v2 in find_refs(text):
            texts = self.texts_with(book)
            if not texts:
                continue
            chosen = [t for t in texts if t["id"] in preferred] or texts[:1]
            for t in chosen[:2]:
                verses = self.passage(t["id"], book, ch, v1, v2 if v2 - v1 < 30 else v1 + 30)
                if verses:
                    blocks.append(f"[{t['name']} — {t['tradition']}]\n" +
                                  "\n".join(f"{v['ref']} {v['text']}" for v in verses[:40]))
        return "\n\n".join(blocks)
