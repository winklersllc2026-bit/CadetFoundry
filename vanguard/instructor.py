"""
The instructor's program: classes, platoons and squads, each Cadet's unit and LET level, and read-only views of
Cadets' class records.

Everything here needs the program private key, which only an instructor's session holds after the Instructor PIN
(security.unlock_program). The roster is sealed with a key derived from it (vault.program_data_key), so a Cadet
can neither read nor change it, and class records are opened with each Cadet's class key -- never their private
files (owner's decision, 2026-10-08: class records only).
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
import uuid

from vanguard import profiles, security, store, vault

UNIT_KINDS = ("class", "platoon", "squad")
LET_LEVELS = (1, 2, 3, 4)
_lock = threading.Lock()


def _roster_path():
    return store.DATA / "program" / "roster.json"


def roster(priv: bytes) -> dict:
    path = _roster_path()
    try:
        data = path.read_bytes()
    except OSError:
        return {"units": [], "cadets": {}}
    try:
        return json.loads(vault.open_sealed(vault.program_data_key(priv), data, "roster.json").decode("utf-8"))
    except vault.VaultError:                    # sealed with an older program key (Instructor PIN was reset)
        return {"units": [], "cadets": {}}


def _save(priv: bytes, data: dict) -> None:
    path = _roster_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(vault.seal(vault.program_data_key(priv), json.dumps(data).encode("utf-8"), "roster.json"))
    tmp.replace(path)


def _clean_name(name) -> str:
    name = " ".join(str(name or "").split())[:40]
    if not name:
        raise ValueError("Enter a name.")
    return name


# ── join codes ──────────────────────────────────────────────────────────────
# Every class, platoon and squad has a short join code. A Cadet who types it (or scans the class QR code) is put in
# that unit -- no instructor clicks. The codes are in program/join_codes.json in the clear, with the unit's name:
# a Cadet's session has no program key, so it can't open the sealed roster. A code only lets someone put their *own*
# new profile in a unit; it never opens anything. The roster itself stays sealed: a join waits in
# program/joins.json until an instructor's session (which can open the roster) files it.
JOIN_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"      # no 0/O, 1/I/L: easy to read off a projector
JOIN_LEN = 6


def _program_file(name: str):
    return store.DATA / "program" / name


def _read_plain(name: str, default):
    try:
        return json.loads(_program_file(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_plain(name: str, data) -> None:
    path = _program_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def clean_code(code) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())[:12]


def _new_code(taken: set) -> str:
    while True:
        code = "".join(secrets.choice(JOIN_ALPHABET) for _ in range(JOIN_LEN))
        if code not in taken:
            return code


def _publish_codes(r: dict) -> None:
    _write_plain("join_codes.json", {u["code"]: {"unit": u["id"], "name": u["name"]} for u in r["units"] if u.get("code")})


def _ensure_codes(r: dict) -> bool:
    taken, changed = {u.get("code") for u in r["units"]}, False
    for u in r["units"]:
        if not u.get("code"):
            u["code"] = _new_code(taken)
            taken.add(u["code"])
            changed = True
    return changed


def unit_for_code(code) -> dict | None:
    """{"unit": id, "name": ...} for a join code, or None."""
    return _read_plain("join_codes.json", {}).get(clean_code(code))


def request_join(pid: str, unit: str) -> None:
    """A Cadet used a join code: filed into the roster the next time an instructor opens class records."""
    with _lock:
        joins = _read_plain("joins.json", {})
        joins[pid] = unit
        _write_plain("joins.json", joins)


def apply_joins(priv: bytes) -> list[str]:
    """Files waiting joins into the sealed roster. Returns the Cadets placed in a unit."""
    with _lock:
        joins = _read_plain("joins.json", {})
        if not joins:
            return []
        _write_plain("joins.json", {})
    units = {u["id"] for u in roster(priv)["units"]}
    placed = []
    for pid, unit in joins.items():
        if unit in units and (profiles.get(pid) or {}).get("kind") == "cadet":
            assign(priv, pid, unit)
            placed.append(pid)
    return placed


def new_code(priv: bytes, uid: str) -> str:
    """A fresh join code for one unit (the old one stops working) -- e.g. after it was shared too widely."""
    with _lock:
        r = roster(priv)
        unit = next((u for u in r["units"] if u["id"] == uid), None)
        if not unit:
            raise ValueError("No such unit.")
        unit["code"] = _new_code({u.get("code") for u in r["units"]})
        _save(priv, r)
        _publish_codes(r)
    return unit["code"]


def set_owner(priv: bytes, uid: str, owner: str) -> None:
    """Which instructor teaches a unit ("" = shared). Lets each instructor filter to "My Cadets"."""
    if owner and (profiles.get(owner) or {}).get("kind") != "instructor":
        raise ValueError("No such instructor.")
    with _lock:
        r = roster(priv)
        unit = next((u for u in r["units"] if u["id"] == uid), None)
        if not unit:
            raise ValueError("No such unit.")
        unit["owner"] = owner
        _save(priv, r)


def units_of(priv: bytes, owner: str) -> list[str]:
    return [u["id"] for u in roster(priv)["units"] if u.get("owner") == owner]


def add_unit(priv: bytes, name, kind, parent: str = "", owner: str = "") -> dict:
    kind = kind if kind in UNIT_KINDS else "class"
    with _lock:
        r = roster(priv)
        if parent and not any(u["id"] == parent for u in r["units"]):
            raise ValueError("That parent unit doesn't exist.")
        if len(r["units"]) >= 100:
            raise ValueError("A program can have up to 100 classes, platoons and squads.")
        unit = {"id": uuid.uuid4().hex[:10], "name": _clean_name(name), "kind": kind, "parent": parent or "",
                "owner": owner, "code": _new_code({u.get("code") for u in r["units"]})}
        r["units"].append(unit)
        _save(priv, r)
        _publish_codes(r)
    return unit


def rename_unit(priv: bytes, uid: str, name) -> None:
    with _lock:
        r = roster(priv)
        unit = next((u for u in r["units"] if u["id"] == uid), None)
        if not unit:
            raise ValueError("No such unit.")
        unit["name"] = _clean_name(name)
        _save(priv, r)
        _publish_codes(r)


def delete_unit(priv: bytes, uid: str) -> None:
    """Removes the unit; its sub-units move up to its parent and its Cadets become unassigned."""
    with _lock:
        r = roster(priv)
        unit = next((u for u in r["units"] if u["id"] == uid), None)
        if not unit:
            raise ValueError("No such unit.")
        r["units"] = [u for u in r["units"] if u["id"] != uid]
        for u in r["units"]:
            if u["parent"] == uid:
                u["parent"] = unit["parent"]
        for c in r["cadets"].values():
            if c.get("unit") == uid:
                c["unit"] = ""
        _save(priv, r)
        _publish_codes(r)


def _clean_title(v) -> str:
    return " ".join(str(v or "").split())[:40]


def cadet_title(pid: str) -> dict:
    """A Cadet's own cadet rank and billet (their job in the cadet corps), for their Home screen. Kept in the clear in
    program/cadet_titles.json because a Cadet's session can't open the sealed roster; it holds nothing else."""
    return _read_plain("cadet_titles.json", {}).get(pid) or {}


def assign(priv: bytes, pid: str, unit: str | None = None, let: int | None = None,
           rank: str | None = None, billet: str | None = None) -> dict:
    p = profiles.get(pid)
    if not p or p["kind"] != "cadet":
        raise ValueError("No such Cadet.")
    with _lock:
        r = roster(priv)
        c = r["cadets"].setdefault(pid, {"unit": "", "let": None})
        if rank is not None or billet is not None:
            if rank is not None:
                c["rank"] = _clean_title(rank)
            if billet is not None:
                c["billet"] = _clean_title(billet)
            titles = _read_plain("cadet_titles.json", {})
            titles[pid] = {k: c.get(k, "") for k in ("rank", "billet") if c.get(k)}
            if not titles[pid]:
                titles.pop(pid)
            _write_plain("cadet_titles.json", titles)
        if unit is not None:
            if unit and not any(u["id"] == unit for u in r["units"]):
                raise ValueError("No such unit.")
            c["unit"] = unit
        if let is not None:
            if let not in LET_LEVELS:
                raise ValueError("LET level is 1 to 4.")
            c["let"] = let
        _save(priv, r)
    return c


def class_key(priv: bytes, pid: str) -> tuple[bytes | None, str]:
    """(the Cadet's class key or None, status). status: "shared" (readable), "open" (no PIN -- files aren't
    encrypted), or "waiting" (the Cadet hasn't signed in since the program key was made)."""
    with security.as_profile(pid):
        st = security._state()
    if not st.get("vault"):
        return None, "open"
    box = st.get("class_for") or {}
    pub = security.program_public()
    if not pub or box.get("to") != vault.key_id(pub):
        return None, "waiting"
    try:
        return vault.open_from(priv, box, "class key"), "shared"
    except vault.VaultError:
        return None, "waiting"


def read_class_file(priv: bytes, pid: str, name: str, default):
    """One class-record file of one Cadet (None if the Cadet hasn't shared yet). Only store.CLASS_FILES."""
    if name not in store.CLASS_FILES:
        raise ValueError("Only class records can be read.")
    ck, status = class_key(priv, pid)
    if status == "waiting":
        return None
    with security.as_profile(pid, None, ck):
        return store.read_lines(name) if name.endswith(".jsonl") else store.read_json(name, default)


def records(priv: bytes, pid: str) -> dict:
    """One Cadet's class records, read-only. Private files are never opened."""
    ck, status = class_key(priv, pid)
    if status == "waiting":
        return {"status": status}
    with security.as_profile(pid, None, ck):
        study = store.read_json("study.json", {})
        exams = store.read_lines("exams.jsonl")
        scen = store.read_lines("scenarios.jsonl")
    answered = len(study)
    right = sum(1 for r in study.values() if r.get("right"))
    last = max((r.get("last", 0) for r in study.values()), default=0)
    return {"status": status, "questions_practiced": answered, "questions_known": right,
            "last_study": time.strftime("%Y-%m-%d", time.localtime(last)) if last else "",
            "exams": list(reversed(exams[-10:])), "scenarios": len(scen)}


def overview(priv: bytes) -> dict:
    with _lock:                                  # units made before join codes existed get one now
        r = roster(priv)
        if _ensure_codes(r):
            _save(priv, r)
            _publish_codes(r)
    cadets = []
    for p in profiles.all_profiles():
        if p["kind"] != "cadet":
            continue
        meta = r["cadets"].get(p["id"], {})
        rec = records(priv, p["id"])
        cadets.append({"id": p["id"], "name": p["name"], "unit": meta.get("unit", ""), "let": meta.get("let"),
                       "rank": meta.get("rank", ""), "billet": meta.get("billet", ""),
                       "status": rec["status"], "questions_known": rec.get("questions_known", 0),
                       "exams": len(rec.get("exams", [])), "last_study": rec.get("last_study", ""),
                       "scenarios": rec.get("scenarios", 0)})
    return {"units": r["units"], "cadets": cadets, "unit_kinds": UNIT_KINDS, "let_levels": LET_LEVELS,
            "instructors": [{"id": p["id"], "name": p["name"]} for p in profiles.all_profiles() if p["kind"] == "instructor"]}
