"""
Several Soldiers on one device: each profile has its own folder (profiles/<id>/)
with its own logbook, letters, memory, progress and PIN. A profile's files are
only reachable through a session unlocked for that profile.
"""
from __future__ import annotations

import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from vanguard import store

ROOT = store.DATA / "profiles"
_lock = threading.Lock()

# Files that used to sit at the top of the data folder before profiles existed.
_LEGACY = ("profile.json", "memory.jsonl", "log.jsonl", "study.json", "chat.json", "contacts.json", "letters.jsonl",
           "daily.json", "checkins.jsonl", "leave.json", "budget.json", "faith_plans.json", "security.json")


def _index() -> dict:
    return store.read_json("profiles.json", {"profiles": []})


def _save(idx: dict) -> None:
    store.write_json("profiles.json", idx)


def folder(pid: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}", pid or ""):
        raise ValueError("bad profile id")
    return ROOT / pid


def all_profiles() -> list[dict]:
    return _index()["profiles"]


def get(pid: str) -> dict | None:
    return next((p for p in all_profiles() if p["id"] == pid), None)


def create(name: str, kind: str = "soldier") -> dict:
    name = " ".join((name or "").split())[:40]
    if not name:
        raise ValueError("Enter a name.")
    with _lock:
        idx = _index()
        if len(idx["profiles"]) >= 30:
            raise ValueError("This device already has the maximum of 30 profiles.")
        if any(p["name"].lower() == name.lower() for p in idx["profiles"]):
            raise ValueError("There's already a profile with that name.")
        p = {"id": uuid.uuid4().hex[:12], "name": name, "created": time.strftime("%Y-%m-%d"),
             "kind": "family" if kind == "family" else "soldier"}      # family: a spouse, parent, etc.
        folder(p["id"]).mkdir(parents=True, exist_ok=True)
        idx["profiles"].append(p)
        _save(idx)
    return p


def rename(pid: str, name: str) -> None:
    name = " ".join((name or "").split())[:40]
    if not name:
        raise ValueError("Enter a name.")
    with _lock:
        idx = _index()
        if any(p["name"].lower() == name.lower() and p["id"] != pid for p in idx["profiles"]):
            raise ValueError("There's already a profile with that name.")
        for p in idx["profiles"]:
            if p["id"] == pid:
                p["name"] = name
        _save(idx)


def set_kind(pid: str, kind: str) -> None:
    with _lock:
        idx = _index()
        for p in idx["profiles"]:
            if p["id"] == pid:
                p["kind"] = "family" if kind == "family" else "soldier"
        _save(idx)


def delete(pid: str) -> None:
    with _lock:
        idx = _index()
        idx["profiles"] = [p for p in idx["profiles"] if p["id"] != pid]
        _save(idx)
        shutil.rmtree(folder(pid), ignore_errors=True)


def migrate_legacy() -> None:
    """First run after the upgrade: move single-user data into a first profile."""
    with _lock:
        if all_profiles():
            return
        legacy = [f for f in _LEGACY if (store.DATA / f).exists()]
        if not legacy:
            return
        name = "Soldier"
        try:
            import json
            name = json.loads((store.DATA / "profile.json").read_text(encoding="utf-8")).get("name") or name
        except Exception:
            pass
        p = {"id": uuid.uuid4().hex[:12], "name": name[:40], "created": time.strftime("%Y-%m-%d")}
        dest = folder(p["id"])
        dest.mkdir(parents=True, exist_ok=True)
        for f in legacy:
            shutil.move(str(store.DATA / f), str(dest / f))
        _save({"profiles": [p]})
