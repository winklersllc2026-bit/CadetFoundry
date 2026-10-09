"""
Everything Vanguard keeps about the Soldier -- in files on this device, encrypted when the
profile has a PIN (see vault.py).

  profile.json   name, rank, MOS, where they are in training, goals
  memory.jsonl   lasting facts Vanguard learned ("fails the plank at 1:30")
  log.jsonl      the logbook: PT scores, qualifications, notes, goals
  study.json     flashcard results (so missed questions come back more often)
  chats.json     conversations (the Ask tab's sidebar); chat.json is the old single conversation
  config.json    device settings: AI model (shared by all profiles)

Folder: $VANGUARD_DATA, or ~/.vanguard. Each Soldier's files live in their
own profile folder (profiles/<id>/); device-wide files stay at the top.
"""
from __future__ import annotations

import contextvars
import json
import re
import os
import threading
import time
import uuid
from pathlib import Path

DATA = Path(os.environ.get("VANGUARD_DATA") or (Path.home() / ".vanguard"))
_lock = threading.RLock()

# Device-wide files (shared by every profile). Everything else belongs to the active profile.
DEVICE_FILES = {"config.json", "profiles.json", "library_index.json"}

# The profile folder for the current request/thread. Set by the server from the
# unlocked session; there is deliberately no fallback to another profile's folder.
_profile_dir: contextvars.ContextVar[Path | None] = contextvars.ContextVar("vanguard_profile_dir", default=None)


class NoProfile(RuntimeError):
    """Raised when Soldier data is accessed without an active profile."""


def use_profile(folder: Path | None):
    """Make `folder` the active profile for this context. Returns a token for reset_profile()."""
    return _profile_dir.set(folder)


def reset_profile(token) -> None:
    _profile_dir.reset(token)


def active_profile_dir() -> Path | None:
    return _profile_dir.get()


def _path(name: str) -> Path:
    base = name.split(".tmp")[0]
    if base in DEVICE_FILES:
        d = DATA
    else:
        d = _profile_dir.get()
        if d is None:
            raise NoProfile(f"no active profile for {name}")
    d.mkdir(parents=True, exist_ok=True)
    return d / name


# The unlocked profile's data key (vanguard/vault.py), set alongside the profile folder. None for a
# profile without a PIN, whose files stay plain. Only security.json -- the PIN hash and the PIN-locked
# data key -- is never sealed, because it's what unlocks everything else.
_profile_key: contextvars.ContextVar[bytes | None] = contextvars.ContextVar("vanguard_profile_key", default=None)
PLAIN_FILES = {"security.json"}

# Class records: schoolwork the instructor may read (owner's decision, 2026-10-08). They are sealed with the Cadet's
# CLASS key, which the instructor can also open; every other file stays under the Cadet's private key only
# (check-ins, chats, memories, letters, logbook, profile...).
CLASS_FILES = {"study.json", "exams.jsonl", "lessons.json", "assignments.json", "scenarios.jsonl",
               "service.jsonl", "fitness.jsonl", "goals.json", "recognition.jsonl"}
_class_key: contextvars.ContextVar[bytes | None] = contextvars.ContextVar("vanguard_class_key", default=None)


def use_key(key: bytes | None):
    return _profile_key.set(key)


def reset_key(token) -> None:
    _profile_key.reset(token)


def use_class_key(key: bytes | None):
    return _class_key.set(key)


def reset_class_key(token) -> None:
    _class_key.reset(token)


def _key_for(name: str) -> bytes | None:
    return _class_key.get() if name in CLASS_FILES else _profile_key.get()


def _sealable(name: str) -> bool:
    return name not in DEVICE_FILES and name not in PLAIN_FILES


def _read_text(name: str) -> str | None:
    """The file's text, decrypted if sealed; None if it doesn't exist. A sealed file that won't open
    raises vault.VaultError -- it is never treated as empty, so it can't be overwritten by mistake."""
    from vanguard import vault
    path = _path(name)                       # raises NoProfile -- never silently "no data"
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if vault.is_sealed(data):
        try:
            data = vault.open_sealed(_key_for(name), data, name)
        except vault.VaultError:
            # a class record not yet moved to the class key (interrupted move): it still opens with the data key
            if name not in CLASS_FILES or _profile_key.get() is None:
                raise
            data = vault.open_sealed(_profile_key.get(), data, name)
    return data.decode("utf-8")


def _write_text(name: str, text: str) -> None:
    """Write atomically (temp file, then rename), sealed when the profile has a key, so a crash or
    power loss mid-write can't leave a half-written logbook."""
    from vanguard import vault
    data = text.encode("utf-8")
    key = _key_for(name)
    if key is not None and _sealable(name):
        data = vault.seal(key, data, name)
    with _lock:
        tmp = _path(name + ".tmp")
        with tmp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(_path(name))


def read_json(name: str, default):
    text = _read_text(name)
    if text is None:
        return default
    try:
        return json.loads(text)
    except ValueError:
        return default


def write_json(name: str, value) -> None:
    _write_text(name, json.dumps(value, indent=2, ensure_ascii=False))


def read_lines(name: str) -> list[dict]:
    text = _read_text(name)
    out = []
    for line in (text or "").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue                     # one damaged line doesn't lose the whole logbook
    return out


def write_lines(name: str, rows: list[dict]) -> None:
    _write_text(name, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def append_line(name: str, row: dict) -> None:
    with _lock:                              # sealed files can't be appended to, so rewrite (they're small)
        write_lines(name, read_lines(name) + [row])


def reseal_folder(folder: Path, old_key: bytes | None, new_key: bytes | None, only: set | None = None,
                  skip: set | None = None) -> int:
    """Re-encrypt files in one profile folder from old_key to new_key (None = plain): all of them, only the names
    in `only`, or all but `skip`. Used when a PIN is set or removed, and to move class records to the class key."""
    from vanguard import vault
    done = 0
    with _lock:
        for path in sorted(folder.iterdir()):
            name = path.name
            if not path.is_file() or name.endswith(".tmp") or not _sealable(name):
                continue
            if (only is not None and name not in only) or (skip and name in skip):
                continue
            data = path.read_bytes()
            if vault.is_sealed(data):
                data = vault.open_sealed(old_key, data, name)
            if new_key is not None:
                data = vault.seal(new_key, data, name)
            tmp = path.with_name(name + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
            done += 1
    return done


# ── profile ─────────────────────────────────────────────────────────────────
# A Cadet's profile: only what helps Vanguard fit the Cadet. Nothing about body size, sex or military status --
# minors' data is kept to the minimum (owner's spec §25), and Train needs none of it.
PROFILE_FIELDS = ("name", "grade", "interests", "goals", "faith_texts", "military_track", "intake_done")
GRADES = ("9th grade", "10th grade", "11th grade", "12th grade", "Other")
INTERESTS = ("Leadership", "Public speaking", "Fitness", "Grades", "Confidence", "Teamwork", "Service", "College",
             "A career", "Military service")


def profile() -> dict:
    return read_json("profile.json", {})


def parse_height(text: str) -> int | None:
    """Height in inches from what people type: 5'10", 5 10, 5ft 10in, 70, 70 in, 178 cm."""
    t = str(text).lower().replace("”", '"').replace("’", "'").replace("″", '"').replace("′", "'").strip()
    feet = re.fullmatch(r"([4-7])\s*(?:'|ft\.?|feet|foot)\s*(?:(\d{1,2})\s*(?:\"|in\.?|inch|inches)?)?", t) \
        or re.fullmatch(r"([4-7])\s+(\d{1,2})", t)
    if feet:
        inches = int(feet.group(2) or 0)
        return int(feet.group(1)) * 12 + inches if inches < 12 else None
    m = re.fullmatch(r"(\d{2,3})\s*(\"|in\.?|inch|inches|cm)?", t)
    if m:
        n = int(m.group(1))
        return round(n / 2.54) if m.group(2) == "cm" or (not m.group(2) and n > 100) else n
    return None


def height_text(inches) -> str:
    try:
        n = int(inches)
    except (TypeError, ValueError):
        return ""
    return f"{n // 12}'{n % 12}\""


def _clean_profile_value(k: str, v: str) -> str:
    """Numbers and choices the AFT scorer and the fitness plan rely on. Raises ValueError with a plain reason."""
    if k == "military_track":                       # the Cadet's opt-in to Basic Training & Beyond: yes or nothing
        return "yes" if v == "yes" else ""
    if not v or k not in ("age", "sex", "height", "weight"):
        return v
    if k == "age":
        n = int(re.sub(r"\D", "", v) or 0)
        if not 16 <= n <= 70:
            raise ValueError("Age should be a number, like 19.")
        return str(n)
    if k == "sex":
        x = v.strip().lower()
        if x in ("m", "male", "man"):
            return "M"
        if x in ("f", "female", "woman"):
            return "F"
        raise ValueError("Answer male or female.")
    if k == "height":
        n = parse_height(v)
        if n is None or not 48 <= n <= 90:
            raise ValueError("Give your height like 5'10\" (or in inches, like 70).")
        return str(n)
    n = int(re.sub(r"(?i)\s*(lbs?|pounds?)\s*$", "", v.strip()) or 0) if re.fullmatch(r"(?i)\d{2,3}\s*(lbs?|pounds?)?", v.strip()) else 0
    if not 80 <= n <= 400:
        raise ValueError("Give your weight in pounds, like 165.")
    return str(n)


def save_profile(data: dict) -> dict:
    """Raises ValueError (plain reason) for an age, height or weight that doesn't make sense; nothing is saved then."""
    p = profile()
    clean = {k: _clean_profile_value(k, str(data[k]).strip()[:300]) for k in PROFILE_FIELDS if k in data}
    p.update(clean)
    p["updated"] = time.strftime("%Y-%m-%d")
    write_json("profile.json", p)
    return p


def profile_text() -> str:
    p = profile()
    bits = []
    if p.get("name"):
        bits.append(f"Name: {p['name']}")
    if p.get("grade"):
        bits.append(f"Grade: {p['grade']}")
    if p.get("interests"):
        bits.append(f"Wants to get better at: {p['interests']}")
    if p.get("goals"):
        bits.append(f"Goals: {p['goals']}")
    return "\n".join(bits)


# ── memory ──────────────────────────────────────────────────────────────────

def memories() -> list[dict]:
    return read_lines("memory.jsonl")


def remember(text: str, source: str = "manual") -> bool:
    text = " ".join((text or "").split())[:300]
    if len(text) < 4 or any(m["text"].lower() == text.lower() for m in memories()):
        return False
    append_line("memory.jsonl", {"id": uuid.uuid4().hex[:8], "text": text, "source": source, "t": time.time()})
    return True


def forget(mem_id: str) -> bool:
    rows = memories()
    keep = [m for m in rows if m["id"] != mem_id]
    write_lines("memory.jsonl", keep)
    return len(keep) != len(rows)


# ── logbook ─────────────────────────────────────────────────────────────────
LOG_KINDS = ("PT", "Qualification", "Training", "Goal", "Note")


def log_entries() -> list[dict]:
    return sorted(read_lines("log.jsonl"), key=lambda r: r.get("date", ""), reverse=True)


def add_log(kind: str, text: str, date: str = "", score: str = "") -> dict:
    row = {"id": uuid.uuid4().hex[:8], "kind": kind if kind in LOG_KINDS else "Note",
           "text": (text or "").strip()[:2000], "score": (score or "").strip()[:60],
           "date": date or time.strftime("%Y-%m-%d"), "t": time.time()}
    append_line("log.jsonl", row)
    return row


def delete_log(entry_id: str) -> bool:
    rows = read_lines("log.jsonl")
    keep = [r for r in rows if r["id"] != entry_id]
    write_lines("log.jsonl", keep)
    return len(keep) != len(rows)


def log_text(limit: int = 12) -> str:
    rows = log_entries()[:limit]
    return "\n".join(f"- {r['date']} [{r['kind']}] {r['text']}" + (f" (score: {r['score']})" if r.get("score") else "")
                     for r in rows)


# ── study results ───────────────────────────────────────────────────────────

def study() -> dict:
    return read_json("study.json", {})


def record_answer(qid: str, correct: bool) -> dict:
    with _lock:
        s = study()
        r = s.get(qid, {"right": 0, "wrong": 0})
        r["right" if correct else "wrong"] += 1
        r["last"] = time.time()
        s[qid] = r
        write_json("study.json", s)
        return r


# ── conversations ───────────────────────────────────────────────────────────
# Separate chats, listed in the Ask tab's sidebar: {"current": id, "chats": [{id, title, created, updated, messages}]}.
# The AI sees only the current chat. (Profiles from before conversations kept one list in chat.json; it becomes
# the first chat.)
MAX_CHATS, MAX_MESSAGES = 60, 200


def _chats() -> dict:
    data = read_json("chats.json", None)
    if data is None:
        old = read_json("chat.json", [])
        data = {"current": "", "chats": []}
        if old:
            cid = uuid.uuid4().hex[:8]
            first = next((m["content"] for m in old if m.get("role") == "user"), "Earlier conversation")
            data = {"current": cid, "chats": [{"id": cid, "title": _title(first), "created": old[0].get("t", time.time()),
                                                "updated": old[-1].get("t", time.time()), "messages": old}]}
            write_json("chats.json", data)            # converted once, so the chat keeps its id
    return data


def _title(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return (t[:48] + "…") if len(t) > 48 else (t or "New chat")


def _current(data: dict) -> dict | None:
    return next((c for c in data["chats"] if c["id"] == data.get("current")), None)


def chat_list() -> dict:
    data = _chats()
    return {"current": data.get("current", ""),
            "chats": [{"id": c["id"], "title": c["title"], "updated": c["updated"], "n": len(c["messages"])}
                      for c in sorted(data["chats"], key=lambda c: c["updated"], reverse=True)]}


def new_chat() -> dict:
    """Start a fresh conversation (an empty one is reused rather than piling up)."""
    with _lock:
        data = _chats()
        cur = _current(data)
        if not (cur and not cur["messages"]):
            cur = {"id": uuid.uuid4().hex[:8], "title": "New chat", "created": time.time(), "updated": time.time(), "messages": []}
            data["chats"].append(cur)
            data["chats"] = sorted(data["chats"], key=lambda c: c["updated"])[-MAX_CHATS:]
        data["current"] = cur["id"]
        write_json("chats.json", data)
        return cur


def open_chat(cid: str) -> list[dict]:
    with _lock:
        data = _chats()
        if not any(c["id"] == cid for c in data["chats"]):
            raise KeyError(cid)
        data["current"] = cid
        write_json("chats.json", data)
        return _current(data)["messages"]


def rename_chat(cid: str, title: str) -> bool:
    with _lock:
        data = _chats()
        c = next((c for c in data["chats"] if c["id"] == cid), None)
        if c and title.strip():
            c["title"] = _title(title)
            write_json("chats.json", data)
        return bool(c)


def delete_chat(cid: str) -> bool:
    with _lock:
        data = _chats()
        keep = [c for c in data["chats"] if c["id"] != cid]
        if len(keep) == len(data["chats"]):
            return False
        data["chats"] = keep
        if data.get("current") == cid:
            data["current"] = max(keep, key=lambda c: c["updated"])["id"] if keep else ""
        write_json("chats.json", data)
        return True


def history() -> list[dict]:
    """The current conversation's messages."""
    cur = _current(_chats())
    return cur["messages"] if cur else []


def add_history(role: str, content: str) -> None:
    with _lock:
        data = _chats()
        cur = _current(data)
        if not cur:
            cur = {"id": uuid.uuid4().hex[:8], "title": "New chat", "created": time.time(), "updated": time.time(), "messages": []}
            data["chats"].append(cur)
            data["current"] = cur["id"]
        if role == "user" and cur["title"] == "New chat":
            cur["title"] = _title(content)            # named after its first question
        cur["messages"] = (cur["messages"] + [{"role": role, "content": content, "t": time.time()}])[-MAX_MESSAGES:]
        cur["updated"] = time.time()
        write_json("chats.json", data)


def clear_history() -> None:
    """Delete every conversation."""
    write_json("chats.json", {"current": "", "chats": []})
    write_json("chat.json", [])


# ── config ──────────────────────────────────────────────────────────────────

def config() -> dict:
    return read_json("config.json", {})


AI_MODES = ("off", "library", "ai")


ALL_CATEGORIES = ("leadership", "citizenship", "military", "health", "careers", "explore", "basic")
# Optional tools the instructor can switch off for every profile on this device (the server refuses their routes).
MODULES = {"faith": "Faith texts (scripture lookup and reading plans)", "letters": "Letters and address book",
           "voice": "Talk to Vanguard (offline voice)"}


def module_on(name: str) -> bool:
    return name not in (config().get("modules_off") or [])


def categories_enabled() -> list[str]:
    """The Learn categories the instructor has turned on for this device (all, until the instructor chooses)."""
    c = config().get("categories")
    return [x for x in ALL_CATEGORIES if x in c] if isinstance(c, list) else list(ALL_CATEGORIES)


def visible_categories(kind: str) -> list[str]:
    """What one profile may see. Instructors: everything (to review it). Cadets and guardians: what the instructor
    enabled -- and Basic Training & Beyond only for a Cadet who said they plan to join the military."""
    if kind == "instructor":
        return list(ALL_CATEGORIES)
    cats = [c for c in categories_enabled() if c != "basic"]
    if kind == "cadet" and "basic" in categories_enabled() and profile().get("military_track") == "yes":
        cats.append("basic")
    return cats


def ai_mode() -> str:
    """The instructor's AI setting: "off" (no AI writing at all), "library" (default: the AI may only explain what
    the library holds, and says so when it holds nothing) or "ai" (broader explanations, labeled as AI)."""
    c = config()
    mode = c.get("ai_mode")
    if mode in AI_MODES:
        return mode
    return "library"


def save_config(data: dict) -> dict:
    c = config()
    for k in ("model", "groq_key", "gemini_key", "online", "ai_mode", "categories", "portfolio_sections", "modules_off", "demo"):
        if k in data:
            c[k] = data[k]
    if c.get("ai_mode") not in AI_MODES:
        c.pop("ai_mode", None)
    if "categories" in c and not (isinstance(c["categories"], list) and all(x in ALL_CATEGORIES for x in c["categories"])):
        c.pop("categories", None)
    if "demo" in c and not isinstance(c["demo"], bool):
        c.pop("demo", None)
    if "modules_off" in c and not (isinstance(c["modules_off"], list) and all(x in MODULES for x in c["modules_off"])):
        c.pop("modules_off", None)
    if "portfolio_sections" in c and not (isinstance(c["portfolio_sections"], list)
                                          and all(isinstance(x, str) and len(x) < 20 for x in c["portfolio_sections"])):
        c.pop("portfolio_sections", None)
    write_json("config.json", c)
    return c
