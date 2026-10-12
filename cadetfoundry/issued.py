"""
Issued drives (owner, 2026-10-12): a Cadet Foundry USB drive made by the project carries Cadet Foundry/issued.json --
who it was issued to and the drive's own volume serial number -- signed with the release key (tools/make_usb.py, with
the owner's key; never on a device). If the app runs from a drive where that record is missing, doesn't verify, or
names a different drive, it was copied: Cadet Foundry shows the copyright notice every time it starts.

It only warns. Nothing is reported anywhere and nothing stops working -- locking an instructor out mid-class, or a
Cadet out of their work, would hurt the wrong people. Cadet drives made inside Cadet Foundry (cadet_drive.py) are
allowed copies and never warn. Installed copies aren't checked (the download needs an access code).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from cadetfoundry import integrity, store

ROOT = Path(__file__).resolve().parent.parent                     # this running copy: <drive>\Cadet Foundry
RECORD = "issued.json"
NOTICE = Path(__file__).resolve().parent / "legal" / "NOTICE.txt"
DATA_DIR = "Cadet Foundry Data"


def drive_root(root: Path = ROOT) -> Path | None:
    """The drive this copy runs from, if it's laid out as a Cadet Foundry USB drive."""
    if root.name == "Cadet Foundry" and (root.parent / DATA_DIR).is_dir():
        return root.parent
    return None


def volume_serial(path: Path) -> str | None:
    """The volume serial number of the drive holding `path` (Windows); None where it can't be read."""
    if os.name != "nt":
        return None
    import ctypes
    anchor = Path(path).resolve().anchor              # "E:\\"
    serial = ctypes.c_uint32()
    ok = ctypes.windll.kernel32.GetVolumeInformationW(anchor, None, 0, ctypes.byref(serial), None, None, None, 0)
    return f"{serial.value:08X}" if ok else None


def record_bytes(serial: str, issued_to: str, date: str) -> bytes:
    return json.dumps({"serial": serial, "to": issued_to, "date": date}, sort_keys=True).encode("utf-8")


def write(app_folder: Path, serial: str, issued_to: str, date: str, key) -> None:
    """Called by tools/make_usb.py with the owner's release key."""
    import base64
    data = record_bytes(serial, issued_to, date)
    (app_folder / RECORD).write_bytes(data)
    (app_folder / (RECORD + ".sig")).write_text(base64.b64encode(key.sign(data)).decode() + "\n")


def status(root: Path = ROOT, serial_of=volume_serial) -> dict:
    """{"drive": bool, "copied": bool, "to": str}. copied=True means: show the notice."""
    drive = drive_root(root)
    if drive is None:
        return {"drive": False, "copied": False, "to": ""}
    if (drive / DATA_DIR / "cadet_drive.json").exists():            # a Cadet drive: an allowed copy
        return {"drive": True, "copied": False, "to": ""}
    try:
        data = (root / RECORD).read_bytes()
        sig = (root / (RECORD + ".sig")).read_text()
        rec = json.loads(data)
    except (OSError, ValueError):
        return {"drive": True, "copied": True, "to": ""}
    here = serial_of(drive)
    ok = integrity.signature_ok(data, sig) and (here is None or here == rec.get("serial"))
    return {"drive": True, "copied": not ok, "to": "" if not ok else str(rec.get("to", ""))}


def notice() -> str:
    try:
        return NOTICE.read_text(encoding="utf-8")
    except OSError:
        return ""
