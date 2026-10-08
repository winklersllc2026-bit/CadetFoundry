"""
Backup and transfer: everything the Soldier entered, in one file -- for a new
device after AIT, or when a handheld is replaced.

Backups are encrypted with a password the Soldier chooses (AES-256-GCM, key from scrypt;
see vault.py), because a backup file travels: USB sticks get lost. Device settings
(config.json: AI model, online switch, keys) belong to the device, not the Soldier, so
they're never exported and a backup can never change them.
"""
from __future__ import annotations

import json
import time

from vanguard import store, vault

JSON_FILES = ("profile.json", "study.json", "chat.json", "chats.json", "contacts.json", "daily.json", "leave.json", "budget.json",
              "faith_plans.json", "drill_times.json", "support.json", "pcs.json", "bct.json",
              "books.json")
LINE_FILES = ("memory.jsonl", "log.jsonl", "letters.jsonl", "checkins.jsonl", "exams.jsonl")
VERSION = 1


def export(kind: str = "soldier") -> dict:
    data = {"vanguard_backup": VERSION, "created": time.strftime("%Y-%m-%d %H:%M"), "kind": kind,
            "json": {f: store.read_json(f, None) for f in JSON_FILES},
            "lines": {f: store.read_lines(f) for f in LINE_FILES}}
    return data


def export_sealed(kind: str, password: str) -> dict:
    """The backup, encrypted with the Soldier's backup password."""
    err = vault.backup_password_problem(password)
    if err:
        raise ValueError(err)
    if not vault.AVAILABLE:
        raise ValueError("Encrypted backups need the 'cryptography' package (run the installer again).")
    return vault.seal_backup(json.dumps(export(kind), ensure_ascii=False).encode("utf-8"), password)


def open_any(data: dict, password: str = "") -> dict:
    """An encrypted backup opened with its password, or an older plain backup as is."""
    if isinstance(data, dict) and data.get("vanguard_backup_sealed"):
        try:
            return json.loads(vault.open_backup(data, password).decode("utf-8"))
        except vault.VaultError as e:
            raise ValueError(str(e)) from e
    return data


def restore(data: dict) -> dict:
    """Replace this device's data with the backup's. Returns what was restored."""
    if not isinstance(data, dict) or data.get("vanguard_backup") != VERSION:
        raise ValueError("That isn't a Vanguard backup file.")
    restored = []
    for f in JSON_FILES:                             # config.json is never restored (device settings)
        v = data.get("json", {}).get(f)
        if v is None:
            continue
        store.write_json(f, v)
        restored.append(f)
    for f in LINE_FILES:
        rows = data.get("lines", {}).get(f)
        if isinstance(rows, list):
            store.write_lines(f, [r for r in rows if isinstance(r, dict)])
            restored.append(f)
    out = {"restored": restored, "from": data.get("created", "")}
    if data.get("kind") in ("soldier", "family"):    # older backups don't say; the profile then keeps its own
        out["kind"] = data["kind"]
    return out
