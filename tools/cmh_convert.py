"""
American Military History (CMH) PDF -> readable text with 'CHAPTER: Title' lines.

The PDFs come from print layouts, so plain text extraction is messy: running headers and page numbers in the
middle of sentences, words split by kerning ('g over nment'), small-capital titles ('t He FormAtiVe yeArs'),
map pages full of place names. This rebuilds the book:
  1. text by page in layout mode (real lines; a paragraph's first line is indented)
  2. chapters from the running headers at page edges (map pages skipped), gaps filled from the contents list
  3. headers, page numbers, captions of removed images and the index dropped
  4. paragraphs from indentation, section headings from short title-case lines
  5. split words rejoined using real English words counted from the clean classics on the device
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from pathlib import Path

NOISE = re.compile(r"^(IMAGE REMOVED DUE TO|LICENSE|RESTRICTIONS|ELEVATION IN (FEET|METERS)|INDEX)$", re.I)
SMALL = {"a", "an", "and", "the", "of", "in", "on", "to", "for", "at", "by", "from", "with"}


def _plain(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _clean(text: str) -> str:
    return re.sub(r"/uni00A0", " ", (text or "").encode("utf-8", "ignore").decode("utf-8")).replace("\t", " ")


def dictionary(books_dir: Path) -> Counter:
    """Real English words, from the clean public-domain books already on this machine (not the manuals:
    'AR 670-1' would make 'ar' look like a word, and 'ar' is exactly the kind of fragment to repair)."""
    c = Counter()
    for f in books_dir.glob("*.txt"):
        if not f.name.startswith("cmh-"):
            c.update(re.findall(r"[a-z]+", f.read_text(encoding="utf-8", errors="ignore").lower()))
    return c


def mend_words(text: str, real_words: Counter, book_words: Counter | None = None) -> str:
    """Kerning splits words with spaces: 'ar my', 'impor tant', 'g over nment', '“dang erous'. Up to four pieces are
    joined when the joined word is known (in the clean books, or unsplit elsewhere in this book) and a piece isn't
    a word in its own right -- common on its own, not dwarfed by the joined word. 'a part' stays two words."""
    book_words = book_words or Counter()

    def fix_line(line: str) -> str:
        toks = line.split(" ")
        out, i = [], 0
        while i < len(toks):
            for n in (4, 3, 2):
                piece = toks[i:i + n]
                if len(piece) != n:
                    continue
                m_first = re.fullmatch(r"([^A-Za-z]*)([A-Za-z]+)", piece[0])
                m_last = re.fullmatch(r"([A-Za-z]+)([^A-Za-z]*)", piece[-1])
                if not (m_first and m_last and all(re.fullmatch(r"[A-Za-z]+", p) for p in piece[1:-1])):
                    continue
                lead, tail = m_first.group(1), m_last.group(2)
                parts = [m_first.group(2)] + piece[1:-1] + [m_last.group(1)]
                joined = "".join(parts)
                known = real_words[joined.lower()] + book_words[joined.lower()]
                word = lambda w: (real_words[w.lower()] >= max(20, known / 8)) and (len(w) > 1 or w.lower() in ("a", "i"))
                # A join starts at a broken piece ('Ser vice' -> 'Service'). It may start at a real word only when the
                # next piece is broken and the joined word is well established: 'for mally' -> 'formally',
                # 'never theless' -> 'nevertheless', but 'in Ser vice' stays 'in Service', not 'inService'.
                starts_broken = not word(parts[0])
                starts_word_ok = real_words[joined.lower()] >= 5 and not word(parts[1])   # clean texts only
                if known >= 2 and (starts_broken or starts_word_ok) and not all(word(p) for p in parts):
                    out.append(lead + joined + tail)
                    i += n
                    break
            else:
                out.append(toks[i])
                i += 1
        return " ".join(out)
    return "\n".join(fix_line(l) for l in text.split("\n"))


def convert(pdf_path: Path, book_title: str, real_words: Counter) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    raw = [_clean(p.extract_text(extraction_mode="layout")) for p in reader.pages]
    pages = [[l.rstrip() for l in t.splitlines() if l.strip()] for t in raw]
    is_map = lambda ls: bool(ls) and bool(re.match(r"\s*Map \d+\b", ls[0]))
    edge = lambda ls: [_plain(l) for l in ls[:2] + ls[-2:]]
    cand = Counter(l for ls in pages if not is_map(ls) for l in set(edge(ls))
                   if len(l) >= 4 and not re.fullmatch(r"[\d\s]+", l))
    running = {l for l, c in cand.items() if c >= 3}
    where: dict[str, list[int]] = {}
    for i, ls in enumerate(pages):
        if not is_map(ls):
            for l in edge(ls):
                where.setdefault(l, []).append(i)
    spread = lambda l: max(where[l]) - min(where[l]) if l in where else 0
    book_words = Counter(re.findall(r"[a-z]+", "\n".join(raw).lower()))
    vocab = {w: c for w, c in (real_words + book_words).items() if c >= 3 and (len(w) > 1 or w in ("a", "i"))}
    total = sum(vocab.values()) or 1

    def segment(run: str) -> list[str]:
        best = [(0.0, [])] + [(-1e18, [])] * len(run)
        for i in range(1, len(run) + 1):
            for j in range(max(0, i - 20), i):
                w = run[j:i]
                if w in vocab and best[j][0] > -1e17 and best[j][0] + math.log(vocab[w] / total) > best[i][0]:
                    best[i] = (best[j][0] + math.log(vocab[w] / total), best[j][1] + [w])
        return best[-1][1] if best[-1][0] > -1e17 else [run]

    def segment_soft(run: str) -> list[str]:
        """Like segment, but a letter the dictionary can't place (a name) costs a lot instead of failing the run."""
        lone = math.log(1 / total) - 12
        best = [(0.0, [])] + [(-1e18, [])] * len(run)
        for i in range(1, len(run) + 1):
            for j in range(max(0, i - 20), i):
                w = run[j:i]
                score = math.log(vocab[w] / total) if w in vocab else (lone if i - j == 1 else None)
                if score is not None and best[j][0] + score > best[i][0]:
                    words = best[j][1] + [w]
                    if w not in vocab and len(best[j][1]) and best[j][1][-1] not in vocab:
                        words = best[j][1][:-1] + [best[j][1][-1] + w]      # unknown letters stay one word
                    best[i] = (best[j][0] + score, words)
        return best[-1][1]

    def respace(text: str) -> str:
        """'W i t h  t h e  i nva s i o n  o f  1 9 4 2' -> 'With the invasion of 1942' (letter-spaced display type)."""
        s, out = text.replace(" ", ""), []
        for part in re.split(r"([A-Za-z]+)", s):
            if part.isalpha():
                at, words = 0, []
                for w in segment_soft(part.lower()):
                    words.append(part[at:at + len(w)])
                    at += len(w)
                out.append(" ".join(words))
            else:
                out.append(part)
        s = "".join(out)
        s = re.sub(r"([,;:!?”)’])(?=[A-Za-z\d“(])", r"\1 ", s)
        s = re.sub(r"\.(?=[A-Za-z]{2,}|\d)", ". ", s)
        s = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?![\d,.–-]|th\b|st\b|nd\b|rd\b|s\b)(?=[A-Za-z])", " ", s)
        return s

    def spaced(text: str) -> bool:
        toks = [t for t in text.split() if t.isalpha()]
        return len(toks) >= 5 and sum(len(t) <= 2 for t in toks) >= 0.6 * len(toks)

    def title_of(text: str) -> str:
        """'THE AMERICAN REVOLUTION, F IRST P HASE' -> 'The American Revolution, First Phase'."""
        text = re.sub(r"\b([A-Z])\.\s?([A-Z])\.", r"|\1.\2.|", _plain(text))
        out = []
        for part in re.split(r"(\|[^|]*\||[^A-Za-z ]+)", text):
            if part.startswith("|"):
                out.append(" " + part.strip("|") + " ")
            elif part.strip() and re.fullmatch(r"[A-Za-z ]+", part):
                lead, trail = part[: len(part) - len(part.lstrip())], part[len(part.rstrip()):]
                out.append(lead + " ".join(segment(re.sub(r"[^a-z]", "", part.lower()))) + trail)
            else:
                out.append(part)
        s = re.sub(r"\s+([:,”’])", r"\1", re.sub(r"\s+", " ", "".join(out)).strip())
        s = re.sub(r"\s*–\s*", "–", s)
        ws, res = s.split(" "), []
        for i, w in enumerate(ws):
            core = re.sub(r"[^a-z]", "", w)
            if core in ("i", "ii", "iii", "iv") and i > 0 and ws[i - 1].lower().startswith("war"):
                res.append(w.upper())
            elif core in SMALL and i > 0 and not ws[i - 1].endswith(":"):
                res.append(w)
            else:
                k = next((n for n, ch in enumerate(w) if ch.isalpha()), 0)
                res.append(w[:k] + w[k:k + 1].upper() + w[k + 1:])
        return re.sub(r"–([a-z])", lambda m: "–" + m.group(1).upper(), " ".join(res))

    # chapters: running headers at page edges (a chapter's title tops its pages from the second page on)
    starts: dict[int, tuple[str, str]] = {}
    for i, ls in enumerate(pages):
        if is_map(ls):
            continue
        if edge(ls)[:1] == ["PROLOGUE"] and not starts:
            starts[max(0, i - 1)] = ("prologue", "Prologue")
            continue
        for l in edge(ls):
            if (l in running and l.upper() == l and len(re.findall(r"[A-Z]", l)) >= 6 and not NOISE.match(l)
                    and l != "AMERICAN MILITARY HISTORY" and cand[l] >= 4 and spread(l) >= 8):
                key = re.sub(r"[^a-z0-9]", "", l.lower())
                if key not in {k for k, _ in starts.values()}:
                    starts[i - 1] = (key, title_of(l))
    # the contents list fills a chapter whose header never shows (book pages vs. PDF pages)
    found = re.findall(r"(?m)^\s*(\d{1,2})\s*\.\s+(.+?)\s*(?:\.\s*){3,}\s*(\d+)\s*$",
                       "\n".join(_clean(p.extract_text() or "") for p in reader.pages[:40]))
    toc = []
    for n, title, page in found:
        if toc and int(n) <= int(toc[-1][0]):
            break                                 # the list of maps starts its numbering again
        toc.append((n, title, page))
    same = lambda a, b: bool(a and b) and (a.startswith(b) or b.startswith(a))
    offs = [p - int(page) for _n, title, page in toc for p, (key, _t) in starts.items()
            if same(re.sub(r"[^a-z0-9]", "", title.lower()), key)]
    if offs:
        off = int(statistics.median(offs))
        for _n, title, page in toc:
            k = re.sub(r"[^a-z0-9]", "", title.lower())
            if not any(same(k, key) for key, _t in starts.values()):
                starts[int(page) + off] = (k, title_of(title.upper()))
    # Step back to each chapter's opening page. It starts with the chapter number alone on a line ("4"), then the
    # title in display type (often scrambled by extraction), then the text. The Prologue has no number.
    body_lines = lambda q: [_plain(x) for x in pages[q] if _plain(x) and _plain(x) not in running]
    opener = lambda q: bool(body_lines(q)) and bool(re.fullmatch(r"\d{1,2}", body_lines(q)[0]))
    moved = {}
    for p, (key, title) in starts.items():
        near = [q for q in range(max(0, p - 3), p + 2) if q < len(pages) and opener(q)]
        moved[min(near, key=lambda q: abs(q - p)) if near and key != "prologue" else p] = (key, title)
    starts = dict(sorted(moved.items()))
    index_page = next((i for i, ls in enumerate(pages) if "INDEX" in edge(ls)), len(pages))

    # text: one stream for the whole book; a paragraph starts at an indented line
    out: list[str] = []
    para: list[str] = []

    def flush():
        if para:
            out.append(" ".join(para))
            para.clear()
    for i, ls in enumerate(pages[:index_page]):
        if is_map(ls):
            continue
        if i in starts:
            flush()
            out.append(f"CHAPTER: {starts[i][1]}")
        body = [l for l in ls if _plain(l) and _plain(l) not in running and not NOISE.match(_plain(l))]
        if i in starts and starts[i][0] != "prologue":
            # The opening page: chapter number, display title, then two text lines indented around the big first
            # letter (drop cap), which extraction puts at the start of the third line ('Tpean' = T + 'pean').
            # Drop the number and title (the clean title comes from the running headers); put the letter back.
            ind = lambda l: len(l) - len(l.lstrip())
            j = next((n for n, l in enumerate(body[:12]) if n >= 2 and ind(l) <= 1 and re.match(r"[A-Z]", l)
                      and ind(body[n - 1]) >= 3 and ind(body[n - 2]) >= 3), None)
            if j is not None:
                first = body[j - 2].lstrip()
                body = [" " * 8 + body[j].lstrip()[0] + first, body[j - 1].lstrip(), body[j].lstrip()[1:]] + body[j + 1:]
            else:
                body = body[next((n for n, l in enumerate(body) if len(_plain(l)) >= 45), len(body)):]
        body = [l for l in body if not re.fullmatch(r"[\d\s]+", _plain(l))]
        if not body:
            continue
        indents = Counter(len(l) - len(l.lstrip()) for l in body)
        base = indents.most_common(1)[0][0]
        for l in body:
            ind, text = len(l) - len(l.lstrip()), _plain(l)
            if spaced(text):
                text = respace(text)
            if ind > base + 12 or ind < base - 4:      # off the text column: a caption or side note
                continue
            if ind >= base + 3:                        # an indented first line starts a paragraph...
                if not para or re.search(r"[.?!:”\"’)]$", para[-1]):
                    flush()                           # ...unless the last one stopped mid-sentence
            elif (len(text) < 60 and not re.search(r"[.,;:?!”’\"-]$", text) and text[:1].isupper()
                  and sum(w[:1].isupper() for w in text.split()) >= max(1, len(text.split()) // 2) and not para):
                flush()                               # a short title-case line on its own: a section heading
                out.append("### " + text)
                continue
            if para and para[-1].endswith("-") and text[:1].islower():
                para[-1] = para[-1][:-1] + text.split(" ", 1)[0]
                rest = text.split(" ", 1)[1] if " " in text else ""
                if rest:
                    para.append(rest)
            else:
                para.append(text)
    flush()
    body_text = mend_words("\n\n".join(out), real_words, book_words)
    return f"{book_title}\n\n{body_text}\n"


if __name__ == "__main__":
    import sys
    import time
    t = time.time()
    root = Path(__file__).resolve().parent.parent
    text = convert(Path(sys.argv[1]), sys.argv[2], dictionary(root / "books"))
    Path(sys.argv[3]).write_text(text, encoding="utf-8")
    print(f"{time.time() - t:.0f}s", [l for l in text.splitlines() if l.startswith("CHAPTER: ")])
