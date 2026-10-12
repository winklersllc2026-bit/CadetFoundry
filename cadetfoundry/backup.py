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

from cadetfoundry import store, vault

JSON_FILES = ("profile.json", "study.json", "chat.json", "chats.json", "contacts.json", "daily.json", "leave.json", "budget.json",
              "faith_plans.json", "drill_times.json", "support.json", "pcs.json", "bct.json",
              "books.json")
LINE_FILES = ("memory.jsonl", "log.jsonl", "letters.jsonl", "checkins.jsonl", "exams.jsonl")
VERSION = 1
OLD = "vanguard"                                 # backups made before the rename (0.2.6) still restore


def export(kind: str = "cadet") -> dict:
    data = {"cadetfoundry_backup": VERSION, "created": time.strftime("%Y-%m-%d %H:%M"), "kind": kind,
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
    if isinstance(data, dict) and (data.get("cadetfoundry_backup_sealed") or data.get(OLD + "_backup_sealed")):
        try:
            return json.loads(vault.open_backup(data, password).decode("utf-8"))
        except vault.VaultError as e:
            raise ValueError(str(e)) from e
    return data


def _shape_ok(name: str, value) -> bool:
    """A backup is a file its owner controls. Every file is an object or a list, and study.json -- a class record the
    instructor's views read -- is an object of objects, so one Cadet's backup can't break the class overview."""
    if not isinstance(value, (dict, list)):
        return False
    if name == "study.json":
        return isinstance(value, dict) and all(isinstance(r, dict) for r in value.values())
    return True


def restore(data: dict) -> dict:
    """Replace this device's data with the backup's. Returns what was restored."""
    if not isinstance(data, dict) or data.get("cadetfoundry_backup", data.get(OLD + "_backup")) != VERSION:
        raise ValueError("That isn't a Cadet Foundry backup file.")
    restored = []
    for f in JSON_FILES:                             # config.json is never restored (device settings)
        v = data.get("json", {}).get(f)
        if v is None or not _shape_ok(f, v):         # a damaged or hand-made file is skipped, never written
            continue
        store.write_json(f, v)
        restored.append(f)
    for f in LINE_FILES:
        rows = data.get("lines", {}).get(f)
        if isinstance(rows, list):
            store.write_lines(f, [r for r in rows if isinstance(r, dict)])
            restored.append(f)
    out = {"restored": restored, "from": data.get("created", "")}
    kind = {"soldier": "cadet", "family": "guardian"}.get(data.get("kind"), data.get("kind"))
    if kind in ("cadet", "guardian"):               # older backups don't say; the profile then keeps its own
        out["kind"] = kind
    return out
