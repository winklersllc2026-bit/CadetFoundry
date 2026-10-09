"""
Program backup (Phase 9): everything the instructor built, in one password-sealed file.

What's in it: the program folder (roster, lessons and their sealed notes, assignments, instructor scenarios, service
projects, fitness events, classroom-vote state is left out), the program key file and the Instructor PIN file (so the
sealed roster and notes still open after a restore), and the instructor's device settings (AI mode, Learn
categories, portfolio sections).

Not in it: any Cadet's files. Each person backs up their own profile (Me -> Download encrypted backup); Cadets'
class records stay theirs.

The file is sealed with the backup password (scrypt + AES-256-GCM, vault.seal_backup) -- without it nobody can open it.
"""
from __future__ import annotations

import base64
import json
import time

from vanguard import store, vault

VERSION = 1
PROGRAM_FILES = ("roster.json", "lessons.json", "lesson_notes.json", "assignments.json", "scenarios.json",
                 "service_projects.json", "fitness_events.json", "quiz_overrides.json")
DEVICE_FILES = ("program.json", "admin.json")
CONFIG_KEYS = ("ai_mode", "categories", "portfolio_sections")


def export(password: str) -> dict:
    err = vault.backup_password_problem(password)
    if err:
        raise ValueError(err)
    files = {}
    for name in PROGRAM_FILES:
        path = store.DATA / "program" / name
        if path.exists():
            files["program/" + name] = base64.b64encode(path.read_bytes()).decode("ascii")
    for name in DEVICE_FILES:
        path = store.DATA / name
        if path.exists():
            files[name] = base64.b64encode(path.read_bytes()).decode("ascii")
    cfg = store.config()
    payload = {"vanguard_program_backup": VERSION, "created": time.strftime("%Y-%m-%d %H:%M"), "files": files,
               "config": {k: cfg[k] for k in CONFIG_KEYS if k in cfg}}
    return {"vanguard_program_backup_sealed": VERSION, **vault.seal_backup(json.dumps(payload).encode("utf-8"), password)}


def restore(box: dict, password: str) -> dict:
    """Replaces the program on this device with the backup. Cadets' profiles are not touched."""
    if not isinstance(box, dict) or box.get("vanguard_program_backup_sealed") != VERSION:
        raise ValueError("That isn't a Vanguard program backup.")
    try:
        data = json.loads(vault.open_backup(box, password).decode("utf-8"))
    except vault.VaultError:
        raise ValueError("Wrong backup password, or the file is damaged.") from None
    allowed = {"program/" + n for n in PROGRAM_FILES} | set(DEVICE_FILES)
    files = data.get("files") or {}
    if not isinstance(files, dict) or not set(files) <= allowed:
        raise ValueError("That backup contains files Vanguard doesn't expect, so it wasn't restored.")
    (store.DATA / "program").mkdir(parents=True, exist_ok=True)
    for name, b64 in files.items():
        path = store.DATA / name
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(base64.b64decode(b64))
        tmp.replace(path)
    cfg = {k: v for k, v in (data.get("config") or {}).items() if k in CONFIG_KEYS}
    if cfg:
        store.save_config(cfg)
    return {"restored": sorted(files), "from": data.get("created", "")}
