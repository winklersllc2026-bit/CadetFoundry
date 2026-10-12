"""
Where the class lives (owner, 2026-10-12): an instructor either installs Cadet Foundry on their teaching laptop or runs
it from a USB drive -- one home for the class, never both, because the two copies don't sync.

  * home()         where this copy keeps its data: "computer" or "usb" (shown in the app's top bar).
  * class_drives() an installed copy notices an instructor's USB drive plugged in: "your class lives there".
  * Backups        running from a USB drive on the instructor's OWN computer (they say so once), the class is copied
                   to that computer's disk every so often -- the newest 5 kept -- so a lost drive isn't a lost class.
                   Never on a school or shared computer. The copy is the data folder as it is on the drive: profiles,
                   class records and program data stay sealed with their PINs and the Class PIN.

Restore onto a new drive: python tools/make_usb.py E:\\ --restore "<backup.zip>" (or unzip it into the drive's
Cadet Foundry Data folder).
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import time
import zipfile
from pathlib import Path

from cadetfoundry import issued, store

KEEP = 5
EVERY = 30 * 60                                   # check for changes every 30 minutes while running
TRUST = "backup_computers.json"                   # in the drive's data folder: {machine id: true/false}
SKIP_SUFFIX = (".tmp", ".log", ".pid")
SKIP_NAMES = {"library_index.json"}               # a cache, rebuilt on its own
_lock = threading.Lock()
_last: dict = {}


def home() -> dict:
    drive = issued.drive_root()
    if drive is None:
        return {"where": "computer", "drive": ""}
    return {"where": "usb", "drive": str(drive).rstrip("\\/")}


def class_drives() -> list[str]:
    """Plugged-in USB drives holding an instructor's class (not Cadet drives) -- only asked by an installed copy."""
    if issued.drive_root() is not None:
        return []
    from cadetfoundry import cadet_drive
    out = []
    for root in cadet_drive.removable_drives():
        data = root / issued.DATA_DIR
        if (data / "admin.json").exists() and not (data / "cadet_drive.json").exists():
            out.append(str(root).rstrip("\\/"))
    return out


# ── backups of a USB class onto the instructor's own computer ───────────────
def machine_id() -> str:
    raw = f"{socket.gethostname()}|{os.environ.get('USERNAME') or os.environ.get('USER', '')}|{Path.home()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _trust() -> dict:
    try:
        return json.loads((store.DATA / TRUST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def trusted() -> bool | None:
    """True / False once the instructor has said whether this is their own computer; None if not asked yet."""
    v = _trust().get(machine_id())
    return v if isinstance(v, bool) else None


def set_trusted(yes: bool) -> None:
    t = _trust()
    t[machine_id()] = bool(yes)
    tmp = store.DATA / (TRUST + ".tmp")
    tmp.write_text(json.dumps(t), encoding="utf-8")
    tmp.replace(store.DATA / TRUST)


def backup_dir() -> Path:
    return Path.home() / "Cadet Foundry USB backups" / store.data_id()


def _files() -> list[Path]:
    return sorted(p for p in store.DATA.rglob("*") if p.is_file() and p.suffix not in SKIP_SUFFIX
                  and p.name not in SKIP_NAMES and p.name != TRUST)


def _fingerprint() -> str:
    h = hashlib.sha256()
    for p in _files():
        st = p.stat()
        h.update(f"{p.relative_to(store.DATA)}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()


def backups() -> list[dict]:
    d = backup_dir()
    return [{"name": p.name, "size": p.stat().st_size, "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))}
            for p in sorted(d.glob("class-*.zip"), reverse=True)] if d.is_dir() else []


def backup_now(force: bool = False) -> dict | None:
    """Copy the class to this computer if it's running from USB, on a computer the instructor trusts, and changed."""
    if home()["where"] != "usb" or trusted() is not True:
        return None
    with _lock:
        d = backup_dir()                             # first: it may write instance.id, which is part of the class
        fp = _fingerprint()
        if not force and _last.get("fp") == fp:
            return None
        d.mkdir(parents=True, exist_ok=True)
        out = d / f"class-{time.strftime('%Y%m%d-%H%M%S')}.zip"
        tmp = out.with_suffix(".tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for p in _files():
                z.write(p, p.relative_to(store.DATA).as_posix())
        tmp.replace(out)
        for old in sorted(d.glob("class-*.zip"), reverse=True)[KEEP:]:
            old.unlink(missing_ok=True)
        _last["fp"] = fp
        return {"file": str(out), "when": time.strftime("%Y-%m-%d %H:%M")}


def start() -> None:
    """At startup (server.py): back up now and then every EVERY seconds, while this copy runs from a USB drive."""
    if home()["where"] != "usb":
        return

    def loop():
        while True:
            try:
                backup_now()
            except OSError:
                pass                                   # a full disk or an unplugged drive: try again later
            time.sleep(EVERY)
    threading.Thread(target=loop, daemon=True, name="usb-backup").start()


def restore(zip_path: Path, data_dir: Path) -> int:
    """Unzip a class backup into an empty data folder (tools/make_usb.py --restore). Returns the files written."""
    if data_dir.exists() and any((data_dir / n).exists() for n in ("admin.json", "profiles.json")):
        raise ValueError(f"{data_dir} already has a class in it. Nothing was changed.")
    data_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            target = (data_dir / info.filename).resolve()
            if data_dir.resolve() not in target.parents:          # no paths that climb out of the folder
                raise ValueError("That backup has a bad file path in it. Nothing more was written.")
            if info.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(info))
            n += 1
    return n
