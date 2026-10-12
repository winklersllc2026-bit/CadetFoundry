"""
Multiple-choice answers for study-card questions: Practice quizzes, the Daily 10, exams and live questions.

Owner's report (2026-10-11): the wrong choices were picked at random from every other answer, so "Name three things
drill builds" offered "120" and "The Blue Book", and "What are the three Marine Corps values?" offered "1883" and
"Honor" (a piece of the right answer). Now every wrong choice has to:
  - be the same KIND of answer as the right one (a number for a number, a list for a list, a short name for a name)
    and the same sort of thing (a person or rank for a person, a unit for a unit, a verb phrase for a verb phrase);
  - answer the same kind of question (who / when / where / why / how / what), about the same subject;
  - be clearly different from the right answer -- never equal to it, never a piece of it, and never the answer to the
    same question asked on another card for the same branch (that one is probably right too).
Numbers get nearby numbers in the same words ("Twice" -> "Once", "Three times"). Yes/no and "this or that" questions
offer just those options. Card authors can write their own wrong answers, which are used first:
    Q: question | A: answer | WRONG: one; two; three
A choice shows the short part of an answer ("The Anvil" for "The Anvil -- two days and two nights"); the whole answer
is shown after the Cadet picks. A question with no fair set of choices gets None: it's asked as a typed answer instead,
and left out of exams -- never padded with nonsense. tests/test_choices.py checks every question in the library.
"""
from __future__ import annotations

import math
import random
import re
from functools import lru_cache


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


STOP = set("""a an the of to in on at for and or but is are was were be been it its this that these those what which who whom
whose when where why how do does did can could should would will may must you your yours they their them he his she her we
our us i me my not no yes as by with from into than then there here about name two three four five six one list give
called call say says mean means kind type part each every all any some most more much many""".split())
# Branch words: two questions that differ only in the branch ask the same sort of thing about different services.
BRANCH = set("""army navy naval marine marines corps air force space coast guard guardian guardians soldier soldiers sailor
sailors airman airmen jrotc rotc njrotc afjrotc mcjrotc usmc usaf uscg ussf""".split())
AUX = re.compile(r"^(is|are|was|were|can|could|should|would|will|do|does|did|may|must|has|have|had)\b", re.I)
YESNO = re.compile(r"^(yes|no)\b(?!\s+(more|less|fewer|later|earlier|longer|sooner|one)\b)", re.I)   # not "No more than 2"
NUM_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
             "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}
WORD_OF = {v: k for k, v in NUM_WORDS.items()}
DIGITS = re.compile(r"(?<![\w.])(\$?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(%?)")
NUM_WORD_RE = re.compile(r"\b(" + "|".join(NUM_WORDS) + r"|once|twice)\b", re.I)
MONTHS = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d", re.I)

# What sort of thing a short answer names. A wrong choice for "Who is the senior NCO of a company?" has to be a person
# or a rank, never "The Continental Congress". Checked in this order.
CLASSES = [
    ("command", re.compile(r"\b(?![IVXL]+\b)[A-Z]{3,}\b")),          # "Ready, TWO" -- not "Article III"
    ("person", re.compile(r"\b(private|corporal|sergeants?|lieutenants?|captains?|major|colonel|general|ensign|admiral|"
                          r"commanders?|seaman|petty officer|chief|specialist|warrant|airman|guardian|soldiers?|sailors?|"
                          r"leaders?|ncos?|officers?|instructors?|cadets?|president|secretary|chaplain|recruiter|"
                          r"mentors?|mentee|coach|parents?|teammates?|members?|marines?|airmen)\b", re.I)),
    ("unit", re.compile(r"\b(squad|team|platoon|company|battalion|brigade|division|flight|wing|squadron|group|element|"
                        r"section|fleet|regiment|detachment|unit|battery|troop)s?\b", re.I)),
    ("doc", re.compile(r"\b(manual|creed|article|amendment|book|guide|regulation|form|publication|law|act|order|oath|"
                       r"code|constitution|declaration|pledge|policy|message|instruction|report)s?\b", re.I)),
    ("org", re.compile(r"\b(corps|congress|department|academy|school|court|office|agency|center|government|branch|"
                       r"committee|council|senate|house|administration|command|service|association|university|college)\b",
                       re.I)),
    ("body", re.compile(r"\b(muscles?|diaphragm|foot|feet|hands?|arms?|legs?|head|eyes|heart|lungs?|chest|back|"
                        r"shoulders?|thumbs?|fingers?|elbows?|knees?|heels?|toes?|chin)\b", re.I)),
]
# An answer that starts with one of these is an instruction ("Ask for it to be repeated"), not a thing.
VERBS = set("""ask tell use keep stay make take give call move stand report avoid wear salute check find follow get go be do
have let look put read say see send set show start stop talk think try turn wait walk write contact practice prepare raise
drink eat sleep help listen learn lead apply fill bring pick plan protect remove return seek speak study treat carry clean
place hold face step march drop lift run press push pull breathe focus identify explain describe review request notify
inform record compare receive issue conduct assess decide encourage build develop train teach serve obey respect protect
support visit attend complete join enlist register submit choose""".split())


def _class(h: str) -> str:
    h = re.sub(r"\bgeneral orders?\b", "orders", h, flags=re.I)      # a sentry's general orders aren't a General
    for name, rx in CLASSES:
        if rx.search(h):
            return name
    return ""


def _group(q: str) -> str:
    """The kind of question: wrong choices come from questions of the same kind. "In the Navy's ninth general order,
    whom does a sentry call ...?" is a "who" question."""
    n = norm(q)
    m = re.search(r"\b(who|whose|whom|when|where|why|how|what|which)\b", n)
    if m and not AUX.match(n):
        n = n[m.start():]
    if re.match(r"(who|whose|whom)\b", n):
        return "who"
    if re.match(r"(when|what year|in what year|what date)\b", n):
        return "when"
    if re.match(r"where\b", n):
        return "where"
    if re.match(r"why\b", n):
        return "why"
    if re.match(r"(how (many|much|long|far|often|old|tall|fast)|about how)\b", n):
        return "amount"
    if re.match(r"how\b", n):
        return "how"
    if AUX.match(n):
        return "yesno"
    return "what"


def _shape(h: str) -> str:
    """"verb" (an instruction: "Ask ...", "To fly ..."), "ing" ("Detecting ..."), "thing" ("The ...", "A ...") or ""
    (can't tell, fits anything)."""
    w = norm(h).split()[0] if norm(h) else ""
    if w == "to" or w in VERBS:
        return "verb"
    if len(w) > 4 and w.endswith("ing") and w not in ("thing", "spring", "string", "wing", "king"):
        return "ing"
    if w in ("the", "a", "an", "his", "her", "their", "your", "our", "its"):
        return "thing"
    return ""


def _proper_name(h: str) -> bool:
    """"Paul W. Airey", "Baron Friedrich von Steuben" -- a person's name, not a role like "The junior person"."""
    if re.match(r"^(the|a|an)\b", h.strip(), re.I):
        return False
    words = [w for w in re.findall(r"[A-Za-z][\w.'’-]*", h) if w.lower() not in ("von", "de", "of", "jr", "jr.", "sr")]
    return len(words) >= 2 and all(w[:1].isupper() for w in words)


def _shapes_fit(a: str, b: str) -> bool:
    return a == b or not a or not b


def _ask_noun(q: str) -> str:
    """The noun a "which/what X" question asks for: "In which operation ..." -> "operation"."""
    m = re.search(r"\b(?:which|what)\s+([a-z]+)", norm(q))
    return m.group(1) if m and m.group(1) not in STOP else ""


def head(answer: str) -> str:
    """The part of an answer a choice shows: "The Anvil -- two days and two nights" -> "The Anvil". A trailing
    explanation after a dash, or a trailing note in brackets, is shown after the Cadet answers."""
    a = (answer or "").strip()
    m = re.match(r"^(.+?)\s+[—–]\s+(.+)$", a) or re.match(r"^(.+?)\s+--\s+(.+)$", a)
    if m and len(m.group(2).split()) >= 2 and norm(m.group(1)):
        a = m.group(1).strip()
    b = re.sub(r"\s*\([^()]*\)\s*$", "", a).strip()
    return (b if norm(b) else a).rstrip(".;:, ")


def _strip_article(s: str) -> str:
    return re.sub(r"^(the|a|an)\s+", "", norm(s))


def _binary(q: str, a: str) -> list[str] | None:
    """Yes/no, or "this or that": "Is it easier or harder ...?" (answered "Harder -- ...") offers Easier / Harder;
    "Which is older, the Army or the Declaration of Independence?" offers those two."""
    na = _strip_article(a)

    def starts(opt: str) -> bool:
        o = _strip_article(opt)
        return bool(o) and (na == o or na.startswith(o + " "))

    m = re.search(r",\s*([^,?]+?)\s+or\s+([^,?]+?)\s*\?\s*$", q)        # "..., the Army or the Declaration ...?"
    if m:
        left, right = m.group(1).strip(), m.group(2).strip()
        if starts(left) != starts(right):
            return [left[:1].upper() + left[1:], right[:1].upper() + right[1:]]
    low = [w.lower() for w in re.findall(r"[A-Za-z'-]+", q)]
    for i, w in enumerate(low):
        if w == "or" and 0 < i < len(low) - 1:
            left, right = low[i - 1], low[i + 1]
            if left in STOP or right in STOP:
                continue
            if starts(left) != starts(right):
                return [left.capitalize(), right.capitalize()]
    if YESNO.match(a.strip()) and (AUX.match(q.strip()) or len(head(a).split()) <= 1):
        return ["Yes", "No"]
    return None


def right_choice(q: str, a: str) -> str:
    """What the right answer looks like among the choices (grading compares a pick to this)."""
    two = _binary(q, a)
    if two:
        if YESNO.match(a.strip()):
            return "Yes" if a.strip()[:1].lower() == "y" else "No"
        na = _strip_article(a)
        return next(o for o in two if na == _strip_article(o) or na.startswith(_strip_article(o) + " "))
    return head(a)


def is_right(q: str, a: str, choice: str) -> bool:
    c = norm(choice)
    return bool(c) and c in (norm(right_choice(q, a)), norm(a))


def _content(s: str) -> set[str]:
    return {w for w in norm(s).split() if w not in STOP and len(w) > 1}


def _subject(q: str) -> set[str]:
    """What a question is about, without the branch -- single letters kept ("the letter X")."""
    return {w for w in norm(q).split() if w not in STOP} - BRANCH


def _items(s: str) -> list[str]:
    parts = re.split(r",|;|\band\b|\bor\b|/", s, flags=re.I)
    return [norm(p) for p in parts if norm(p)]


def _numbers(s: str) -> list[float]:
    out = [float(m.group(2).replace(",", "") + (m.group(3) or "")) for m in DIGITS.finditer(s)]
    if not out:
        for m in NUM_WORD_RE.finditer(s):
            w = m.group(1).lower()
            out.append({"once": 1, "twice": 2}.get(w, NUM_WORDS.get(w, 0)))
    return out


ASKS_NUMBER = re.compile(r"^(how (many|much|long|far|often|old|tall|fast)|about how|at what age|what year|in what year|"
                         r"when|what percent|what( total| minimum| maximum| passing)? (score|percent|percentage|age|grade))")
ASKS_LIST = re.compile(r"\b(name (two|three|four|five|six|seven|the)|(what|which) are the|list the|"
                       r"(two|three|four|five|six|seven) (\w+ )?(ways|things|parts|steps|kinds|types|values))\b")


@lru_cache(maxsize=8192)
def features(q: str, a: str) -> dict:
    h = head(a)
    hw = h.split()
    nums = _numbers(h)
    ql = norm(q)
    items = _items(h)
    if (nums or ORDINAL.search(h) or ROMAN.search(h)) and (len(hw) <= 7 or (ASKS_NUMBER.match(ql) and len(hw) <= 12)) \
            and not re.search(r",.*,", h) and _class(h) != "command":            # "Ready, TWO" is a command
        kind = "number"
    elif h.count(",") + h.count(";") >= 2 or (len(items) >= 2 and ASKS_LIST.search(ql)):
        kind = "list"
    elif len(hw) <= 4:
        kind = "term"
    else:
        kind = "phrase"
    unit = _content(re.sub(r"\d[\d,.]*", " ", NUM_WORD_RE.sub(" ", h))) if kind == "number" else set()
    return {"head": h, "kind": kind, "nums": nums, "unit": unit, "len": max(1, len(h)), "nwords": len(hw),
            "group": _group(q) if q else "", "noun": _ask_noun(q), "cls": _class(h), "shape": _shape(h),
            "yn": bool(YESNO.match(h)), "subject": _subject(q), "words": _content(h), "items": items}


# ── numbers: nearby values in the same words ─────────────────────────────────────────────────────────────────────────
def _grain(v: float) -> float:
    if v != int(v):
        return 0.5 if (v * 2) == int(v * 2) else 10 ** -len(str(v).split(".")[1])
    v = int(v)
    for g in (1000, 100, 50, 10, 5):
        if v >= g * 2 and v % g == 0:
            return g
    return 1


def _alt(v: float, i: int, is_year: bool, is_pct: bool) -> float | None:
    if is_year:
        return v + (-10, 10, -5, 5, -25, 25)[i]
    if v == int(v) and v <= 12:
        n = (v + 1, v - 1, v + 2, v * 2, v - 2, v + 3)[i]
        return n if n > 0 else None
    g = _grain(v)
    n = round(v * (1.25, 0.75, 1.5, 0.6, 2, 0.5)[i] / g) * g
    if n <= 0 or n == v or (is_pct and n > 100):
        return None
    return n


def _fmt(n: float, like: str) -> str:
    if n == int(n):
        n = int(n)
        return f"{n:,}" if "," in like else str(n)
    return str(round(n, 6))


def _word(n: float, like: str) -> str | None:
    if n != int(n) or not 0 < int(n) <= 20:
        return None
    n, low = int(n), like.lower()
    if low in ("once", "twice"):
        w = {1: "once", 2: "twice"}.get(n, WORD_OF[n] + " times")
    else:
        w = WORD_OF[n]
    return w.capitalize() if like[:1].isupper() else w


ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh",
            "twelfth"]
ORDINAL = re.compile(r"\b(" + "|".join(ORDINALS) + r")\b", re.I)
ROMAN_OF = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
ROMAN = re.compile(r"\b(Article|Section|Title|Amendment|Phase)\s+(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\b")
# Real limits, so a wrong choice is never something that can't exist ("the 38th Amendment").
LIMITS = [(re.compile(r"\bamendments?\b", re.I), 27), (re.compile(r"\bArticle\s+[IVX]+\b"), 7),
          (re.compile(r"\bgeneral orders?\b", re.I), 11), (re.compile(r"\b[EOW]-\d\b"), 10)]


def _suffix(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _number_variants(h: str, q: str = "") -> list[str]:
    """Nearby numbers in the same words: "The 19th Amendment" -> "The 18th Amendment"; "Twice" -> "Three times";
    "The eighth general order" -> "The ninth general order"; "Article III" -> "Article IV". An identifier like
    "AR 670-1" gets none: a made-up regulation number isn't a fair choice."""
    if re.search(r"\d-\d", h) or _class(h) == "person":     # "Fifth Lieutenant" isn't a rank
        return []
    cap = min([n for rx, n in LIMITS if rx.search(h) or rx.search(q)] or [10 ** 9])
    spans, how = list(DIGITS.finditer(h)), "digits"
    if not spans:
        spans, how = list(ROMAN.finditer(h)), "roman"
    if not spans:
        spans, how = list(ORDINAL.finditer(h)), "ordinal"
    if not spans:
        words = list(NUM_WORD_RE.finditer(h))
        spans, how = (words if len(words) == 1 else []), "word"         # "Zero six hundred" isn't a count
    if not spans:
        return []
    month = bool(MONTHS.search(h))
    out = []
    for i in range(6):
        text, ok, vals, olds = h, True, [], []
        for m in reversed(spans):
            if how == "digits":
                raw = m.group(2) + (m.group(3) or "")
                v = float(raw.replace(",", ""))
                year = 1600 <= v <= 2099 and v == int(v) and "," not in raw
                if month and not year:                      # a day of the month stays as it is
                    continue
                n = _alt(v, i, year, bool(m.group(4)))
                new = None if n is None or n > cap else m.group(1) + _fmt(n, raw) + (m.group(4) or "")
                start, end = m.start(), m.end()
                if new and re.match(r"(st|nd|rd|th)\b", h[end:]):            # "19th" -> "18th", never "21th"
                    new, end = new + _suffix(int(n)), end + 2
            elif how == "roman":
                v = ROMAN_OF.index(m.group(2))
                n = _alt(v, i, False, False)
                new = None if n is None or n > min(cap, 12) else m.group(1) + " " + ROMAN_OF[int(n)]
                start, end = m.start(), m.end()
            elif how == "ordinal":
                w = m.group(1)
                v = ORDINALS.index(w.lower()) + 1
                n = _alt(v, i, False, False)
                new = None if n is None or n > min(cap, 12) else ORDINALS[int(n) - 1]
                if new and w[:1].isupper():
                    new = new.capitalize()
                start, end = m.start(), m.end()
            else:
                w = m.group(1)
                v = {"once": 1, "twice": 2}.get(w.lower(), NUM_WORDS.get(w.lower(), 0))
                n = _alt(v, i, False, False)
                new = None if n is None or n > cap else _word(n, w)
                start, end = m.start(), m.end()
            if new is None:
                ok = False
                break
            vals.append(n)
            olds.append(v)
            text = text[:start] + new + text[end:]
        # a range keeps its order ("31 to 65" never becomes "46 to 33")
        same_order = sorted(range(len(vals)), key=vals.__getitem__) == sorted(range(len(olds)), key=olds.__getitem__)
        if ok and vals and same_order and norm(text) != norm(h):
            out.append(text)
    return list(dict.fromkeys(out))


# ── picking ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _too_close(f: dict, g: dict) -> bool:
    """A wrong choice that is the right answer, a piece of it, or most of it."""
    if norm(g["head"]) == norm(f["head"]):
        return True
    a, b = f["words"], g["words"]
    if a and b and (a <= b or b <= a or len(a & b) / len(a | b) >= 0.5):
        return True
    if f["kind"] == "list" and g["kind"] == "list" and set(g["items"]) <= set(f["items"]):
        return True
    return False


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _fits(f: dict, g: dict) -> bool:
    """Could g pass for an answer to f's question, on its looks? (Same kind, same sort of thing, similar size.)"""
    if g["kind"] != f["kind"] or g["yn"] or not _shapes_fit(f["shape"], g["shape"]):
        return False
    if f["kind"] in ("term", "number") and g["cls"] != f["cls"]:
        return False
    if f["kind"] == "phrase" and f["cls"] and g["cls"] != f["cls"]:
        return False
    if f["group"] == "who" and _proper_name(f["head"]) != _proper_name(g["head"]):
        return False                                       # a name for a name, a role for a role
    if f["kind"] in ("term", "phrase") and bool(DIGITS.search(g["head"])) != bool(DIGITS.search(f["head"])):
        return False                                       # "9-line MEDEVAC request" for a question about line 9
    if f["kind"] == "number" and g["unit"] != f["unit"]:
        return False
    if f["kind"] == "term" and (abs(g["nwords"] - f["nwords"]) > 2 or not 0.33 <= g["len"] / f["len"] <= 3):
        return False
    if f["kind"] in ("list", "phrase") and not 0.4 <= g["len"] / f["len"] <= 2.5:
        return False
    return True


def wrong_answers(library, card, q: str, a: str, k: int = 3, rng=random) -> list[str] | None:
    """Up to k wrong choices for card's question q (answer a), or None if no fair set exists."""
    two = _binary(q, a)
    if two:
        r = right_choice(q, a)
        return [o for o in two if o != r]
    f = features(q, a)
    out: list[str] = []

    def add(text: str, check: bool = True) -> None:
        g = features("", text)
        if len(out) >= k or norm(text) == norm(f["head"]) or any(norm(text) == norm(x) for x in out):
            return
        if check and _too_close(f, g):
            return
        out.append(text.strip())

    # The card author's own, checked by a person. Shown the way the right answer is: shortened only when the right
    # answer is shortened too ("Leave Entitlement Schedule" next to "Leave and Earnings Statement").
    short = head(a) != a.strip().rstrip(".;:, ")
    for w in getattr(card, "wrong", {}).get(q, []):
        add(head(w) if short else w, check=False)
    if len(out) >= k:
        return out[:k]
    if f["kind"] == "number":
        variants = _number_variants(f["head"], q)[:5]
        for v in rng.sample(variants, min(len(variants), k - len(out))):
            add(v, check=False)                               # differs from the answer only in its numbers, on purpose
        if len(out) >= 2:
            return out
    scored = []
    seen = {norm(f["head"])} | {norm(x) for x in out}
    for c in library.cards:
        for cq, ca in c.quiz:
            if c is card and cq == q:
                continue
            g = features(cq, ca)
            if norm(g["head"]) in seen or g["group"] != f["group"] or not _fits(f, g) or _too_close(f, g):
                continue
            qsim = _jaccard(f["subject"], g["subject"])
            same_branch = c.service == card.service
            if qsim >= 0.75 and same_branch and c is not card:  # the same question on another card: likely right too
                continue
            same_noun = bool(f["noun"]) and f["noun"] == g["noun"]
            # "Who salutes first?" must not offer "General John Raymond" from a Space Force history card: a choice
            # that's related only by topic has to come from the same branch too.
            shared = len(f["subject"] & g["subject"])             # one shared word ("leads") isn't enough
            if not (c is card or (qsim >= 0.2 and shared >= 2) or qsim >= 0.5 or same_noun
                    or (f["cls"] and c.topic == card.topic and same_branch)):
                continue                                        # about something else entirely
            if re.search(r"['’]s$", g["head"]):                 # a fragment ("General John A. Lejeune's")
                continue
            score = 3 * qsim + 2 * same_noun + 1.0 * (c is card) + 0.7 * (c.topic == card.topic) \
                + 0.4 * (c.category == card.category) + 0.3 * same_branch - 0.8 * abs(math.log(g["len"] / f["len"]))
            if f["kind"] == "list":
                score -= 0.3 * abs(len(g["items"]) - len(f["items"]))
            seen.add(norm(g["head"]))
            scored.append((score, g["head"]))
    scored.sort(key=lambda x: -x[0])
    top = [t for _s, t in scored[:k + 2]]                      # the best few, in a different mix each time
    rng.shuffle(top)
    for t in top:
        add(t)
    return out if len(out) >= 2 else None


def build(library, card, q: str, a: str, rng=random) -> list[str] | None:
    """The shuffled choices for one question (the right one included), or None to ask it as a typed answer."""
    wrong = wrong_answers(library, card, q, a, rng=rng)
    if not wrong:
        return None
    choices = wrong + [right_choice(q, a)]
    rng.shuffle(choices)
    return choices
