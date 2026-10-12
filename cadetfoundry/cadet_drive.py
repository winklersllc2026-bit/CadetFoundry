"""
Cadet flash drives (owner, 2026-10-12): the instructor makes a drive for a Cadet from Me, the Cadet studies at home
with it, and the work comes back when the drive is plugged into the instructor's computer.

Making a drive (instructor, with the Class PIN open):
  * The app is copied from this running copy (with its own Python), plus the official videos if chosen. Never the
    offline AI, never anyone else's data.
  * The drive's data folder gets the program's PUBLIC key only -- so a profile made on the drive shares its class
    records with this class -- and never the Class PIN, the program's private key or another Cadet's anything.
  * For a named Cadet: their profile (encrypted with their own PIN) and the lessons assigned to them. For "any Cadet":
    an empty drive set to one class; the Cadet makes their profile (with a PIN) the first time they open it.
  * A replacement for a lost drive is the same thing: a drive for that Cadet, from this computer's last synced copy.

Bringing work back (automatic, while the instructor is signed in with the class open): a drive from this program is
noticed when it's plugged in. Class records (store.CLASS_FILES) are merged both ways -- nothing done in class or at
home is lost; quiz counts add up -- and new lessons go out to the drive. Private files (check-ins, chats, notes,
letters) are never read or copied; they stay where they were written.

The drive marks itself with Cadet Foundry Data/cadet_drive.json. A Cadet Foundry running from such a drive is a
"Cadet drive": Cadet profiles only, a PIN required, no instructor setup, no classroom network, no sample class.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import string
import threading
import time
import uuid
from pathlib import Path

from cadetfoundry import __version__, instructor, lessons, profiles, security, store, vault

APP_DIR, DATA_DIR, MARK = "Cadet Foundry", "Cadet Foundry Data", "cadet_drive.json"
ROOT = Path(__file__).resolve().parent.parent                     # this running copy of Cadet Foundry
# What a drive needs from the app (tools/make_usb.py uses the same list).
APP_ITEMS = ["cadetfoundry", "web", "tools", "library", "books", "faith", "python", "run.py", "README.md", "LIBRARY.md",
             "SECURITY.md", "install-cadetfoundry.bat", "install-cadetfoundry.sh", "start-cadetfoundry.bat",
             "start-cadetfoundry.sh"]
_lock = threading.RLock()
_seen: dict[str, str] = {}                                        # drive id -> fingerprint at the last sync

START_BAT = r"""@echo off
title Cadet Foundry
rem Cadet Foundry from this USB drive. Nothing is installed on this computer; all data stays on the drive.
cd /d "%~dp0Cadet Foundry"
set "CADETFOUNDRY_DATA=%~dp0Cadet Foundry Data"
if exist "%~dp0Cadet Foundry\ollama\ollama.exe" set "CADETFOUNDRY_OLLAMA=%~dp0Cadet Foundry\ollama\ollama.exe"
echo.
echo   CADET FOUNDRY - running from this USB drive
echo   Keep this window open while you use Cadet Foundry.
echo   To stop: Me ^> Quit Cadet Foundry, or close this window. Then unplug the drive.
echo.
"%~dp0Cadet Foundry\python\python.exe" run.py {args} %*
if errorlevel 1 pause
"""

CADET_START_HERE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cadet Foundry — your drive</title>
<style>body { margin: 0; background: #f6f4ee; color: #1b1a17; font: 18px/1.6 system-ui, "Segoe UI", sans-serif; }
.w { max-width: 720px; margin: 0 auto; padding: 28px 18px 60px; } h1 { margin: 0 0 6px; } .file { font-family: Consolas, monospace;
background: #efe8d6; padding: 2px 7px; border-radius: 6px; } li { margin: 6px 0; }</style></head><body><div class="w">
<h1>✦ Your Cadet Foundry drive</h1>
<p>{who}Study at home with no internet. Version {version}.</p>
<ol>
<li>Plug this drive into a <b>Windows</b> computer.</li>
<li>Open the drive and double-click <span class="file">Start Cadet Foundry.bat</span>. A black window opens, then Cadet
Foundry opens in the browser. Leave the black window open while you study.</li>
<li>Sign in with <b>your</b> PIN{first}.</li>
<li>When you're done: <b>Me → Quit Cadet Foundry</b> (or close the black window), then unplug the drive.</li>
<li>Bring the drive to class. When your instructor plugs it in, your class work goes to them and any new lessons
come onto the drive. Your private notes and check-ins stay on the drive.</li>
</ol>
<p>Your work is saved on this drive, locked with your PIN. If you lose the drive, tell your instructor — they can
make you a new one with the work you last brought to class.</p>
<p style="color:#555;font-size:15px">Cadet Foundry is designed to support JROTC instruction. It is not an official JROTC, military or
school product. A free community project — the Cadet Foundry project.</p>
</div></body></html>
"""


# ── this copy ───────────────────────────────────────────────────────────────
def here() -> dict | None:
    """The mark when this running Cadet Foundry is a Cadet drive, else None."""
    try:
        m = json.loads((store.DATA / MARK).read_text(encoding="utf-8"))
        return m if isinstance(m, dict) and m.get("id") else None
    except (OSError, ValueError):
        return None


def claim(pid: str) -> None:
    """A Cadet made their profile on an "any Cadet" drive: it's theirs now."""
    m = here()
    if m is not None:
        m["for"] = pid
        _write_json(store.DATA / MARK, m)


# ── finding drives ──────────────────────────────────────────────────────────
def removable_drives() -> list[Path]:
    """Plugged-in USB flash drives. (Tests set CADETFOUNDRY_TEST_DRIVES to folders standing in for drives.)"""
    test = os.environ.get("CADETFOUNDRY_TEST_DRIVES")
    if test is not None:
        return [Path(p) for p in test.split(os.pathsep) if p]
    if os.name != "nt":
        out = []
        for base in (Path("/media"), Path("/run/media"), Path("/Volumes")):
            if base.is_dir():
                for p in base.glob("*") if base.name == "Volumes" else base.glob("*/*"):
                    if p.is_dir() and os.path.ismount(p):
                        out.append(p)
        return out
    import ctypes
    mask, out = ctypes.windll.kernel32.GetLogicalDrives(), []
    for i, letter in enumerate(string.ascii_uppercase):
        if mask >> i & 1 and ctypes.windll.kernel32.GetDriveTypeW(f"{letter}:\\") == 2:      # DRIVE_REMOVABLE
            if os.path.exists(f"{letter}:\\"):
                out.append(Path(f"{letter}:\\"))
    return out


def _label(root: Path) -> str:
    if os.name == "nt" and len(str(root)) <= 3:
        import ctypes
        buf = ctypes.create_unicode_buffer(261)
        if ctypes.windll.kernel32.GetVolumeInformationW(str(root), buf, 261, None, None, None, None, 0):
            return buf.value
    return root.name


def _mark(root: Path) -> dict | None:
    try:
        m = json.loads((root / DATA_DIR / MARK).read_text(encoding="utf-8"))
        return m if isinstance(m, dict) and m.get("id") else None
    except (OSError, ValueError):
        return None


def _drive_profiles(root: Path) -> list[dict]:
    try:
        idx = json.loads((root / DATA_DIR / "profiles.json").read_text(encoding="utf-8"))
        return [p for p in idx.get("profiles", []) if isinstance(p, dict)]
    except (OSError, ValueError):
        return []


def _program_id() -> str:
    pub = security.program_public()
    return vault.key_id(pub) if pub else ""


def describe(root: Path) -> dict:
    """What's on a drive, and whether a Cadet drive may be made on it."""
    root = Path(root)
    try:
        du = shutil.disk_usage(root)
        free, total = du.free, du.total
    except OSError:
        free = total = 0
    out = {"path": str(root), "label": _label(root), "free": free, "total": total}
    data = root / DATA_DIR
    running_here = any(p == root or root in p.parents for p in (ROOT.resolve(), store.DATA.resolve()))
    m = _mark(root)
    if running_here:
        out.update(state="this", note="Cadet Foundry is running from this drive.")
    elif m:
        people = _drive_profiles(root)
        out.update(state="cadet" if m.get("program") == _program_id() else "other",
                   cadet=(people[0]["name"] if people else ""), cadet_id=m.get("for", ""), unit_name=m.get("unit_name", ""),
                   note="" if m.get("program") == _program_id() else "A Cadet drive from another class's Cadet Foundry.")
    elif (data / "admin.json").exists() or (data / "program.json").exists():
        out.update(state="instructor", note="An instructor's Cadet Foundry drive — it's never changed from here.")
    elif (data / "profiles").is_dir() and any((data / "profiles").iterdir()):
        out.update(state="people", note="Has Cadet Foundry profiles on it — it's never changed from here.")
    else:
        out.update(state="blank", note="")
    return out


def drives() -> list[dict]:
    return [describe(r) for r in removable_drives()]


def app_bytes(videos: bool) -> int:
    total = 0
    for item in APP_ITEMS:
        p = ROOT / item
        if p.is_file():
            total += p.stat().st_size
        elif p.is_dir():
            total += sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and "__pycache__" not in f.parts)
    if videos:
        total += sum(f.stat().st_size for f in _videos())
    return total


def _videos() -> list[Path]:
    v = ROOT / "videos"
    return sorted(v.glob("dvids-*.mp4")) + ([v / "status.json"] if (v / "status.json").exists() else []) if v.is_dir() else []


# ── encrypted files, read and written straight from a folder ────────────────
def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _read_class(folder: Path, name: str, key: bytes | None):
    """One class-record file from a profile folder: a list (.jsonl), a value (.json), or None if it isn't there."""
    try:
        data = (folder / name).read_bytes()
    except OSError:
        return None
    if vault.is_sealed(data):
        data = vault.open_sealed(key, data, name)
    text = data.decode("utf-8")
    if name.endswith(".jsonl"):
        out = []
        for line in text.splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
        return out
    try:
        return json.loads(text)
    except ValueError:
        return None


def _write_class(folder: Path, name: str, key: bytes | None, value) -> None:
    text = ("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in value) if name.endswith(".jsonl")
            else json.dumps(value, indent=2, ensure_ascii=False))
    data = text.encode("utf-8")
    if key is not None:
        data = vault.seal(key, data, name)
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / (name + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(folder / name)


def _class_key_in(folder: Path, priv: bytes) -> bytes | None:
    """A profile folder's class key, opened with the program's private key (None: the profile has no PIN)."""
    st = json.loads((folder / "security.json").read_text(encoding="utf-8")) if (folder / "security.json").exists() else {}
    if not st.get("vault"):
        return None
    box = st.get("class_for") or {}
    pub = security.program_public()
    if not pub or box.get("to") != vault.key_id(pub):
        raise LookupError("waiting")                  # not shared with this class yet
    return vault.open_from(priv, box, "class key")


# The last merged class records of each Cadet with a drive: what both copies agreed on. Sealed with the program's
# data key (instructor only). With it, work done on both sides adds up instead of one side winning.
def _base_path(pid: str) -> Path:
    return store.DATA / "program" / "sync" / f"{pid}.json"


def _read_base(priv: bytes, pid: str) -> dict | None:
    try:
        raw = _base_path(pid).read_bytes()
        return json.loads(vault.open_sealed(vault.program_data_key(priv), raw, "sync base").decode("utf-8"))
    except (OSError, vault.VaultError, ValueError):
        return None


def _save_base(priv: bytes, pid: str, base: dict) -> None:
    path = _base_path(pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(vault.seal(vault.program_data_key(priv), json.dumps(base).encode("utf-8"), "sync base"))
    tmp.replace(path)


# ── merging ─────────────────────────────────────────────────────────────────
_STAMPS = ("updated", "completed", "verified", "last", "logged", "started", "date", "created")


def _newer(a, b):
    """Two changed versions of one record: the newer one, else the finished one, else the drive's (b)."""
    def stamp(x):
        if not isinstance(x, dict):
            return ""
        return max((str(x.get(k)) for k in _STAMPS if x.get(k) not in (None, "")), default="")
    if isinstance(a, dict) and isinstance(b, dict):
        if (a.get("state") == "complete") != (b.get("state") == "complete"):
            return a if a.get("state") == "complete" else b
    sa, sb = stamp(a), stamp(b)
    return a if sa > sb else b


_GONE = object()


def _three_way(b, l, d):
    """One record: base, laptop, drive (_GONE = not there). Returns the merged value or _GONE."""
    if l == d:
        return l
    if l == b:
        return d
    if d == b:
        return l
    if l is _GONE:
        return d
    if d is _GONE:
        return l
    return _newer(l, d)


def _merge_dict(b: dict | None, l: dict, d: dict) -> dict:
    b = b or {}
    out = {}
    for k in list(l) + [k for k in d if k not in l]:
        v = _three_way(b.get(k, _GONE), l.get(k, _GONE), d.get(k, _GONE))
        if v is not _GONE:
            out[k] = v
    return out


def _row_key(r) -> str:
    return f"id:{r['id']}" if isinstance(r, dict) and r.get("id") else "row:" + json.dumps(r, sort_keys=True)


def _merge_rows(b: list | None, l: list, d: list) -> list:
    bk = {_row_key(r): r for r in (b or [])}
    lk = {_row_key(r): r for r in l}
    dk = {_row_key(r): r for r in d}
    out = []
    for k in list(lk) + [k for k in dk if k not in lk]:
        v = _three_way(bk.get(k, _GONE), lk.get(k, _GONE), dk.get(k, _GONE))
        if v is not _GONE:
            out.append(v)
    return out


def _merge_study(b: dict | None, l: dict, d: dict) -> dict:
    """Quiz counts: what was there before, plus what each side added since (practice at home and in class both
    count). Without a base, the larger count is kept -- never counted twice."""
    out = {}
    for q in set(l) | set(d):
        lv, dv = l.get(q) or {}, d.get(q) or {}
        r = {}
        for f in ("right", "wrong"):
            if b is None:
                r[f] = max(lv.get(f, 0), dv.get(f, 0))
            else:
                bv = (b.get(q) or {}).get(f, 0)
                r[f] = max(0, bv + (lv.get(f, bv) - bv) + (dv.get(f, bv) - bv))
        last = max(lv.get("last", 0) or 0, dv.get("last", 0) or 0)
        if last:
            r["last"] = last
        out[q] = r
    return out


def merge(name: str, b, l, d):
    """One class-record file, merged (b: the last agreed copy or None; l: this computer's; d: the drive's)."""
    if l is None:
        return d
    if d is None:
        return l
    if name == "study.json" and isinstance(l, dict) and isinstance(d, dict):
        return _merge_study(b if isinstance(b, dict) else None, l, d)
    if isinstance(l, list) and isinstance(d, list):
        return _merge_rows(b if isinstance(b, list) else None, l, d)
    if isinstance(l, dict) and isinstance(d, dict):
        return _merge_dict(b if isinstance(b, dict) else None, l, d)
    return d


def _news(b: dict, d: dict) -> dict:
    """What the drive brought: lessons finished and quiz answers since the last sync."""
    def answers(s):
        return sum((v or {}).get("right", 0) + (v or {}).get("wrong", 0) for v in (s or {}).values()) if isinstance(s, dict) else 0
    done = lambda w: {k for k, v in (w or {}).items() if isinstance(v, dict) and v.get("state") == "complete"} \
        if isinstance(w, dict) else set()
    rows = lambda x: len(x) if isinstance(x, list) else 0
    return {"answers": max(0, answers(d.get("study.json")) - answers(b.get("study.json"))),
            "lessons": len(done(d.get("assignments.json")) - done(b.get("assignments.json"))),
            "entries": sum(max(0, rows(d.get(n)) - rows(b.get(n))) for n in ("exams.jsonl", "scenarios.jsonl",
                                                                             "service.jsonl", "fitness.jsonl"))}


# ── lessons out to a drive ──────────────────────────────────────────────────
def _program_out(data: Path, pid: str = "", unit: str = "") -> int:
    """The lessons this Cadet has (or, before they've made a profile, their class has), written to the drive."""
    rows = []
    for a in lessons.all_assignments():
        if pid and pid in lessons.recipients(a):
            rows.append({**a, "everyone": False, "cadets": [pid]})
        elif not pid and unit and unit in a.get("units", []):
            rows.append({**a, "everyone": False, "cadets": []})     # sync_unit adds the Cadet when they join
    ids = {a["lesson"] for a in rows}
    _write_json(data / "program" / "assignments.json", rows)
    _write_json(data / "program" / "lessons.json", [x for x in lessons.all_lessons() if x["id"] in ids])
    return len(rows)


# ── making a drive ──────────────────────────────────────────────────────────
_job: dict = {}


def job() -> dict:
    return dict(_job)


def start_make(priv: bytes, path: str, pid: str = "", unit: str = "", videos: bool = True, erase: bool = False) -> dict:
    """Check everything, then copy in the background (job() reports progress). Raises ValueError with a plain reason."""
    root = Path(path)
    if str(root) not in {str(r) for r in removable_drives()}:
        raise ValueError("That flash drive isn't plugged in any more.")
    info = describe(root)
    if info["state"] in ("this", "instructor", "people", "other"):
        raise ValueError(info["note"] + " Use a blank flash drive.")
    if not (ROOT / "python").is_dir() and not os.environ.get("CADETFOUNDRY_TEST_DRIVES"):
        raise ValueError("Make Cadet drives from the installed Cadet Foundry (or from a Cadet Foundry flash drive).")
    ov = instructor.roster(priv)
    p = profiles.get(pid) if pid else None
    if pid:
        if not p or p["kind"] != "cadet":
            raise ValueError("Pick a Cadet from your class.")
        if not security.has_pin(pid):
            raise ValueError(f"{p['name']} doesn't have a PIN yet. A drive goes home, so it needs one: sign in to "
                             f"{p['name']} on this computer, then 👤 Me → Security → Set a PIN.")
        unit = (ov["cadets"].get(pid) or {}).get("unit") or unit
        try:
            _class_key_in(profiles.folder(pid), priv)
        except LookupError:
            raise ValueError(f"{p['name']} needs to sign in once on this computer first, so their class work is "
                             "shared with your class.") from None
    units = {u["id"]: u["name"] for u in ov["units"]}
    if not pid and unit not in units:
        raise ValueError("Pick the class this drive is for.")
    if info["state"] == "cadet" and info.get("cadet_id") and info["cadet_id"] != pid and not erase:
        raise ValueError(f"This is {info['cadet'] or 'another Cadet'}'s drive. Their private notes are only on it. "
                         "To give it to someone else, confirm that it may be erased.")
    need = app_bytes(videos) + 20 * 2**20
    have = info["free"] + (sum(f.stat().st_size for f in (root / APP_DIR).rglob("*") if f.is_file())
                           if (root / APP_DIR).is_dir() else 0)
    if have < need:
        raise ValueError(f"This drive has room for {have / 2**30:.1f} GB; it needs {need / 2**30:.1f} GB"
                         f"{' (or leave the videos off)' if videos else ''}. Use a bigger flash drive.")
    with _lock:
        if _job.get("running"):
            raise ValueError("A drive is already being made. Wait for it to finish.")
        _job.clear()
        _job.update(running=True, pct=0, msg="Starting…", path=str(root), name=p["name"] if p else "", error="", done=False)
    args = (priv, root, pid, unit, units.get(unit, ""), videos, info)
    threading.Thread(target=_make, args=args, daemon=True).start()
    return job()


def _make(priv, root: Path, pid, unit, unit_name, videos, info) -> None:
    try:
        if info["state"] == "cadet":                     # a drive coming back: bring its work in first
            _job["msg"] = "Bringing in the work already on this drive…"
            sync(priv, root, force=True)
        make(priv, root, pid, unit, unit_name, videos, progress=lambda pct, msg: _job.update(pct=pct, msg=msg))
        _job.update(pct=100, msg="Done", done=True)
    except Exception as e:                               # noqa: BLE001 -- reported to the instructor
        _job.update(error=f"The drive wasn't finished: {e}", done=True)
    finally:
        _job["running"] = False


def make(priv: bytes, root: Path, pid: str = "", unit: str = "", unit_name: str = "", videos: bool = True,
         progress=lambda pct, msg: None) -> dict:
    root = Path(root)
    app, data = root / APP_DIR, root / DATA_DIR
    files = [(ROOT / i, app / i) for i in APP_ITEMS if (ROOT / i).exists()]
    plan = []
    for src, dst in files:
        if src.is_dir():
            plan += [(f, dst / f.relative_to(src)) for f in src.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
        else:
            plan.append((src, dst))
    if videos:
        plan += [(f, app / "videos" / f.name) for f in _videos()]
    total = sum(f.stat().st_size for f, _ in plan) or 1
    for item in APP_ITEMS:                               # replace the app; the data folder is handled below
        t = app / item
        if t.is_dir():
            shutil.rmtree(t)
        elif t.exists():
            t.unlink()
    if not videos and (app / "videos").is_dir():
        shutil.rmtree(app / "videos")
    shutil.rmtree(app / "ollama", ignore_errors=True)    # never the offline AI on a Cadet drive
    done = 0
    for src, dst in plan:
        if dst.exists() and dst.stat().st_size == src.stat().st_size and "videos" in dst.parts:
            done += src.stat().st_size                   # a video already there (they never change)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        done += src.stat().st_size
        progress(min(95, math.floor(95 * done / total)), f"Copying Cadet Foundry… {done / 2**30:.2f} of {total / 2**30:.2f} GB")
    progress(96, "Setting up the Cadet's data…")
    old = _mark(root)
    keep_profile = bool(old and old.get("for") == pid and pid)          # the same Cadet's drive: keep their private files
    if data.exists() and not keep_profile:
        shutil.rmtree(data)
    data.mkdir(parents=True, exist_ok=True)
    pub = security.program_public()
    _write_json(data / "program.json", {"public": pub.hex()})          # the public key only -- never the private one
    for leftover in ("admin.json",):
        (data / leftover).unlink(missing_ok=True)
    conf = {"program": store.program(), "ai_mode": "library"}
    if store.config().get("terms"):
        conf["terms"] = store.config()["terms"]          # the instructor accepted the terms for their program
    _write_json(data / "config.json", conf)
    mark = {"id": (old or {}).get("id") or uuid.uuid4().hex[:12], "program": vault.key_id(pub), "unit": unit,
            "unit_name": unit_name, "for": pid, "made": time.strftime("%Y-%m-%d"), "version": __version__}
    if pid:
        p = profiles.get(pid)
        src = profiles.folder(pid)
        dst = data / "profiles" / pid
        if keep_profile and dst.is_dir():
            sync(priv, root, force=True)                 # their work comes in, new lessons go out
        else:
            shutil.rmtree(dst, ignore_errors=True)
            with store._lock:
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*.tmp"))
            # what both copies agree on right now: later work on either side adds to it
            ck = _class_key_in(src, priv)
            _save_base(priv, pid, {n: _read_class(src, n, ck) for n in store.CLASS_FILES})
        _write_json(data / "profiles.json", {"profiles": [{**{k: v for k, v in p.items() if k != "has_pin"},
                                                           "joined": unit_name or p.get("joined", "")}]})
    _write_json(data / MARK, mark)
    _program_out(data, pid, unit)
    _write_launchers(root, profiles.get(pid)["name"] if pid else "", unit_name)
    _remember(mark, pid)
    progress(100, "Done")
    return mark


def _write_launchers(root: Path, name: str, unit_name: str) -> None:
    (root / "Start Cadet Foundry.bat").write_bytes(
        START_BAT.replace("{args}", "").replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    who = f"This drive belongs to <b>{_html(name)}</b>. " if name else (f"For a Cadet in <b>{_html(unit_name)}</b>. " if unit_name else "")
    first = "" if name else " — the first time, make your profile: your name and a PIN only you know"
    notice = Path(__file__).resolve().parent / "legal" / "NOTICE.txt"      # the copyright notice; this copy is allowed
    if notice.exists():
        text = notice.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n")   # Notepad-friendly
        (root / "NOTICE - READ FIRST.txt").write_bytes(text.encode("utf-8"))
    (root / "START HERE.html").write_text(CADET_START_HERE.replace("{who}", who).replace("{first}", first)
                                          .replace("{version}", __version__), encoding="utf-8")


def _html(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _drives_file() -> Path:
    return store.DATA / "program" / "drives.json"


def _remember(mark: dict, pid: str) -> None:
    """This computer's list of the Cadet drives it made (shown in Me; no records in it)."""
    try:
        rows = json.loads(_drives_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rows = {}
    rows[mark["id"]] = {"for": pid, "unit": mark.get("unit", ""), "made": mark["made"],
                        "synced": rows.get(mark["id"], {}).get("synced", "")}
    _write_json(_drives_file(), rows)


def made() -> dict:
    try:
        return json.loads(_drives_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ── bringing work back ──────────────────────────────────────────────────────
def _fingerprint(root: Path, pids: list[str]) -> str:
    h = hashlib.sha256()
    for folder in [root / DATA_DIR / "profiles" / p for p in pids] + [profiles.ROOT / p for p in pids]:
        for n in sorted(store.CLASS_FILES):
            try:
                st = (folder / n).stat()
                h.update(f"{folder}|{n}|{st.st_size}|{st.st_mtime_ns}".encode())
            except OSError:
                pass
    # their lessons only, as the drive gets them (another Cadet joining the same assignment isn't a change here)
    mine = [{k: v for k, v in a.items() if k not in ("cadets", "units", "everyone", "to")}
            for a in lessons.all_assignments() if any(p in lessons.recipients(a) for p in pids)]
    ids = {a["lesson"] for a in mine}
    h.update(json.dumps([mine, [x for x in lessons.all_lessons() if x["id"] in ids]], sort_keys=True).encode())
    return h.hexdigest()


def scan(priv: bytes) -> list[dict]:
    """Every plugged-in drive of this class: synced if anything changed. Returns a notice per drive synced."""
    out = []
    for root in removable_drives():
        m = _mark(root)
        if not m or m.get("program") != _program_id() or describe(root)["state"] != "cadet":
            continue
        try:
            r = sync(priv, root)
        except Exception as e:                           # noqa: BLE001 -- shown to the instructor, nothing written
            r = {"drive": str(root), "error": f"Couldn't bring in the drive in {root}: {e}"}
        if r:
            out.append(r)
    return out


def sync(priv: bytes, root: Path, force: bool = False) -> dict | None:
    """Merge one drive with this computer. None when nothing changed since the last time."""
    root = Path(root)
    data = root / DATA_DIR
    mark = _mark(root)
    if not mark or mark.get("program") != _program_id():
        raise ValueError("This drive isn't from this class.")
    people = [p for p in _drive_profiles(root) if profiles.role_of(p.get("kind")) == "cadet"]
    pids = [p["id"] for p in people]
    fp = _fingerprint(root, pids)
    if not force and _seen.get(mark["id"]) == fp:
        return None
    notices, new_people = [], []
    roster = instructor.roster(priv)
    for p in people:
        pid, dfold = p["id"], data / "profiles" / p["id"]
        try:
            dck = _class_key_in(dfold, priv)
        except LookupError:
            notices.append(f"{p['name']}'s drive isn't shared with this class yet — they need to sign in on it once.")
            continue
        with store._lock:
            if profiles.get(pid) is None:                # made on an "any Cadet" drive: they join this class now
                lfold = profiles.ROOT / pid
                shutil.copytree(dfold, lfold, ignore=shutil.ignore_patterns("*.tmp"), dirs_exist_ok=True)
                _add_profile(p)
                unit = mark.get("unit") or ""
                if unit in {u["id"] for u in roster["units"]}:
                    instructor.assign(priv, pid, unit)
                    lessons.sync_unit(pid, unit)
                brought = {n: _read_class(dfold, n, dck) for n in store.CLASS_FILES}
                _save_base(priv, pid, brought)
                new_people.append((p["name"], _news({}, brought)))
                mark["for"] = pid
                continue
            lfold = profiles.folder(pid)
            try:
                lck = _class_key_in(lfold, priv)
            except LookupError:
                lck = dck                                 # the same Cadet: the same class key
            base = _read_base(priv, pid) or {}
            merged, drive_had = {}, {}
            for n in store.CLASS_FILES:
                l, d = _read_class(lfold, n, lck), _read_class(dfold, n, dck)
                drive_had[n] = d
                m = merge(n, base.get(n), l, d)
                if m is not None:
                    merged[n] = m
            for n, v in merged.items():                  # everything read first; now write both sides
                _write_class(lfold, n, lck, v)
                _write_class(dfold, n, dck, v)
            _save_base(priv, pid, merged)
            notices.append(_say(p["name"], _news(base, drive_had)))      # what was done on the drive
    sent = 0
    for pid in pids:
        if profiles.get(pid):
            sent += _program_out(data, pid)
    _write_json(data / MARK, mark)
    rows = made()
    rows.setdefault(mark["id"], {"for": mark.get("for", ""), "unit": mark.get("unit", ""), "made": mark.get("made", "")})
    rows[mark["id"]].update(synced=time.strftime("%Y-%m-%d %H:%M"), **({"for": mark["for"]} if mark.get("for") else {}))
    _write_json(_drives_file(), rows)
    _seen[mark["id"]] = _fingerprint(root, pids)
    for name, news in new_people:
        did = _say(name, news).split(": ", 1)[1]
        notices.append(f"{name} joined your class from their drive" + ("." if did.startswith("up to date") else f" — {did}"))
    return {"drive": str(root), "names": [p["name"] for p in people], "notices": notices, "lessons_sent": sent}


def _say(name: str, news: dict) -> str:
    bits = []
    if news["lessons"]:
        bits.append(f"{news['lessons']} lesson{'s' if news['lessons'] != 1 else ''} finished")
    if news["answers"]:
        bits.append(f"{news['answers']} quiz answer{'s' if news['answers'] != 1 else ''}")
    if news["entries"]:
        bits.append(f"{news['entries']} other entr{'ies' if news['entries'] != 1 else 'y'}")
    return f"{name}'s drive: " + (", ".join(bits) + " — brought in ✓" if bits else "up to date ✓")


def _add_profile(p: dict) -> None:
    """A profile made on a drive joins this computer's list (a second Cadet with the same name gets a number)."""
    with profiles._lock:
        idx = profiles._index()
        if any(x["id"] == p["id"] for x in idx["profiles"]):
            return
        name, n = p["name"], 2
        while any(x["name"].lower() == name.lower() for x in idx["profiles"]):
            name, n = f"{p['name']} ({n})", n + 1
        idx["profiles"].append({"id": p["id"], "name": name, "created": p.get("created", time.strftime("%Y-%m-%d")),
                                "kind": "cadet", **({"joined": p["joined"]} if p.get("joined") else {})})
        profiles._save(idx)
