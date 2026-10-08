"""
Offline voice input (optional): speech-to-text with Vosk, entirely on this device.

Browsers' built-in speech recognition sends audio to cloud servers, so Recruit
doesn't use it. Instead the page records 16 kHz mono audio and sends it here;
Vosk turns it into text locally. Nothing leaves the device.

Setup (once, on the machine that prepares the device): python tools/install_voice.py
If Vosk or its model isn't installed, voice input is simply unavailable.
"""
from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

MODEL_DIR = Path(__file__).parent.parent / "voice-model"
_model = None
_lock = threading.Lock()


def available() -> bool:
    if not MODEL_DIR.exists():
        return False
    try:
        import vosk  # noqa: F401
        return True
    except Exception:
        return False


def _get_model():
    global _model
    with _lock:
        if _model is None:
            import vosk
            vosk.SetLogLevel(-1)
            _model = vosk.Model(str(MODEL_DIR))
        return _model


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                       "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}


def words_to_digits(text: str) -> str:
    """'article one hundred twelve a' -> 'article 112 a'; 'fifteen' -> '15' (so the library's numbers match)."""
    words = text.split()
    out, num, active, last = [], 0, False, ""     # last: "unit" | "tens" | "hundred"

    def flush():
        nonlocal num, active, last
        if active:
            out.append(str(num))
        num, active, last = 0, False, ""

    for i, word in enumerate(words):
        w = word.lower()
        nxt = words[i + 1].lower() if i + 1 < len(words) else ""
        if w in _UNITS:
            v = _UNITS[w]
            # a unit joins "twenty" (-> 25) or "one hundred" (-> 112); otherwise it's a new number
            if active and not ((last == "tens" and v < 10) or (last == "hundred" and num % 100 == 0)):
                flush()
            num += v; active, last = True, "unit"
        elif w in _TENS:
            if active and not (last == "hundred" and num % 100 == 0):
                flush()
            num += _TENS[w]; active, last = True, "tens"
        elif w == "hundred" and active and last in ("unit", "tens") and num < 10:
            num *= 100; last = "hundred"
        elif w == "and" and last == "hundred" and (nxt in _UNITS or nxt in _TENS):
            continue                                  # "one hundred and five"
        else:
            flush()
            out.append(word)
    flush()
    return " ".join(out)


# Sounds the small English model often confuses, in a military context.
_FIXES = [(r"\bgreat (coordinate|square|reference|line|zone)", r"grid \1"), (r"\bgreat\b(?= \d)", "grid"),
          (r"\b(eight|8) digit great\b", r"\1 digit grid"), (r"\bart (\d+)", r"article \1"),
          (r"\bu c m j\b", "UCMJ"), (r"\bo p sec\b", "OPSEC"), (r"\ba f t\b", "AFT"), (r"\bm o s\b", "MOS"),
          (r"\bt s p\b", "TSP"), (r"\bl e s\b", "LES"), (r"\bsharp\b", "SHARP"), (r"\bait\b", "AIT")]


def tidy(text: str) -> str:
    import re
    t = words_to_digits(text)
    for pat, rep in _FIXES:
        t = re.sub(pat, rep, t, flags=re.I)
    return t[:1].upper() + t[1:] if t else t


def _recognize(pcm16_b64: str, rate: int, grammar: list[str] | None = None) -> str:
    if not available():
        raise RuntimeError("Voice input isn't installed on this device.")
    audio = base64.b64decode(pcm16_b64)
    if len(audio) > rate * 2 * 90:                        # at most 90 seconds (a full creed recitation)
        audio = audio[: rate * 2 * 90]
    import vosk
    rec = (vosk.KaldiRecognizer(_get_model(), rate, json.dumps(grammar + ["[unk]"])) if grammar
           else vosk.KaldiRecognizer(_get_model(), rate))
    for i in range(0, len(audio), 8000):
        rec.AcceptWaveform(audio[i:i + 8000])
    return json.loads(rec.FinalResult()).get("text", "").strip()


def transcribe(pcm16_b64: str, rate: int = 16000) -> str:
    """16-bit little-endian mono PCM (base64) -> text."""
    return tidy(_recognize(pcm16_b64, rate))


# ── Radio mode: the recognizer only listens for radio words, which makes it far more accurate ──
# NATO/ICAO phonetic alphabet; numbers as said on the radio. (The small model has no "juliett",
# "xray" or "fower", so those are heard as "juliet", "x ray" and "four".)
NATO = {w: w[0].upper() for w in "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike "
        "november oscar papa quebec romeo sierra tango uniform victor whiskey yankee zulu".split()}
RADIO_DIGITS = {"zero": "0", "one": "1", "two": "2", "three": "3", "tree": "3", "four": "4", "five": "5", "fife": "5",
                "six": "6", "seven": "7", "eight": "8", "nine": "9", "niner": "9"}
CALL_WORDS = "bulldog saber viking dragon warrior ranger".split()
# Only radio words -- "I have a" is left out on purpose: "I" and "a" would be read as the letters I and A.
RADIO_GRAMMAR = sorted(set(NATO) | set(RADIO_DIGITS) | {"x", "ray", "line", "break", "over", "out", "decimal", "point",
                                                        "medevac", "request"} | set(CALL_WORDS))


def radio_tokens(text: str) -> list[str]:
    """'one seven sierra papa ... x ray' -> ['1', '7', 'S', 'P', ..., 'X']; other words upper-cased."""
    words, out, i = text.lower().split(), [], 0
    while i < len(words):
        w = words[i]
        if w == "x" and i + 1 < len(words) and words[i + 1] == "ray":
            out.append("X"); i += 2; continue
        if w in ("x", "ray", "[unk]"):              # half of "x ray", or noise
            i += 1; continue
        out.append(NATO.get(w) or RADIO_DIGITS.get(w) or ("." if w in ("decimal", "point") else w.upper()))
        i += 1
    return out


def nine_line(text: str) -> dict:
    """Split a spoken 9-line MEDEVAC request into its lines: 'LINE ONE ... LINE TWO ...'."""
    toks = radio_tokens(text)
    lines: dict[str, list[str]] = {}
    current, preamble = None, []
    i = 0
    while i < len(toks):
        if toks[i] == "LINE":
            if i + 1 < len(toks) and toks[i + 1].isdigit() and toks[i + 1] != "0":
                current, i = toks[i + 1], i + 2
            else:                                 # number not caught: lines are sent in order
                current, i = str(int(current or 0) + 1), i + 1
            lines.setdefault(current, [])
            continue
        (lines[current] if current else preamble).append(toks[i])
        i += 1
    joined = {}
    for n, ts in lines.items():
        ts = [t for t in ts if t not in ("OVER", "OUT", "MEDEVAC", "REQUEST")]
        parts, prev_single = [], False
        for t in ts:
            single = len(t) == 1
            if parts and single and prev_single:
                parts[-1] += t
            else:
                parts.append(t)
            prev_single = single
        joined[n] = " ".join(parts)
    words = text.lower().split()
    return {"text": " ".join(toks), "lines": joined,
            "opened": "medevac" in " ".join(preamble).lower() or ("MEDEVAC" in preamble),
            "closed": bool(words) and words[-1] == "over"}


def transcribe_radio(pcm16_b64: str, rate: int = 16000) -> dict:
    return nine_line(_recognize(pcm16_b64, rate, RADIO_GRAMMAR))
