"""
Letters home: an address book, AI-drafted letters from the Soldier's own notes,
and an OPSEC check before a letter goes out. All stored on this device.
"""
from __future__ import annotations

import re
import time
import uuid

from vanguard import engine, safety, store

# Extra things worth a second look in a letter (on top of safety.OPSEC_RE)
_LETTER_FLAGS = [
    (re.compile(r"\b(deploy\w*|ship(ping)? out|leav(e|ing) for|head(ing)? (to|out)|convoy|mission|operation)\b", re.I),
     "mentions movements or missions"),
    (re.compile(r"\b(on|by|until|before|after|the)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2}(st|nd|rd|th)?\b|"
                r"\b\d{1,2}(st|nd|rd|th)\s+of\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|"
                r"\b\d{1,2}/\d{1,2}(/\d{2,4})?\b", re.I), "gives a specific date"),
    (re.compile(r"\b\d+\s+(other\s+)?(soldiers|troops|guys|people|men|women|personnel|of us|platoons|companies|"
                r"vehicles|trucks|tanks|helicopters|aircraft|weapons|rounds)\b", re.I),
     "gives numbers of people or equipment"),
    (re.compile(r"\b(grid|coordinates?|mgrs|\d{1,2}[A-Z]{3}\s?[A-Z]{2}\s?\d{4,10})\b", re.I), "gives a location or grid"),
    (re.compile(r"\b(password|access code|cac|badge number|security procedure|guard schedule|gate code)\b", re.I),
     "mentions security details"),
]


def contacts() -> list[dict]:
    return store.read_json("contacts.json", [])


def save_contact(data: dict) -> dict:
    rows = contacts()
    cid = data.get("id") or uuid.uuid4().hex[:8]
    row = {"id": cid, "name": str(data.get("name", "")).strip()[:80],
           "relation": str(data.get("relation", "")).strip()[:40],
           "address": str(data.get("address", "")).strip()[:400]}
    rows = [r for r in rows if r["id"] != cid] + [row]
    store.write_json("contacts.json", rows)
    return row


def delete_contact(cid: str) -> bool:
    rows = contacts()
    keep = [r for r in rows if r["id"] != cid]
    store.write_json("contacts.json", keep)
    return len(keep) != len(rows)


def letters() -> list[dict]:
    return sorted(store.read_lines("letters.jsonl"), key=lambda r: r.get("t", 0), reverse=True)


def save_letter(data: dict) -> dict:
    rows = store.read_lines("letters.jsonl")
    lid = data.get("id") or uuid.uuid4().hex[:8]
    row = {"id": lid, "to": str(data.get("to", ""))[:80], "text": str(data.get("text", ""))[:20000],
           "date": data.get("date") or time.strftime("%Y-%m-%d"), "t": time.time()}
    rows = [r for r in rows if r["id"] != lid] + [row]
    store.write_lines("letters.jsonl", rows)
    return row


def delete_letter(lid: str) -> bool:
    rows = store.read_lines("letters.jsonl")
    keep = [r for r in rows if r["id"] != lid]
    store.write_lines("letters.jsonl", keep)
    return len(keep) != len(rows)


def opsec_check(text: str) -> list[dict]:
    """Sentences that may share too much, with why."""
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        s = sentence.strip()
        if not s:
            continue
        why = [reason for rx, reason in _LETTER_FLAGS if rx.search(s)]
        if safety.OPSEC_RE.search(s) and "mentions movements or missions" not in why:
            why.append("may describe unit movements or locations")
        if why:
            out.append({"sentence": s, "why": sorted(set(why))})
    return out


DRAFT_PROMPT = """You help a U.S. Army Soldier write a personal letter home. Write it in the Soldier's own voice,
first person, warm and natural, like a real handwritten letter — not formal, not cheesy. Use ONLY the Soldier's notes
for facts; don't invent events, people or feelings they didn't mention. Keep it OPSEC-safe: no unit movements,
specific future dates, locations beyond what they wrote, numbers of troops or equipment, or security details — if
their notes include those, leave them out. About 150-300 words unless the notes ask otherwise. Start with
"Dear <name>," and end with a sign-off and the Soldier's first name if given. Reply with the letter only."""


def draft(to_name: str, relation: str, notes: str) -> str:
    prof = store.profile()
    me = prof.get("name", "")
    msgs = [{"role": "system", "content": DRAFT_PROMPT},
            {"role": "user", "content": f"Letter to: {to_name or 'my family'}" + (f" ({relation})" if relation else "") +
                                        (f"\nFrom: {me}" if me else "") + (f" ({prof.get('stage')})" if prof.get("stage") else "") +
                                        f"\n\nMy notes:\n{notes[:3000]}"}]
    try:
        return "".join(engine.stream(msgs, max_tokens=700)).strip()
    except Exception:
        return ""
