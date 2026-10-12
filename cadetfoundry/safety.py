"""
Safety checks that run on every message before the AI answers.

  * Crisis: signs of suicidal thoughts, self-harm, abuse or sexual assault ->
    help resources are shown FIRST (before any AI text), and the AI switches to
    a short, caring reply that encourages reaching out now.
  * OPSEC: if someone starts typing unit movements, dates, locations or
    numbers, a gentle reminder is added. Nothing is blocked or reported --
    everything stays on this device.
"""
from __future__ import annotations

import re

# Best-effort pattern matching (security review, 2026-10-11): it can miss indirect or novel wording and it can't know
# anyone's intent. It decides only what Cadet Foundry shows; it never notifies anyone and records nothing beyond the
# person's own private chat. Two levels:
#   * a DISCLOSURE (first person: "I want to...", "my dad hits me") -> help resources first, then a caring reply;
#   * the TOPIC only ("what's the punishment for hazing?", "explain the suicide prevention brief") -> a short,
#     neutral help line, then a normal answer.
# tests/test_safety.py lists what's caught, the false positives accepted on purpose, and known misses.
CRISIS_RE = re.compile(
    r"\b(kill(ing)? myself|kms|unalive( myself)?|end myself|take my (own )?life|"
    r"(want|going|gonna|ready|trying|plan(ning)?) to end (it|it all|my life|everything)|end (it all|my life)|"
    r"don'?t want to (live|be alive|be here|exist|wake up)|"
    r"wan(t|na)( to)? die|wish (i|i'?d) (was|were|had been) dead|wish i (wasn'?t|was never) (born|alive|here)|"
    r"better off (dead|without me)|no (reason|point) (to live|in living|in going on|to go on)|can'?t go on|"
    r"nobody would (care|miss me)|disappear forever|think(ing)? about (dying|death|killing myself|ending it)|"
    r"hurt(ing)? myself|self[- ]?harm(ing)?|cut(ting)? myself|overdos\w*|"
    r"took (a bunch of|too many|all (of )?(my|the)) (pills|meds)|hang myself|shoot myself|"
    r"(i'?m|i am|i feel|feeling|been feeling) (so |really |kind of )?suicidal|"
    r"(thinking|thought|thinking about|considering|planning) (about )?(suicide|sucide|suicde|suiside)|"
    r"(not|don'?t feel) safe at home|(afraid|scared) to go home)\b",
    re.I)
ASSAULT_RE = re.compile(
    r"\b((i was|i've been|i got|got|been) (sexually )?(raped|molested|groped|assaulted|abused|harassed)|raped|"
    r"(sexually )?(assaulted|harassed|molested|groped|abused|raped) me|"
    r"(he|she|they|someone|somebody|my \w+) (hits|beats|chokes|kicks|abuses|hurts|touches|touched|hit|beat) me|"
    r"touched me (without|when i didn'?t|and i didn'?t)|forced me to|made me (do|touch)|"
    r"(is|are|been|being|keeps?|kept) (hazing|harassing|bullying|abusing) me|being (harassed|hazed|bullied|abused))\b",
    re.I)
TOPIC_RE = re.compile(r"\b(suicid\w*|sucid\w*|self[- ]?harm|hazing|sexual (assault|harassment)|abuse\w*|rape|988)\b",
                      re.I)
TOPIC_BANNER = ("*If this is about you or someone you know: call or text **988** (24/7), or talk to a counselor or an "
                "adult you trust. In an emergency, call **911**.*\n\n")

CRISIS_BANNER = (
    "**You matter, and help is available right now.**\n"
    "- Call or text **988** (Suicide & Crisis Lifeline) — free, 24/7. Or text **HOME** to **741741**.\n"
    "- Tell a parent or guardian, a school counselor, your instructor, or another adult you trust **now**. "
    "You don't have to carry this alone.\n"
    "- In immediate danger: call **911**.\n\n"
)
ASSAULT_BANNER = (
    "**What happened to you is not okay, and it is not your fault.**\n"
    "- **RAINN: 800-656-4673** (24/7) · **Childhelp: 800-422-4453** (24/7, for anyone under 18).\n"
    "- Tell a parent or guardian, a school counselor, or another adult you trust. They can help you stay safe.\n"
    "- If you're in danger, call **911**.\n\n"
)

# Used when no AI model is available and the message showed signs of crisis or harm.
CARE_FALLBACK = (
    "I'm here, and I'm glad you said something. Please reach out to a person right now — call or text **988**, or "
    "tell a parent or guardian, a school counselor or another adult you trust. If you're in danger, call **911**. "
    "You don't have to carry this alone."
)

CARE_PROMPT = (
    "You are the Cadet Foundry assistant, a supportive companion for a JROTC Cadet (a high school student). The Cadet may be in crisis "
    "or may have been harmed. Help resources have already been shown above your reply. Speak like a calm, caring "
    "older mentor: short, warm, plain sentences. Acknowledge what they said and that it matters. Ask if they are safe "
    "right now. Encourage them to call or text 988 or to tell a parent or guardian, a school counselor or another "
    "trusted adult right now — and say you're here to keep talking. Never lecture, never judge, never refuse, never "
    "promise to keep a secret, and don't list many resources (they're already shown)."
)

OPSEC_RE = re.compile(
    r"\b(we('re| are)|my unit('s| is)?|our (unit|company|battalion|platoon))\b.{0,40}\b(deploy\w*|moving|shipping out|"
    r"heading|going|leaving|stationed|located|staging|convoy)\b|"
    r"\b(deploy\w*|ship(ping)? out|leaving|convoy|mission)\b.{0,30}\b(on|by|in)\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|"
    r"oct|nov|dec|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}/\d{1,2})|"
    r"\b\d{1,2}[A-Z]{3}\s?[A-Z]{2}\s?\d{4,10}\b|"          # MGRS-style grid coordinates
    r"\b(how many|number of) (soldiers|troops|vehicles)\b.{0,20}\b(we have|in my unit|on base)\b",
    re.I)

OPSEC_NOTE = ("\n\n*OPSEC reminder: details about unit movements, dates, locations or numbers stay off phones, "
              "posts and texts — even with family. This app keeps your notes on this device only.*")


def check(text: str) -> dict:
    t = text or ""
    crisis = bool(CRISIS_RE.search(t))
    assault = bool(ASSAULT_RE.search(t))
    banner = (CRISIS_BANNER if crisis else "") + (ASSAULT_BANNER if assault else "")
    if not banner and TOPIC_RE.search(t):          # the topic, not a disclosure: a neutral line, then a normal answer
        banner = TOPIC_BANNER
    return {
        "care": crisis or assault,
        "banner": banner,
        "opsec": bool(OPSEC_RE.search(t)),
    }
