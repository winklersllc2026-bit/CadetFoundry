"""
The Vanguard library: everything Vanguard knows comes from here, with sources.

Two kinds of material:
  * cards/   -- short study cards (Markdown with a small header). Hand-checked,
               each one names the official publication it comes from.
  * library/ -- official PUBLIC documents dropped in as-is: .txt, .md, or .pdf
               (PDF needs the optional `pypdf` package). Regulations, the UCMJ,
               field manuals, public job descriptions. See LIBRARY.md.

Search is BM25 over ~900-character passages -- pure Python, no internet, fast
on a Raspberry Pi. Answers quote the passages they used and name the source.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import math
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent
CARDS_DIR = HERE / "cards"
CHUNK = 900
OVERLAP = 150
_WORD = re.compile(r"[a-z0-9][a-z0-9'-]*")
_STOP = set("""a an and are as at be but by for from has have he her his how i if in into is it its me my no not of
on or our she so that the their them then there these they this to up us was we were what when where which who why
will with you your do does did can could would should about than too very just also any all""".split())


# Army and DoD publication numbers, e.g. "AR 670-1", "DA PAM 670-1", "TC 3-22.9", "FM 7-22", "DA Form 4856"
PUB_RE = re.compile(r"\b(?:DA\s+PAM|PAM|AR|TC|FM|ATP|ADP|ADRP|STP|GTA|DA\s+Form|DD\s+Form)\s+\d+(?:[-.–]\d+)*(?:\.\d+)?", re.I)


def _pub_key(s: str) -> str:
    s = re.sub(r"\s+", " ", s.upper().replace("–", "-")).strip().rstrip(".")
    return s.replace("DA PAM", "PAM")


# Numbers in an AI answer are checked against everything the model was given. A number it invented ("10 pull-ups")
# appears in none of it. List numbering ("1." at the start of a line) isn't a fact, so it's skipped.
_NUM_RE = re.compile(r"(?<![\w.:])(\d{1,2}:\d{2}|\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\d:])(\s*(?:%|percent\b|[A-Za-z][\w-]*))?")
_LIST_MARK = re.compile(r"^\s*\d+[.)]\s", re.M)
_WORD_NUMS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
              "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30",
              "forty": "40", "fifty": "50", "sixty": "60", "hundred": "100", "half": "0.5"}


def _num(s: str) -> str:
    s = s.replace(",", "")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _digits(text: str) -> str:
    """Spelled-out numbers as digits ("three gallons" -> "3 gallons"), so both spellings compare equal."""
    return re.sub(r"\b(" + "|".join(_WORD_NUMS) + r")\b", lambda m: _WORD_NUMS[m.group(1).lower()], text or "", flags=re.I)


def numbers_in(text: str) -> set[str]:
    """Every number in a text, including spelled-out ones ("three gallons" -> 3)."""
    return {_num(m.group(1)) for m in _NUM_RE.finditer(_digits(text))}


_LINK_WORDS = {"in", "to", "and", "or", "of", "a", "an", "the", "per", "each", "for", "at", "is", "are", "on", "by"}


def _stem(w: str) -> str:
    return "perc" if w == "%" else w.lower().strip("-%")[:4]


def unsupported_numbers(answer: str, given: str) -> list[str]:
    """Numbers in `answer` that `given` doesn't back up, with the word after them for context.

    A number alone isn't enough -- "10" is somewhere in almost any manual. When the AI ties a number to a word
    ("10 pull-ups"), that word must appear in a sentence with the same number in what it was given ("10 inches"
    doesn't count)."""
    near: dict[str, set[str]] = {}
    for sentence in re.split(r"(?<=[.!?])\s+|\n\s*\n", _digits(given)):     # a list continues its sentence
        words = re.findall(r"\d{1,2}:\d{2}|\d[\d,]*(?:\.\d+)?|[A-Za-z][\w-]*|%", sentence)
        stems = {_stem(x) for x in words if not x[0].isdigit()}
        for w in words:
            if w[0].isdigit():
                near.setdefault(_num(w), set()).update(stems)
    # Only numbers the AI wrote as digits are checked ("five events" is prose, not a figure to verify), and
    # "AR 600-8-10" is checked as a manual, not as numbers.
    body = PUB_RE.sub(" ", _LIST_MARK.sub(" ", answer or ""))
    out = []
    for m in _NUM_RE.finditer(body):
        n, unit = _num(m.group(1)), (m.group(2) or "").strip()
        if n not in near:
            ok = False
        elif not unit or unit.lower() in _LINK_WORDS:
            ok = True                                   # a bare number that the sources contain
        else:
            ok = _stem(unit) in near[n]
        if not ok:
            out.append((m.group(1) + (" " + unit if unit and unit != "%" else unit)).strip())
    return list(dict.fromkeys(out))


# Words that change how a question is phrased, not what it asks ("how far MUST a latrine be")
_FILLER = {"must", "need", "needs", "supposed", "allowed", "ok", "okay", "really", "actually", "exactly"}


def _terms(text: str) -> list[str]:
    return [w.strip("'-") for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


@dataclass
class Card:
    id: str
    title: str
    topic: str
    source: str
    body: str
    quiz: list[tuple[str, str]] = field(default_factory=list)   # (question, answer)
    also: dict[str, list[str]] = field(default_factory=dict)     # question -> other ways Soldiers ask it
    verified: bool = True        # "verified: no" in the header: couldn't be checked against a current public source
    category: str = "military"   # one of CATEGORIES (Learn's sections)
    service: str = "joint"       # one of SERVICES: which branch the card is about ("joint" = every service / general)


# Learn's sections (owner's spec §7), plus two for Cadets interested in serving:
#   explore -- Explore Military Service: information for any curious Cadet (pay, benefits, how service works)
#   basic   -- Basic Training & Beyond: the Soldier study guide, only for Cadets who say they plan to join
CATEGORIES = {"leadership": "Leadership", "citizenship": "Citizenship", "military": "Military Knowledge",
              "health": "Health & Fitness", "careers": "Careers", "explore": "Explore Military Service",
              "basic": "Basic Training & Beyond"}
# Every branch Cadets can explore, whatever their own JROTC program (owner, 2026-10-10). A branch shows in Learn once
# it has checked cards. "joint" = shared material (citizenship, health, careers, general leadership, JROTC itself).
SERVICES = {"army": "Army", "navy": "Navy", "air_force": "Air Force", "marine_corps": "Marine Corps",
            "space_force": "Space Force", "coast_guard": "Coast Guard", "joint": "All services"}

# Which categories this request may see (None = everything: tools, tests, instructors). Set per request by the
# server from the instructor's settings and the Cadet's own choice (security.py / server.py).
_visible: contextvars.ContextVar[frozenset | None] = contextvars.ContextVar("vanguard_visible_categories", default=None)


def use_categories(cats):
    return _visible.set(frozenset(cats) if cats is not None else None)


def reset_categories(token) -> None:
    _visible.reset(token)


def _shown(category: str) -> bool:
    allowed = _visible.get()
    return allowed is None or category in allowed


# Study cards summarize the manuals with paragraph numbers; raw manual pages hold many
# passing mentions ("the platoon sergeants salute"), so a matching card ranks a little higher.
CARD_BOOST = 1.3


@dataclass
class Passage:
    source: str          # e.g. "AR 670-1 (library/AR_670-1.pdf)"
    where: str           # page / heading
    text: str
    terms: list[str] = field(default_factory=list)
    card: bool = False   # a checked study card, not raw manual text
    category: str = ""   # a card's category (empty for manual pages)


def parse_card(path: Path) -> Card | None:
    """cards/*.md:
        ---
        title: The Soldier's Creed
        topic: Creeds & Values
        source: TC 7-21.13, The Soldier's Guide
        ---
        body...
        ## Quiz
        Q: question | A: answer
    """
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\s*\n(.*?)\n---\s*\n(.*)", raw, re.S)
    if not m:
        return None
    meta = dict(re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M))
    body = m.group(2).strip()
    quiz, also = [], {}
    if "## Quiz" in body:
        body, qpart = body.split("## Quiz", 1)
        for q, a in re.findall(r"^Q:\s*(.+?)\s*\|\s*A:\s*(.+)$", qpart, re.M):
            a, _, alts = a.partition("| ALSO:")            # "Q: ... | A: ... | ALSO: one way; another way"
            quiz.append((q.strip(), a.strip()))
            if alts.strip():
                also[q.strip()] = [x.strip() for x in alts.split(";") if x.strip()]
    cat = meta.get("category", "military").strip().lower()
    svc = meta.get("service", "joint").strip().lower().replace(" ", "_").replace("-", "_")
    return Card(id=path.stem, title=meta.get("title", path.stem), topic=meta.get("topic", "General"),
                source=meta.get("source", "Vanguard study card"), body=body.strip(), quiz=quiz, also=also,
                verified=meta.get("verified", "yes").strip().lower() not in ("no", "false"),
                category=cat if cat in CATEGORIES else "military", service=svc if svc in SERVICES else "joint")


def _read_document(path: Path) -> list[tuple[str, str]]:
    """[(where, text)] for a library file."""
    suf = path.suffix.lower()
    if suf in (".txt", ".md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        parts, heading = [], path.stem
        for block in re.split(r"\n(?=#{1,3} )", text):
            h = re.match(r"#{1,3} (.+)", block)
            if h:
                heading = h.group(1).strip()[:80]
            parts.append((heading, block))
        return parts
    if suf == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return []
        try:
            reader = PdfReader(str(path))
            return [(f"page {i + 1}", (pg.extract_text() or "")) for i, pg in enumerate(reader.pages)]
        except Exception:
            return []
    return []


def _chunks(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    out, i = [], 0
    while i < len(text):
        end = min(len(text), i + CHUNK)
        if end < len(text):                          # end on a sentence or line break if possible
            cut = max(text.rfind(". ", i + CHUNK // 2, end), text.rfind("\n", i + CHUNK // 2, end))
            if cut > i:
                end = cut + 1
        piece = text[i:end].strip()
        if len(piece) > 40:
            out.append(piece)
        if end >= len(text):
            break
        i = max(end - OVERLAP, i + 1)
    return out


class Library:
    """Cards + documents, searchable."""

    def __init__(self, cards_dir: Path = CARDS_DIR, library_dir: Path | None = None, cache_dir: Path | None = None):
        self.cards_dir = cards_dir
        self.library_dir = library_dir or (HERE.parent / "library")
        self.cache_dir = cache_dir
        self.all_cards: list[Card] = []
        self.passages: list[Passage] = []
        self.skipped: list[str] = []
        self._df: dict[str, int] = {}
        self._avg = 1.0
        self._lock = threading.Lock()
        self.load()

    @property
    def cards(self) -> list[Card]:
        """The study cards this request may see (see use_categories). Quizzes, the Daily 10, exams, Ask and the
        card list all read this, so a hidden category is hidden everywhere."""
        return [c for c in self.all_cards if _shown(c.category)]

    # ── building ────────────────────────────────────────────────────────────
    def _fingerprint(self) -> str:
        h = hashlib.sha1()
        for d in (self.cards_dir, self.library_dir):
            if d.exists():
                for p in sorted(d.rglob("*")):
                    if p.is_file():
                        st = p.stat()
                        h.update(f"{p}{st.st_size}{st.st_mtime_ns}".encode())
        return h.hexdigest()

    def load(self) -> None:
        with self._lock:
            self.all_cards = [c for c in (parse_card(p) for p in sorted(self.cards_dir.glob("*.md"))) if c]
            passages: list[Passage] = []
            for c in self.all_cards:
                text = f"{c.title}\n{c.body}" + "".join(f"\nQ: {q} A: {a}" for q, a in c.quiz)
                for piece in _chunks(text):
                    passages.append(Passage(source=c.source, where=c.title, text=piece, card=True, category=c.category))
            passages += self._load_documents()
            for p in passages:
                p.terms = _terms(p.where + " " + p.text)
            # Inverted index: for each word, the passages that contain it and how often. A search then only
            # touches passages sharing a word with the question, instead of rescanning all ~12,000.
            postings: dict[str, list[tuple[int, int]]] = {}
            for i, p in enumerate(passages):
                tf: dict[str, int] = {}
                for t in p.terms:
                    tf[t] = tf.get(t, 0) + 1
                for t, f in tf.items():
                    postings.setdefault(t, []).append((i, f))
            self.passages, self._postings = passages, postings
            self._df = {t: len(v) for t, v in postings.items()}
            self._avg = (sum(len(p.terms) for p in passages) / len(passages)) if passages else 1.0
            self._pubs = None

    def _load_documents(self) -> list[Passage]:
        if not self.library_dir.exists():
            return []
        cache = (self.cache_dir / "library_index.json") if self.cache_dir else None
        fp = self._fingerprint()
        if cache and cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                if data.get("fingerprint") == fp:
                    self.skipped = data.get("skipped", [])
                    return [Passage(**p) for p in data["passages"]]
            except Exception:
                pass
        out, skipped = [], []
        for path in sorted(self.library_dir.rglob("*")):
            if not path.is_file() or path.name.startswith(("_", ".")) or path.name.upper() == "README.MD":
                continue
            parts = _read_document(path)
            if not parts:
                skipped.append(path.name)
                continue
            label = path.stem.replace("_", " ")
            for where, text in parts:
                for piece in _chunks(text):
                    out.append(Passage(source=f"{label} ({path.name})", where=where, text=piece))
        self.skipped = skipped
        if cache:
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps({"fingerprint": fp, "skipped": skipped,
                                             "passages": [{"source": p.source, "where": p.where, "text": p.text}
                                                          for p in out]}), encoding="utf-8")
            except Exception:
                pass
        return out

    # ── searching ───────────────────────────────────────────────────────────
    def search(self, query: str, k: int = 5, min_score: float = 1.0) -> list[tuple[float, Passage]]:
        q = _terms(query)
        if not q or not self.passages:
            return []
        n = len(self.passages)
        k1, b = 1.4, 0.75
        acc: dict[int, float] = {}
        for t in set(q):                                  # BM25, summed over the passages each word appears in
            plist = self._postings.get(t)
            if not plist:
                continue
            idf = math.log(1 + (n - len(plist) + 0.5) / (len(plist) + 0.5))
            for i, f in plist:
                norm = k1 * (1 - b + b * len(self.passages[i].terms) / self._avg)
                acc[i] = acc.get(i, 0.0) + idf * f * (k1 + 1) / (f + norm)
        scored = []
        for i, s in acc.items():
            p = self.passages[i]
            if p.card:
                s *= CARD_BOOST
            if s >= min_score:
                scored.append((s, p))
        scored.sort(key=lambda x: -x[0])
        # at most 2 passages from the same place, so answers draw on several sources
        out, per = [], {}
        for s, p in scored:
            if p.card and not _shown(p.category):        # a card from a category this Cadet can't see
                continue
            key = (p.source, p.where)
            if per.get(key, 0) >= 2:
                continue
            per[key] = per.get(key, 0) + 1
            out.append((s, p))
            if len(out) >= k:
                break
        return out

    def context(self, query: str, k: int = 5, budget: int = 4500) -> tuple[str, list[dict]]:
        """Library text for the model + the passages used: [{"source", "where", "text"}]
        (so the Soldier can open the exact page an answer came from)."""
        hits = self.search(query, k)
        if hits:                                  # drop weak matches that only share a word or two with the question
            hits = [h for h in hits if h[0] >= 0.55 * hits[0][0]]
        hits.sort(key=lambda h: not h[1].card)    # checked study cards first: small models lean on what they read first
        parts, cites, used, seen_cards = [], [], 0, set()
        for _s, p in hits:
            text = p.text
            if p.card:
                # Any matching piece of a card brings in the whole card body, once. Cards are short, and a
                # chunk can start mid-sentence. The quiz lines help search, but the model would cite them.
                if p.where in seen_cards:
                    continue
                seen_cards.add(p.where)
                card = next((c for c in self.cards if c.title == p.where), None)
                text = card.body if card else text
            kind = "STUDY CARD (checked summary)" if p.card else "MANUAL PAGE (raw text, may be about something else)"
            block = f"[{kind} · {p.source} — {p.where}]\n{text}"
            if used + len(block) > budget:
                break
            parts.append(block)
            used += len(block)
            label = p.source.split(" (")[0]
            same = next((c for c in cites if c["source"] == label and c["where"] == p.where), None)
            if same:                                  # two passages from one page -> one citation
                same["text"] += "\n…\n" + text
            else:
                cites.append({"source": label, "where": p.where, "text": text, "edition": self.edition(p.source)})
        return "\n\n".join(parts), cites

    def edition(self, source: str) -> str:
        """A library document's publication date, from its first line ("# AR 670-1, ... (01/26/2021)") -> "2021-01-26".
        Search shows it so a Soldier can tell a 2013 manual from a 2026 one."""
        m = re.search(r"\(([^()]+\.(?:md|txt))\)$", source or "")
        if not m:
            return ""
        cache = self.__dict__.setdefault("_editions", {})
        if m.group(1) not in cache:
            date = ""
            try:
                with open(self.library_dir / m.group(1), encoding="utf-8") as f:
                    d = re.search(r"\((\d{2})/(\d{2})/(\d{4})\)\s*$", f.readline())
                date = f"{d.group(3)}-{d.group(1)}-{d.group(2)}" if d else ""
            except (OSError, TypeError):
                pass
            cache[m.group(1)] = date
        return cache[m.group(1)]

    def known_pubs(self) -> set[str]:
        """Every publication number the library or the cards mention ("AR 670-1", "TC 3-22.9", "DA Form 4856")."""
        if getattr(self, "_pubs", None) is None or self._pubs_n != len(self.passages):
            found = set()
            for p in self.passages:
                for m in PUB_RE.finditer(p.source + " " + p.text):
                    found.add(_pub_key(m.group(0)))
            for c in self.all_cards:
                for m in PUB_RE.finditer(c.source + " " + c.body):
                    found.add(_pub_key(m.group(0)))
            self._pubs, self._pubs_n = found, len(self.passages)
        return self._pubs

    def unknown_pubs(self, text: str) -> list[str]:
        """Publications named in an AI answer that Vanguard's library doesn't have (likely made up)."""
        known = self.known_pubs()
        return list(dict.fromkeys(m.group(0).strip() for m in PUB_RE.finditer(text or "")
                                  if _pub_key(m.group(0)) not in known))

    def checked_answer(self, query: str, min_match: float = 0.75) -> dict | None:
        """A study-card quiz answer for a question asked almost the same way.

        Quiz answers were checked against the source, so when one fits, Vanguard shows it word for word instead of
        trusting a small model to restate it. Both sides must share most of their words; a near miss returns None.
        """
        q = set(_terms(query)) - _FILLER
        if not q:
            return None
        # "Who do I salute?" has one real word, so only the same whole question on a card counts ("how do I salute"
        # is a different question).
        short = len(q) == 1
        plain = lambda s: " ".join("i" if w in ("you", "me") else w for w in re.findall(r"[a-z0-9]+", s.lower()))
        best = None
        for c in self.cards:
            if not c.verified:                       # never present an unchecked card as a checked answer
                continue
            for question, answer in c.quiz:
                for asked in [question, *c.also.get(question, [])]:     # the card's question and other ways to ask it
                    t = set(_terms(asked)) - _FILLER
                    if not t:
                        continue
                    if short and plain(asked) != plain(query):
                        continue
                    shared = len(q & t)
                    score = min(shared / len(q), shared / len(t))
                    if score >= min_match and (best is None or score > best[0]):
                        best = (score, question, answer, c)
        if not best:
            return None
        _s, question, answer, c = best
        # "AR 600-25, Salutes... (2026), paras ...; TC 3-21.5, ..." -> "AR 600-25; TC 3-21.5". A card built from several
        # sources names them all (short form) rather than guessing which one this answer came from.
        names = []
        for part in c.source.split(";"):
            pub = re.match(r"\s*((?:DA )?(?:AR|TC|FM|ATP|ADP|PAM) [\d.\-]+)", part)
            name = pub.group(1) if pub else re.split(r" \(|, | — ", part.strip())[0]
            if name and name not in names:
                names.append(name)
        source = "; ".join(names)
        return {"question": question, "answer": answer, "source": source, "card": c.title}

    # ── study ───────────────────────────────────────────────────────────────
    def topics(self) -> dict[str, list[Card]]:
        out: dict[str, list[Card]] = {}
        for c in self.cards:
            out.setdefault(c.topic, []).append(c)
        return out

    def card(self, card_id: str) -> Card | None:
        return next((c for c in self.cards if c.id == card_id), None)

    def stats(self) -> dict:
        docs = sorted({p.source for p in self.passages if "(" in p.source})
        return {"cards": len(self.all_cards), "quiz_questions": sum(len(c.quiz) for c in self.all_cards),
                "documents": docs, "passages": len(self.passages), "skipped": self.skipped}
