"""
One chat turn: safety check -> library search -> prompt -> AI -> learn.
"""
from __future__ import annotations

import contextvars
import json
import random
import re
import threading
from typing import Generator

from vanguard import daily, engine, facts, quiz_edits, safety, store
from vanguard.faith import Faith
from vanguard.knowledge import PUB_RE, Library, unsupported_numbers

PERSONA = """You are Vanguard, an offline learning and leadership companion for JROTC Cadets (high school students).
You support their JROTC instructor; you never replace the instructor, the curriculum, school policy or official
sources. You are not an official Army, JROTC or school source.

How you talk: like a calm, encouraging senior Cadet leader — respectful, direct, plain words a high school student
understands. Answers are complete but not padded: give every step, number and rule the library gives, then stop.
Use the Cadet's name if you know it. Encourage, don't lecture, never shame.

How you answer:
- Base answers on the LIBRARY passages below. When you use one, cite it in parentheses, e.g. (AR 670-1). If the
  library doesn't cover the question, say so plainly and tell them to ask their instructor.
- Standards change and programs differ. For anything with numbers or rules, tell them to confirm with their
  instructor.
- Health or injury: the school nurse, a parent or guardian, or a doctor. Personal struggles: a school counselor, a
  parent or guardian, or another trusted adult. You never diagnose or judge.
- You never grade, discipline, decide promotions, or speak for the instructor.
- Never help with cheating, hurting anyone, or breaking school rules. Explain why and point to the right help.
- Never invent or reveal sensitive information.
- For study: quiz them, make memory tricks, break things into steps.
- Faith: respect every tradition and none; never push a religion.
"""


def _my_people() -> str:
    """The Cadet's own support contacts (Check-in -> My people), shown right under the crisis lines."""
    people = daily.support()
    if not people:
        return ""
    return "**Your people:**\n" + "\n".join(
        f"- {p['role']}: **{p['name']}**" + (f" — {p['phone']}" if p["phone"] else "") + (f" ({p['note']})" if p["note"] else "")
        for p in people) + "\n\n"


# Always in the prompt: small models invent acronym expansions ("AIT = Airborne Infantry Training"). These are the
# exact meanings (FM 7-22 glossary; ATP 7-22.02 for the AFT) -- the same as the "Army Terms" study card.
ARMY_TERMS = """## JROTC AND MILITARY TERMS (exact meanings — never expand an acronym any other way)
JROTC = Junior Reserve Officers' Training Corps (the high school program the Cadet is in) · LET = Leadership
Education and Training (the JROTC course level, LET 1 to LET 4) · SAI = Senior Army Instructor · NCO =
noncommissioned officer · MOS = military occupational specialty (an Army job) · BCT = basic combat training ·
AIT = advanced individual training (Army job training after BCT) · H2F = holistic health and fitness · AFT = Army
Fitness Test (the Army's fitness test for Soldiers; it replaced the ACFT)
"""

ANSWER_RULES = """## Before you answer
1. Answer from the LIBRARY above. STUDY CARDS are checked summaries — trust them first. MANUAL PAGES are raw text
   and may be about something else that only shares a word with the question; ignore those.
2. Use only steps, numbers and rules that appear in the LIBRARY. Never add a step of your own — especially for
   weapons, first aid, safety or pay.
3. If the LIBRARY gives steps, list all of them, numbered, in the same order.
4. Name the source in parentheses, e.g. (TC 3-22.9) or (AR 670-1).
5. If the LIBRARY doesn't answer it, say so and tell them who to ask.
6. Expand an acronym only as ARMY TERMS or the LIBRARY gives it; if you don't know it, don't guess. The fitness
   test is the Army Fitness Test (AFT) — never call it the PFT or APFT.
7. Use what you know about the Cadet (their LET level, goals and interests) to make the answer fit them.
8. Talk to the Cadet as "you". Never mention file names.
"""

# When Vanguard already showed the answer from its own data, the AI may only add a little help around it -- it
# never restates or changes the facts (the AFT answer once listed pull-ups right under the checked answer).
COACH_RULES = """## Your job now
The Cadet already sees the ANSWER above, from Vanguard's official data. Do NOT repeat it, list it again, change it,
or add any numbers, events, steps or rules. Write at most 3 short sentences that help them use it: why it matters,
a practical tip, or who to ask. Talk to them as "you". If there's nothing useful to add, write one short sentence
of encouragement.
"""

# Questions that ask for a fact. When the library has nothing on one, Vanguard says so instead of letting the AI guess.
_FACTUAL = re.compile(r"^\s*(what|which|when|where|who|how (many|much|long|often|far|fast|old|heavy))\b"
                      r"|\b(minimum|maximum|required|requirement|regulation|standard|policy)s?\b", re.I)

# Chatbot filler small models tack onto every answer.
_BOILERPLATE = re.compile(r"feel free to ask|if you have any (other|more|further) questions|hope this helps|let me know\b",
                          re.I)

LIBRARY_GAP = ("Vanguard's library doesn't cover that, so I won't guess. Ask your instructor.")


FAMILY_NOTE = """## Who you're talking with
This profile belongs to a PARENT OR GUARDIAN of a Cadet, not a Cadet. Talk to them as a supportive guide: explain
JROTC and military terms plainly, and help them understand and support their Cadet. For questions about their
Cadet's grades, standing or the program, point them to the JROTC instructor and the school.
"""


_VAGUE = re.compile(r"\b(what (do|should) i (need to )?know|what to expect|how (do|can) i prepare|get ready|any tips|what('s| is) next)\b", re.I)

# "How does this work?" is about Vanguard itself -- answered the same way every time, no AI, no library.
_APP_HELP = re.compile(r"\b(how (does|do) (this|vanguard|it|you) work|what (am i|do i|should i) (supposed to )?do with (this|it|vanguard)"
                       r"|what can (you|vanguard) do|how do i use (this|vanguard|it|you)|what is (this|vanguard)( app)?\W*$)", re.I)


def app_help_question(text: str) -> bool:
    """Short questions about Vanguard itself ("How does this work?"), not "how does a tourniquet work"."""
    return len(text) <= 90 and bool(_APP_HELP.search(text)) or text.strip().lower() in ("help", "help?", "/help")


APP_HELP = """Here's how Vanguard works:

- **📘 Learn** — study cards, quizzes, timed exams and the library (founding documents, Army history, classics). Answers come from sources stored on this device, with the source shown. A **✅ Checked answer** matched a study card checked against its source.
- **🧭 Lead** — leadership scenarios and your leadership log.
- **💪 Train** — your fitness history and goals, measured against your own last result.
- **🤝 Serve** — your service projects and hours, and Explore Military Service if you want to learn what serving is like.
- **📈 Progress** — your growth over time.
- **💬 Ask** (top of the screen) — ask a question about anything in the library. **👤** is your profile, PIN and backup.

Everything stays on this device. Vanguard supports your instructor — your instructor and official sources come first."""


def used_cites(reply: str, cites: list[dict], checked: dict | None = None) -> list[dict]:
    """Only the sources the answer actually names (a publication number like AR 600-25, or the source's title).
    The library hands the AI several passages; showing all of them under every answer looked like evidence for
    things the answer never said."""
    text = re.sub(r"\s+", " ", reply)
    named = text.lower()
    if checked:
        named += " " + checked["source"].lower()

    def used(c: dict) -> bool:
        pubs = re.findall(r"\b(?:AR|FM|TC|ATP|ADP|DA PAM|GTA|EO)\s?\d[\d.-]*", c["source"], re.I)
        if pubs:
            return any(re.sub(r"\s+", " ", x).lower() in named for x in pubs)
        head = c["source"].split(",")[0].strip().lower()
        return bool(head) and head in named or c.get("where", "").lower() in named

    return [c for c in cites if used(c)]


# Vanguard's own trust markers. Only Vanguard adds them; any copy in AI text is removed.
_MARKERS = re.compile(r"✅\s*(\*\*)?\s*checked answers?:?\s*(\*\*)?\s*|\*?\*?checked answers?:\*?\*?\s*|✅\s*|⚠️\s*\*?\s*"
                      r"(not found in vanguard's sources|vanguard's library has no)[^\n]*\n?|📄\s*", re.I)


def strip_markers(text: str) -> str:
    return _MARKERS.sub("", text or "")


# Small models invent official-looking links ("army.mil/ScoringScale.pdf"), and on an offline device no link opens
# anyway. A markdown link keeps its words; a bare web address is dropped.
_MD_LINK = re.compile(r"\[([^\]\n]{1,120})\]\(\s*(?:https?://|www\.)[^)\s]*\s*\)", re.I)
_URL = re.compile(r"\(?\b(?:https?://|www\.)[^\s)\]]+\)?", re.I)


# Library file names leak into AI text ("AR_621-5_Army_Continuing_Education_System.md") -> "AR 621-5".
_FILE = re.compile(r"\b(AR|FM|TC|ATP|ADP|DA_PAM|GTA)_(\d[\w.\-]*?)(?:_[A-Za-z0-9\-]+)*\.(?:md|txt)\b")
# Small models drift into talking about the Cadet ("they should check with their finance office").
_THEY = re.compile(r"\bthey (should|can|could|will need to|need to|may want to|might want to) "
                   r"(check|confirm|ask|contact|talk|see|visit|refer|reach out)", re.I)


# Copied from Vanguard's own formatting or the prompt: a trailing "— *DFAS pay tables*", "STUDY CARD (checked
# summary)", a manual's paragraph number at the start of a line ("14-8 The Deadlift ...").
_SOURCE_TAIL = re.compile(r"\s*—\s*\*[^*\n]{2,120}\*?(?=\s*$)|\s*—\s*\([^)\n]{2,60}\)(?=\s*$)")
_PROMPT_LABEL = re.compile(r"\s*[\[(]?(STUDY CARD \(checked summary\)|MANUAL PAGE \([^)]*\))[\])]?", re.I)
_PARA_NUM = re.compile(r"(?m)^\s*\d{1,2}-\d{1,3}\.?\s+(?=[A-Z])")


def strip_ai_text(text: str) -> str:
    text = _URL.sub("", _MD_LINK.sub(r"\1", strip_markers(text)))
    text = _FILE.sub(lambda m: f"{m.group(1).replace('_', ' ')} {m.group(2)}", text)
    text = _PROMPT_LABEL.sub("", text)
    return _THEY.sub(lambda m: f"you {m.group(1)} {m.group(2)}", text)


def tidy_sentence(piece: str) -> str:
    """Per-sentence cleanup once a whole sentence is in hand."""
    return _PARA_NUM.sub("", _SOURCE_TAIL.sub("", piece))


def for_history(text: str) -> str:
    """An earlier answer as the AI sees it again: Vanguard's badge and '— *source*' formatting removed, so the model
    doesn't learn to copy them."""
    text = re.sub(r"✅\s*\*\*Checked answer:\*\*\s*(.*?)\s*—\s*\*([^*\n]+)\*", r"\1 (\2)", text or "", flags=re.S)
    return strip_markers(text)


class SentenceGate:
    """Releases AI text one sentence (or line) at a time, and drops any sentence `keep` rejects -- one with a number
    or a manual Vanguard's sources don't back up. The Cadet never sees a made-up figure, and never has to be told
    to double-check one."""
    _END = re.compile(r"(?<!\b[A-Z])[.!?](?=\s)|\n")          # not inside "U.S." or after an initial

    def __init__(self, keep):
        self.keep, self.buf, self.sent = keep, "", ""

    def _pass(self, piece: str) -> str:
        if piece.strip():
            piece = tidy_sentence(piece)
            if not piece.strip() or not self.keep(piece):
                return ""
        elif not self.sent or self.sent.endswith("\n\n"):     # no run of blank lines where sentences were dropped
            return ""
        self.sent = (self.sent + piece)[-4:]
        return piece

    def feed(self, text: str) -> str:
        self.buf += text
        out = []
        while True:
            m = self._END.search(self.buf)
            if not m:
                break
            piece, self.buf = self.buf[:m.end()], self.buf[m.end():]
            out.append(self._pass(piece))
        return "".join(out)

    def flush(self) -> str:
        piece, self.buf = self.buf, ""
        return self._pass(piece) if piece else ""


class MarkerFilter:
    """Streams AI text with Vanguard's trust markers and any web links removed. A marker or link can arrive split
    across chunks ("✅ **Check" + "ed answer:**"), so text is only released at a safe point: a space that isn't
    inside a link, a bold run, or anything after ✅ / ⚠️ on the same line. The rest waits for the next chunk."""
    HOLD = 100
    _OPEN = re.compile(r"(\[[^\]\n]*|\([^)\s]*|✅[^\n]*|⚠️[^\n]*|📄[^\n]*|\*\*[^*\n]*|(?:https?://|www\.)\S*)$", re.I)

    def __init__(self):
        self.buf = ""

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        cut = self.buf.rfind(" ", 0, max(0, len(self.buf) - self.HOLD) + 1)
        if cut <= 0:
            return ""
        head = self.buf[:cut]
        unfinished = self._OPEN.search(head)
        if unfinished:                                # don't release half a link or marker
            cut = unfinished.start()
            head = self.buf[:cut]
        self.buf = self.buf[cut:]
        return strip_ai_text(head)

    def flush(self) -> str:
        out, self.buf = strip_ai_text(self.buf), ""
        return out


class Brain:
    def __init__(self, library: Library, faith: Faith | None = None):
        self.library = library
        self.faith = faith

    def _messages(self, text: str, care: bool, family: bool = False,
                  checked: dict | None = None) -> tuple[list[dict], list[dict]]:
        if care:
            system = safety.CARE_PROMPT
            sources: list[dict] = []
        else:
            lib, sources = self.library.context(text)
            parts = [PERSONA]
            if family:
                parts.append(FAMILY_NOTE)
            prof = store.profile_text()
            if prof:
                parts.append("## The Cadet\n" + prof)
            mems = store.memories()[-25:]
            if mems:
                parts.append("## What you remember about them\n" + "\n".join(f"- {m['text']}" for m in mems))
            log = store.log_text(8)
            if log and re.search(r"\b(pt|score|run|plank|push|deadlift|qual|range|progress|log|goal|improv)\w*", text, re.I):
                parts.append("## Their logbook (recent)\n" + log)
            if self.faith and self.faith.catalog and store.module_on("faith"):
                preferred = [x for x in (store.profile().get("faith_texts") or "").split(",") if x]
                scripture = self.faith.context_for(text, preferred)
                if scripture:
                    parts.append("## SCRIPTURE (exact text — quote it, name the translation)\n" + scripture)
            parts.append(ARMY_TERMS)
            parts.append("## LIBRARY (official sources — cite them)\n" + (lib or "(nothing in the library matched this question)"))
            if checked:
                parts.append("## ANSWER (already shown to the Cadet)\n"
                             f"Q: {checked.get('question', text)}\nA: {checked['answer']} ({checked['source']})")
            parts.append(COACH_RULES if checked else ANSWER_RULES)   # last, where small models pay the most attention
            system = "\n\n".join(parts)
        msgs = [{"role": "system", "content": system}]
        # Earlier answers go back to the model without Vanguard's trust markers -- otherwise it copies
        # "✅ Checked answer:" into its own text, and a made-up answer looks verified.
        msgs += [{"role": m["role"], "content": for_history(m["content"]) if m["role"] == "assistant" else m["content"]}
                 for m in store.history()[-8:]]
        msgs.append({"role": "user", "content": text})
        return msgs, sources

    def chat(self, text: str, family: bool = False) -> Generator[dict, None, None]:
        """Yields {"t": text} chunks, then {"done": True, "sources": [names], "cites": [passages]}."""
        text = (text or "").strip()[:4000]
        if not text:
            return
        check = safety.check(text)
        if not check["care"] and app_help_question(text):
            store.add_history("user", text)
            store.add_history("assistant", APP_HELP)
            yield {"t": APP_HELP}
            yield {"done": True, "sources": [], "cites": []}
            return
        if check["banner"]:
            yield {"t": check["banner"] + _my_people(), "banner": True}
        # Facts come from Vanguard's own data, not the AI: pay, BAS, AFT scores, LES blocks and Army jobs are answered
        # straight from the tables, and a question asked like a study-card quiz question gets that checked answer,
        # word for word. The AI may only add a few sentences of help around it.
        checked = None if check["care"] else (facts.direct_answer(text, self.library.library_dir)
                                              or self.library.checked_answer(text))
        asked_unknown = [] if check["care"] or checked else self.library.unknown_pubs(text)
        if asked_unknown:
            # "What does AR 999-99 say?" -- Vanguard doesn't have it, so it says so instead of letting the AI guess.
            names = ", ".join(f"**{x}**" for x in asked_unknown)
            gap = f"Vanguard's library doesn't have {names}, so I can't tell you what it says — and I won't guess."
            topic = re.sub(r"\b(say|says|said|tell|tells|mean|means|state|states)\b", " ", PUB_RE.sub(" ", text), flags=re.I)
            said = self._library_says(topic)                 # "...about haircuts", not the made-up number
            if said:
                gap += "\n\nHere's what Vanguard's library has on this:\n\n" + said
            yield {"t": gap}
            store.add_history("user", text)
            store.add_history("assistant", gap)
            yield {"done": True, "sources": [], "cites": [], "ai": False}
            return
        msgs, sources = self._messages(text, check["care"], family, checked)
        reply, fell_back = [], False
        if checked:
            first = f"✅ **Checked answer:** {checked['answer']} — *{checked['source']}*\n\n"
            reply.append(first)
            yield {"t": first, "checked": checked}
        # Library-only mode (set by the device admin): no AI writing at all -- only checked answers and the
        # exact text of the manuals. Someone in crisis still gets the care response below.
        mode = store.ai_mode()
        library_only = mode == "off"                     # AI Off: checked answers and quoted library text only
        # A factual question the library has nothing on: say so, don't guess. (Not for faith questions, which
        # answer from scripture, or questions about the Cadet's own log and profile.)
        # In Library-only mode (the default) that applies to every question, not only factual ones.
        gap = (not check["care"] and not checked and not sources and (mode != "ai" and len(text.split()) >= 4 or bool(_FACTUAL.search(text)))
               and "## SCRIPTURE" not in msgs[0]["content"] and not re.search(r"\b(my|me|i)\b", text, re.I))
        given = "\n".join(m["content"] for m in msgs)

        answer_words = (set(re.findall(r"[a-z]{3,}", (checked["answer"] + " " + checked["source"]).lower()))
                        if checked else set())

        def keep(sentence: str) -> bool:
            if checked:
                # Help around a data answer is a few plain sentences: no numbers, no lists or headings, and
                # nothing that just repeats the answer the Cadet already sees.
                s = sentence.strip()
                if re.search(r"\d", s) or re.match(r"([-*•]|\d+\.)\s", s) or s.endswith(":") or len(s) < 12:
                    return False
                words = re.findall(r"[a-z]{3,}", s.lower())
                if words and sum(w in answer_words for w in words) / len(words) >= 0.6:
                    return False
            if _BOILERPLATE.search(sentence):
                return False
            return not unsupported_numbers(sentence, given) and not self.library.unknown_pubs(sentence)

        try:
            if checked and checked.get("final"):
                raise LookupError("complete answer")
            if gap:
                raise LookupError("not in the library")
            if library_only:
                raise RuntimeError("library-only mode")
            clean = MarkerFilter()                       # the AI can never write the ✅ badge or a ⚠️ notice
            gate = SentenceGate(keep if not check["care"] else (lambda s: True))
            for chunk in engine.stream(msgs, max_tokens=500 if check["care"] else 250 if checked else 1200):
                chunk = gate.feed(clean.feed(chunk))
                if chunk:
                    reply.append(chunk)
                    yield {"t": chunk}
            tail = gate.feed(clean.flush()) + gate.flush()
            if tail:
                reply.append(tail)
                yield {"t": tail}
        except LookupError:
            fell_back = True
            if gap:
                reply.append(LIBRARY_GAP)
                yield {"t": LIBRARY_GAP}
        except Exception:
            # No AI available. Someone in crisis must never get library search results -- only care.
            if check["care"]:
                fallback = safety.CARE_FALLBACK
            elif checked:                                # the checked answer above already answers it
                fallback = ("*AI is off: this is the checked answer on its own. Open Learn to read the whole card.*"
                            if library_only else
                            "*The offline AI isn't running, so this is the checked answer on its own. Open Learn to read the whole card.*")
            else:
                fallback = self._offline_fallback(text, library_only)
            fell_back = True
            reply.append(fallback)
            yield {"t": fallback}
        if check["opsec"] and not check["care"]:
            yield {"t": safety.OPSEC_NOTE}
        full = "".join(reply)
        store.add_history("user", text)
        store.add_history("assistant", full)
        if not check["care"]:
            ctx = contextvars.copy_context()             # keep this Cadet's profile in the background job
            threading.Thread(target=ctx.run, args=(self._learn, text, full), daemon=True).start()
        if not fell_back:                                # the offline fallback quotes every passage it shows
            sources = used_cites(full, sources, checked)
        yield {"done": True, "sources": list(dict.fromkeys(c["source"] for c in sources)), "cites": sources,
               "ai": not fell_back and not check["care"]}      # the app labels AI-written text

    _SIMPLER = ("You are Vanguard. Rewrite the answer below for a Cadet who wants it in plain words. Use short "
                "sentences and everyday words. The first time an acronym or Army term appears, say what it means in "
                "a few words. Keep every fact, number, rule and source name (like AR 670-1) exactly as given. Do not "
                "add anything that isn't in the answer. Keep it under 150 words. Reply with the rewrite only.")

    def simplify(self, answer: str) -> Generator[dict, None, None]:
        """Re-say an answer in plain words. Needs an AI model; adds no new facts and isn't saved to history."""
        answer = (answer or "").strip()[:4000]
        if not answer:
            return
        if store.ai_mode() == "off":
            yield {"t": "AI is turned off on this device, so Vanguard doesn't reword answers."}
            yield {"done": True}
            return
        msgs = [{"role": "system", "content": self._SIMPLER}, {"role": "user", "content": strip_markers(answer)}]
        try:
            clean = MarkerFilter()                       # same rules as Ask: no badges, no invented links
            for chunk in engine.stream(msgs, max_tokens=400):
                chunk = clean.feed(chunk)
                if chunk:
                    yield {"t": chunk}
            tail = clean.flush()
            if tail:
                yield {"t": tail}
        except Exception:
            yield {"t": "Simpler explanations need the offline AI model, and it isn't running right now."}
        yield {"done": True}

    def _library_says(self, text: str) -> str:
        """The top library matches, quoted whole: a checked card's body, or the manual page's own text."""
        out = []
        for _s, p in self.library.search(text, k=2):
            card = next((c for c in self.library.cards if p.card and c.title == p.where), None)
            body = card.body if card else p.text           # a whole checked card, never its quiz lines
            out.append(f"**{p.where}** ({p.source.split(' (')[0]})\n\n{body.strip()}")
        return "\n\n---\n\n".join(out)

    def _offline_fallback(self, text: str, library_only: bool = False) -> str:
        said = self._library_says(text)
        msg = ("**AI is off** — answers come straight from the library and study cards. "
               "Here's what the library says:\n\n" if library_only else
               "I can't reach an AI model right now (the local AI isn't running). "
               "Here's what the library says:\n\n")
        if not said:
            return msg.replace("Here's what the library says:\n\n", "") + \
                   "I didn't find this in the library either. Check Learn, or ask your instructor."
        return msg + said

    _LEARN = ("From this exchange, list 0-2 lasting facts about the Cadet that will help in future conversations "
              "(goals, struggles, job, progress, preferences, family they mention). Never record anything about unit "
              "locations, movements or dates. Never guess. Reply with a JSON array of short strings only, or [].")

    def _learn(self, user: str, reply: str) -> None:
        if len(user) < 20:
            return
        raw = engine.quick([{"role": "system", "content": self._LEARN},
                            {"role": "user", "content": f"Cadet: {user[:1500]}\nVanguard: {reply[:1500]}"}], 200)
        m = re.search(r"\[.*\]", raw or "", re.S)
        try:
            items = json.loads(m.group(0)) if m else []
        except Exception:
            items = []
        for it in items[:2]:
            if isinstance(it, str) and not safety.OPSEC_RE.search(it):
                store.remember(it, "learned")

    # ── study ───────────────────────────────────────────────────────────────
    def quiz(self, topic: str = "", n: int = 10) -> list[dict]:
        """Flashcards weighted toward questions the Cadet has missed or never seen."""
        stats = store.study()
        pool = []
        for c in self.library.cards:
            if topic and topic not in (c.topic, c.id, c.category, c.service):   # a topic, card, category or service
                continue
            for i, (q, a) in enumerate(c.quiz):
                qid = f"{c.id}#{i}"
                edited = quiz_edits.apply(qid, q, a)          # the instructor's version, or hidden
                if edited is None:
                    continue
                q, a = edited
                s = stats.get(qid, {})
                weight = 3 + 4 * s.get("wrong", 0) - min(2, s.get("right", 0)) if s else 5
                pool.append((max(1, weight), {"id": qid, "q": q, "a": a, "card": c.title, "topic": c.topic,
                                              "source": c.source}))
        picked = []
        while pool and len(picked) < n:
            total = sum(w for w, _ in pool)
            r, acc = random.uniform(0, total), 0
            for i, (w, item) in enumerate(pool):
                acc += w
                if acc >= r:
                    picked.append(item)
                    pool.pop(i)
                    break
        return picked

    def quiz_item(self, qid: str) -> dict | None:
        """One quiz question by its id ("card_id#index"), only from cards this request may see."""
        cid, _, idx = (qid or "").partition("#")
        c = self.library.card(cid)
        if not c or not idx.isdigit() or int(idx) >= len(c.quiz):
            return None
        edited = quiz_edits.apply(f"{c.id}#{idx}", *c.quiz[int(idx)])
        if edited is None:                                 # hidden by the instructor
            return None
        q, a = edited
        return {"id": f"{c.id}#{idx}", "q": q, "a": a, "card": c.title, "topic": c.topic, "source": c.source}

    def for_screen(self, items: list[dict], mode: str = "") -> list[dict]:
        """Quiz questions as the screen gets them: never the answer. Practice mode adds four choices (the right one
        and three from other questions), shuffled; challenge mode (typed answers) has none."""
        from vanguard import exam
        out = []
        for x in items:
            q = {k: v for k, v in x.items() if k != "a"}
            if mode == "mc":
                card = self.library.card(x["id"].partition("#")[0])
                choices = (exam._choices(self.library, card, x["a"]) if card else []) + [x["a"]]
                random.shuffle(choices)
                q["choices"] = choices
            out.append(q)
        return out

    def progress(self) -> dict:
        stats = store.study()
        out = {}
        for c in self.library.cards:
            right = sum(stats.get(f"{c.id}#{i}", {}).get("right", 0) > 0 for i in range(len(c.quiz)))
            out[c.topic] = out.get(c.topic, [0, 0])
            out[c.topic][0] += right
            out[c.topic][1] += len(c.quiz)
        return {t: {"known": k, "total": n} for t, (k, n) in out.items()}
