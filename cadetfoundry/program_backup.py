"""
Program backup (Phase 9): everything the instructor built, in one password-sealed file.

What's in it: the program folder (roster, join codes, cadet titles, lessons and their sealed notes, assignments,
instructor scenarios, service projects, fitness events, quiz edits, pilot files and pending join requests -- the live
classroom vote is never stored), the program key file and the Class PIN file (so the sealed files still open after a
restore), and the instructor's device settings (AI mode, Learn categories, portfolio sections).

Not in it: any Cadet's files. Each person backs up their own profile (Me -> Download encrypted backup); Cadets'
class records stay theirs.

The file is sealed with the backup password (scrypt + AES-256-GCM, vault.seal_backup) -- without it nobody can open it.

Restoring is a COMPLETE REPLACEMENT of the program, never a merge (security review, 2026-10-11): after it, the program
folder holds exactly what the backup holds -- a file the backup doesn't have is gone, not left behind. Cadets'
profiles are not touched. How it's done safely:

  1. Every file in the backup is decoded and checked before anything changes (allowed names only, sizes, JSON that
     parses or a sealed file). A bad backup changes nothing.
  2. The restored program is written to program.restoring/, with a ready marker as the last step.
  3. The current program is renamed to program.before-restore-<date>/ (with copies of the key files): the safety copy.
     The three newest are kept.
  4. program.restoring/ is renamed into place, then the key files are put in place.

If Cadet Foundry stops part-way, finish_pending() (run at every start) completes a restore that was ready, or puts the
safety copy back -- there's never "no program". To undo a restore by hand: close Cadet Foundry, rename program/ out of the
way, rename the newest program.before-restore-*/ to program/, and copy its _device_*.json files back as program.json
and admin.json in the data folder.
"""
from __future__ import annotations

import base64
import binascii
import json
import shutil
import time

from cadetfoundry import store, vault

VERSION = 1
PROGRAM_FILES = ("roster.json", "lessons.json", "lesson_notes.json", "assignments.json", "scenarios.json",
                 "service_projects.json", "fitness_events.json", "quiz_overrides.json", "pilot.json",
                 "pilot_snapshots.json", "feedback_cadets.json", "feedback_instructor.json",
                 "pilot_survey.json", "join_codes.json", "cadet_titles.json", "joins.json",
                 "feedback_daily.json")
DEVICE_FILES = ("program.json", "admin.json")
CONFIG_KEYS = ("ai_mode", "categories", "portfolio_sections")
MAX_FILE = 20 * 2 ** 20                          # one file in a backup; far more than a real program needs
KEEP_SAFETY_COPIES = 3
OLD = "vanguard"                                 # program backups made before the rename (0.2.6) still restore
_STAGING, _READY, _DEVICE = "program.restoring", "_RESTORE_READY", "_device"


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
    payload = {"cadetfoundry_program_backup": VERSION, "created": time.strftime("%Y-%m-%d %H:%M"), "files": files,
               "config": {k: cfg[k] for k in CONFIG_KEYS if k in cfg}}
    return {"cadetfoundry_program_backup_sealed": VERSION, **vault.seal_backup(json.dumps(payload).encode("utf-8"), password)}


def _decode(files: dict) -> dict[str, bytes]:
    """Every file, decoded and checked -- or ValueError, before anything on this device changes."""
    allowed = {"program/" + n for n in PROGRAM_FILES} | set(DEVICE_FILES)
    if not isinstance(files, dict) or not files or not set(files) <= allowed:
        raise ValueError("That backup contains files Cadet Foundry doesn't expect, so it wasn't restored.")
    out = {}
    for name, b64 in files.items():
        if not isinstance(b64, str) or len(b64) > MAX_FILE * 4 // 3 + 8:
            raise ValueError("That backup is damaged, so it wasn't restored.")
        try:
            raw = base64.b64decode(b64, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("That backup is damaged, so it wasn't restored.") from None
        if not vault.is_sealed(raw):              # sealed files are checked when they're opened; the rest must parse
            try:
                json.loads(raw.decode("utf-8"))
            except ValueError:
                raise ValueError("That backup is damaged, so it wasn't restored.") from None
        out[name] = raw
    return out


def restore(box: dict, password: str) -> dict:
    """Replaces the program on this device with the backup (a complete replacement). Cadets' profiles are not
    touched. A backup that fails any check changes nothing."""
    if not isinstance(box, dict) or box.get("cadetfoundry_program_backup_sealed", box.get(OLD + "_program_backup_sealed")) != VERSION:
        raise ValueError("That isn't a Cadet Foundry program backup.")
    try:
        data = json.loads(vault.open_backup(box, password).decode("utf-8"))
    except (vault.VaultError, ValueError):
        raise ValueError("Wrong backup password, or the file is damaged.") from None
    if not isinstance(data, dict) or data.get("cadetfoundry_program_backup", data.get(OLD + "_program_backup")) != VERSION:
        raise ValueError("That isn't a Cadet Foundry program backup.")
    files = _decode(data.get("files") or {})
    root = store.DATA
    root.mkdir(parents=True, exist_ok=True)
    finish_pending()                              # an earlier restore that was interrupted: settle it first
    staging = root / _STAGING
    shutil.rmtree(staging, ignore_errors=True)
    (staging / _DEVICE).mkdir(parents=True)
    for name, raw in files.items():
        target = staging / name[len("program/"):] if name.startswith("program/") else staging / _DEVICE / name
        target.write_bytes(raw)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (staging / _READY).write_text(stamp, encoding="utf-8")            # the staged program is complete
    live, before = root / "program", root / f"program.before-restore-{stamp}"
    n = 1
    while before.exists():
        before, n = root / f"program.before-restore-{stamp}-{n}", n + 1
    if live.exists():
        live.rename(before)                       # the safety copy
    else:
        before.mkdir()
    for name in DEVICE_FILES:
        if (root / name).exists():
            shutil.copy2(root / name, before / f"_device_{name}")
    try:
        staging.rename(live)
    except OSError:
        if not live.exists():
            _rollback(before)
        raise ValueError("The program couldn't be replaced, so it was left as it was.") from None
    finish_pending()                              # the key files, then the marker
    _prune_safety_copies()
    cfg = {k: v for k, v in (data.get("config") or {}).items() if k in CONFIG_KEYS}
    if cfg:
        store.save_config(cfg)
    return {"restored": sorted(files), "from": data.get("created", ""), "mode": "replace",
            "safety_copy": before.name}


def _rollback(before) -> None:
    """Put a safety copy back as the program (its key-file copies go back too)."""
    live = store.DATA / "program"
    before.rename(live)
    for name in DEVICE_FILES:
        copy = live / f"_device_{name}"
        if copy.exists():
            tmp = store.DATA / f"{name}.tmp"
            shutil.copy2(copy, tmp)
            tmp.replace(store.DATA / name)
            copy.unlink()


def finish_pending() -> None:
    """Settle a restore that was interrupted (called at every start, and around each restore). Idempotent."""
    root = store.DATA
    live, staging = root / "program", root / _STAGING
    if not live.exists():
        if staging.is_dir() and (staging / _READY).exists():
            staging.rename(live)                  # the staged restore was complete: finish it
        else:
            copies = sorted(root.glob("program.before-restore-*"), key=lambda p: p.stat().st_mtime)
            if copies:
                _rollback(copies[-1])             # it wasn't: put the program back as it was
    dev = live / _DEVICE
    if dev.is_dir():                              # the restored key files, after the folder is in place
        for f in dev.iterdir():
            if f.name in DEVICE_FILES:
                tmp = root / f"{f.name}.tmp"
                shutil.copy2(f, tmp)
                tmp.replace(root / f.name)
        shutil.rmtree(dev)
    (live / _READY).unlink(missing_ok=True)
    if staging.exists() and live.exists() and staging != live:
        shutil.rmtree(staging, ignore_errors=True)   # half-staged leftovers from an interrupted restore


def _prune_safety_copies() -> None:
    copies = sorted(store.DATA.glob("program.before-restore-*"), key=lambda p: p.stat().st_mtime)
    for old in copies[:-KEEP_SAFETY_COPIES]:
        shutil.rmtree(old, ignore_errors=True)
