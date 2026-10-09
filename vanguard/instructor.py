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


def add_unit(priv: bytes, name, kind, parent: str = "") -> dict:
    kind = kind if kind in UNIT_KINDS else "class"
    with _lock:
        r = roster(priv)
        if parent and not any(u["id"] == parent for u in r["units"]):
            raise ValueError("That parent unit doesn't exist.")
        if len(r["units"]) >= 100:
            raise ValueError("A program can have up to 100 classes, platoons and squads.")
        unit = {"id": uuid.uuid4().hex[:10], "name": _clean_name(name), "kind": kind, "parent": parent or ""}
        r["units"].append(unit)
        _save(priv, r)
    return unit


def rename_unit(priv: bytes, uid: str, name) -> None:
    with _lock:
        r = roster(priv)
        unit = next((u for u in r["units"] if u["id"] == uid), None)
        if not unit:
            raise ValueError("No such unit.")
        unit["name"] = _clean_name(name)
        _save(priv, r)


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


def assign(priv: bytes, pid: str, unit: str | None = None, let: int | None = None) -> dict:
    p = profiles.get(pid)
    if not p or p["kind"] != "cadet":
        raise ValueError("No such Cadet.")
    with _lock:
        r = roster(priv)
        c = r["cadets"].setdefault(pid, {"unit": "", "let": None})
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


def records(priv: bytes, pid: str) -> dict:
    """One Cadet's class records, read-only. Private files are never opened."""
    ck, status = class_key(priv, pid)
    if status == "waiting":
        return {"status": status}
    with security.as_profile(pid, None, ck):
        study = store.read_json("study.json", {})
        exams = store.read_lines("exams.jsonl")
    answered = len(study)
    right = sum(1 for r in study.values() if r.get("right"))
    last = max((r.get("last", 0) for r in study.values()), default=0)
    return {"status": status, "questions_practiced": answered, "questions_known": right,
            "last_study": time.strftime("%Y-%m-%d", time.localtime(last)) if last else "",
            "exams": list(reversed(exams[-10:]))}


def overview(priv: bytes) -> dict:
    r = roster(priv)
    cadets = []
    for p in profiles.all_profiles():
        if p["kind"] != "cadet":
            continue
        meta = r["cadets"].get(p["id"], {})
        rec = records(priv, p["id"])
        cadets.append({"id": p["id"], "name": p["name"], "unit": meta.get("unit", ""), "let": meta.get("let"),
                       "status": rec["status"], "questions_known": rec.get("questions_known", 0),
                       "exams": len(rec.get("exams", [])), "last_study": rec.get("last_study", "")})
    return {"units": r["units"], "cadets": cadets, "unit_kinds": UNIT_KINDS, "let_levels": LET_LEVELS}
