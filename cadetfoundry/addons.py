"""
Optional add-ons, installed from inside Cadet Foundry (Me tab) with a progress bar -- no console window, no setup script.

    Offline AI: Ollama (ollama.com) + the qwen2.5 3B model (about 2 GB). On Windows the official installer is
                downloaded, its Authenticode signature checked (must be valid and signed by Ollama), then run
                silently. Then the model is pulled through Ollama's own API.
    Voice:      the Vosk speech recognizer (pip) + its small English model (about 40 MB, alphacephei.com).
    Videos:     the official DVIDS videos (about 1.3 GB) from cadetfoundry.org, with the instructor's access code
                (owner, 2026-10-12: a downloaded copy has none, and they play offline once saved). The list is signed
                with the release key and every piece is checked by SHA-256; a broken download carries on next time.
                tools/video_pack.py publishes them.

Needs internet once; afterwards both run offline. One job at a time, in a background thread; the page polls
status(). Installing changes the whole device, so it needs the device admin PIN when one is set (server.py).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from cadetfoundry import engine, integrity, videos, voice

WINDOWS = platform.system() == "Windows"
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)       # never flash a console window on Windows
MODEL = "qwen2.5:3b"                                      # same default as tools/setup.py
OLLAMA_SETUP = "https://ollama.com/download/OllamaSetup.exe"
# Fixed versions, checked by SHA-256 after download (a changed or tampered file is refused). See SECURITY.md, Dependencies.
PIP_PYZ = ("https://bootstrap.pypa.io/pip/zipapp/pip-26.2.1.pyz",   # pip as one file, for the installer's embedded Python
           "91d5fd9f6f25549fd839c60536c6f1b945316ce3588d34a605635b6071c91526")
VOICE_MODEL = ("https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
               "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498")
VOSK = "vosk==0.3.45"
UA = {"User-Agent": "Cadet Foundry"}
SITE = os.environ.get("CADETFOUNDRY_SITE") or "https://cadetfoundry.org"     # where the video pack comes from
VIDEO_SIZE = "about 1.3 GB"
_KEY = None                                               # tests: the key the video list is signed with

_lock = threading.Lock()
_job: dict = {}


# ── status ──────────────────────────────────────────────────────────────────

def ollama_exe() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    if WINDOWS:
        p = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        return str(p) if p.exists() else None
    return None


def _tags() -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{engine.OLLAMA}/api/tags", timeout=3) as r:
            return [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return None


def status() -> dict:
    tags = _tags()
    return {"ai": {"installed": bool(tags), "ollama": bool(ollama_exe()) or tags is not None, "model": MODEL,
                   "size": "about 2 GB"},
            "voice": {"installed": voice.available(), "size": "about 50 MB"},
            "videos": _videos_status(),
            "job": dict(_job)}


def start_ollama() -> bool:
    """Ollama installed but not running (e.g. after a restart): start it in the background, hidden."""
    if _tags() is not None:
        return True
    exe = ollama_exe()
    if not exe:
        return False
    subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=HIDDEN)
    for _ in range(30):
        if _tags() is not None:
            return True
        time.sleep(1)
    return False


# ── jobs ────────────────────────────────────────────────────────────────────

def _videos_status() -> dict:
    r = videos.listing()
    return {"installed": r["dvids"] > 0 and r["saved"] >= r["dvids"], "saved": r["saved"], "total": r["dvids"],
            "size": VIDEO_SIZE, "folder": str(videos.VIDEOS)}


def install(name: str, code: str = "") -> dict:
    if name not in ("ai", "voice", "videos"):
        raise ValueError("Unknown add-on.")
    if name == "videos" and len(_norm(code)) < 8:
        raise ValueError("Type your access code — the one you downloaded Cadet Foundry with.")
    with _lock:
        if _job.get("state") == "running":
            raise ValueError("Another add-on is installing — wait for it to finish.")
        _job.clear()
        _job.update({"name": name, "state": "running", "step": "Starting…", "pct": 0, "msg": ""})
    threading.Thread(target=_run, args=(name, code), daemon=True).start()
    return dict(_job)


def remove_videos() -> dict:
    """The opt-out: delete the saved official videos (they can be downloaded again)."""
    with _lock:
        if _job.get("state") == "running":
            raise ValueError("An add-on is installing — wait for it to finish.")
    freed = 0
    for f in list(videos.VIDEOS.glob("dvids-*.mp4")):
        freed += f.stat().st_size
        f.unlink()
    shutil.rmtree(videos.VIDEOS / ".download", ignore_errors=True)
    return {"ok": True, "freed_mb": freed >> 20}


def _set(**kw) -> None:
    with _lock:
        _job.update(kw)


def _run(name: str, code: str = "") -> None:
    try:
        if name == "videos":
            n = _install_videos(code)
            _set(state="done", pct=100, step="Done", msg=f"Saved. {n} official videos now play with no internet.")
            return
        (_install_ai if name == "ai" else _install_voice)()
        _set(state="done", pct=100, step="Done", msg="Installed. " + ("Ask Cadet Foundry a question to try it."
                                                                      if name == "ai" else "Reload the page to see the 🎤 button."))
    except Exception as e:                              # shown to the Soldier as is -- every message is plain
        _set(state="error", msg=str(e) or "Something went wrong.")


def _download(url: str, dest: Path, step: str, lo: int, hi: int, sha256: str | None = None) -> None:
    """Save url to dest, moving the progress bar from lo to hi percent. With sha256, refuse a file that doesn't match."""
    _set(step=step)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r, open(dest, "wb") as f:
            total, done = int(r.headers.get("Content-Length") or 0), 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    _set(pct=lo + (hi - lo) * done // total, step=f"{step} ({done >> 20} of {total >> 20} MB)")
    except OSError as e:
        raise RuntimeError(f"Couldn't download — is this device online? ({e})") from e
    if sha256 and hashlib.sha256(dest.read_bytes()).hexdigest() != sha256:
        dest.unlink(missing_ok=True)
        raise RuntimeError("The download doesn't match its known fingerprint, so it wasn't used.")


def _signed_by_ollama(exe: Path) -> bool:
    """Windows Authenticode check of the downloaded installer: valid signature, signed by Ollama."""
    ps = ("$s = Get-AuthenticodeSignature -LiteralPath $env:CADETFOUNDRY_CHECK; "
          "Write-Output $s.Status; Write-Output $s.SignerCertificate.Subject")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, timeout=60, creationflags=HIDDEN, env={**os.environ, "CADETFOUNDRY_CHECK": str(exe)})
    except (OSError, subprocess.SubprocessError):
        return False
    lines = r.stdout.splitlines()
    return len(lines) >= 2 and lines[0].strip() == "Valid" and "ollama" in lines[1].lower()


def _install_ai() -> None:
    if not ollama_exe() and _tags() is None:
        if not WINDOWS:
            raise RuntimeError("Install Ollama from ollama.com (or run install-cadetfoundry.sh), then try again.")
        tmp = Path(tempfile.mkdtemp(prefix="cadetfoundry-"))
        try:
            setup = tmp / "OllamaSetup.exe"
            _download(OLLAMA_SETUP, setup, "Downloading Ollama", 0, 40)
            _set(step="Checking Ollama's signature")
            if not _signed_by_ollama(setup):
                raise RuntimeError("The Ollama download isn't signed by Ollama, so it wasn't installed.")
            _set(step="Installing Ollama", pct=42)
            r = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"],
                               creationflags=HIDDEN, timeout=1800)
            if r.returncode != 0:
                raise RuntimeError("Ollama's installer didn't finish.")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    _set(step="Starting Ollama", pct=45)
    if not start_ollama():
        raise RuntimeError("Ollama is installed but didn't start. Restart the computer and try again.")
    _set(step=f"Downloading the AI model ({MODEL})", pct=46)
    req = urllib.request.Request(f"{engine.OLLAMA}/api/pull", data=json.dumps({"model": MODEL, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        for line in r:
            ev = json.loads(line or b"{}")
            if ev.get("error"):
                raise RuntimeError(f"Couldn't download the model: {ev['error']}")
            if ev.get("total") and ev.get("completed"):
                _set(pct=46 + 53 * ev["completed"] // ev["total"],
                     step=f"Downloading the AI model ({ev['completed'] >> 20} of {ev['total'] >> 20} MB)")
    if not _tags():
        raise RuntimeError("The model didn't finish downloading. Try again.")
    threading.Thread(target=engine.warm_up, daemon=True).start()


def _python() -> str:
    """python.exe next to pythonw.exe (the installer starts Cadet Foundry with pythonw)."""
    exe = Path(sys.executable)
    console = exe.with_name("python.exe" if WINDOWS else exe.name.replace("pythonw", "python"))
    return str(console if console.exists() else exe)


def _install_voice() -> None:
    try:
        import vosk  # noqa: F401
    except Exception:
        _set(step="Installing the speech recognizer", pct=5)
        here = Path(sys.executable).parent
        if any(here.glob("python3*._pth")):            # Python bundled by the Windows installer: no pip inside
            tmp = Path(tempfile.mkdtemp(prefix="cadetfoundry-"))
            try:
                pyz = tmp / "pip.pyz"
                _download(PIP_PYZ[0], pyz, "Getting pip", 5, 15, sha256=PIP_PYZ[1])
                cmd = [_python(), str(pyz), "install", "--quiet", "--disable-pip-version-check",
                       "--target", str(here / "Lib" / "site-packages"), "--only-binary=:all:", VOSK]
                r = subprocess.run(cmd, capture_output=True, text=True, creationflags=HIDDEN, timeout=900)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            r = subprocess.run([_python(), "-m", "pip", "install", "--quiet", "--disable-pip-version-check", VOSK],
                               capture_output=True, text=True, creationflags=HIDDEN, timeout=900)
        if r.returncode != 0:
            raise RuntimeError("Couldn't install the speech recognizer. " + (r.stderr or r.stdout)[-300:])
        import importlib
        importlib.invalidate_caches()
    dest = voice.MODEL_DIR
    if not (dest.exists() and any(dest.iterdir())):
        tmp = Path(tempfile.mkdtemp(prefix="cadetfoundry-"))
        try:
            z = tmp / "model.zip"
            _download(VOICE_MODEL[0], z, "Downloading the English voice model", 30, 90, sha256=VOICE_MODEL[1])
            _set(step="Unpacking the voice model", pct=92)
            _unpack(z.read_bytes(), dest)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ── official videos ─────────────────────────────────────────────────────────

def _norm(code: str) -> str:
    """An access code as typed -> as stored (the site and tools/pilot_access.py read it the same way)."""
    return "".join(c for c in str(code or "").upper() if c.isascii() and c.isalnum())[:40]


def _pack(code: str, file: str, timeout: int = 60):
    """POST /video-pack: the code goes in the body, never in the address."""
    body = json.dumps({"code": _norm(code), "file": file}).encode()
    req = urllib.request.Request(f"{SITE}/video-pack", data=body, method="POST",
                                 headers={**UA, "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        why = ""
        try:
            why = json.loads(e.read() or b"{}").get("error", "")
        except ValueError:
            pass
        raise RuntimeError({"bad": "That access code isn't right. Check it and try again.",
                            "off": "That access code has been switched off. Ask support@cadetfoundry.org for a new one.",
                            "missing": "The videos aren't on the website yet. Try again later.",
                            "closed": "Downloads are closed right now. Try again later."}.get(why, f"The website said no ({e.code}).")) from None
    except OSError as e:
        raise RuntimeError(f"Couldn't reach cadetfoundry.org — is this computer online? ({e})") from None


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _install_videos(code: str) -> int:
    _set(step="Checking your access code…", pct=1)
    with _pack(code, "manifest") as r:
        got = json.loads(r.read())
    data = str(got.get("manifest", "")).encode("utf-8")
    if not integrity.signature_ok(data, str(got.get("sig", "")), _KEY):
        raise RuntimeError("The video list isn't signed by Cadet Foundry, so nothing was downloaded.")
    manifest = json.loads(data)
    listed = {v["id"] for v in videos.catalog() if v.get("kind") == "dvids"}
    folder = videos.VIDEOS
    folder.mkdir(parents=True, exist_ok=True)
    # DVIDS's caching terms: a video DVIDS removed is deleted here too
    status = {k: v for k, v in (manifest.get("status") or {}).items() if k in listed and isinstance(v, dict)}
    for vid, st in status.items():
        if st.get("removed"):
            (folder / f"{vid}.mp4").unlink(missing_ok=True)
    videos.save_status({**videos.status(), **status})
    want = []
    for v in manifest.get("videos", []):
        if v.get("id") not in listed or (status.get(v["id"]) or {}).get("removed"):
            continue                                    # only videos this copy knows; never a name from outside
        f = folder / f"{v['id']}.mp4"
        if f.is_file() and f.stat().st_size == v["bytes"]:
            continue                                    # already saved
        want.append(v)
    if not want:
        return videos.listing()["saved"]
    need = sum(v["bytes"] for v in want)
    free = shutil.disk_usage(folder).free
    if free < need * 2 + 500 * 2**20:                  # the pieces and the finished video exist together for a moment
        raise RuntimeError(f"Not enough space: the videos need about {need * 2 / 2**30:.1f} GB free while they download, "
                           f"and this drive has {free / 2**30:.1f} GB.")
    parts = folder / ".download"
    parts.mkdir(exist_ok=True)
    done, i = 0, 0
    for v in want:
        i += 1
        for p in v["pieces"]:
            name = p["name"]
            if name != f"{v['id']}.mp4.{v['pieces'].index(p)}":
                raise RuntimeError("The video list has a bad entry, so nothing more was downloaded.")
            piece = parts / name
            if not (piece.is_file() and piece.stat().st_size == p["bytes"] and _sha(piece) == p["sha256"]):
                tmp = piece.with_suffix(piece.suffix + ".tmp")
                with _pack(code, name, timeout=120) as r, open(tmp, "wb") as out:
                    got_n = 0
                    while chunk := r.read(1 << 20):
                        out.write(chunk)
                        got_n += len(chunk)
                        _set(pct=2 + 96 * (done + got_n) // need,
                             step=f"Video {i} of {len(want)} ({(done + got_n) >> 20} of {need >> 20} MB)")
                if _sha(tmp) != p["sha256"]:
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError("A piece of a video didn't match its fingerprint, so it wasn't used. Try again.")
                tmp.replace(piece)
            done += p["bytes"]
            _set(pct=2 + 96 * done // need, step=f"Video {i} of {len(want)} ({done >> 20} of {need >> 20} MB)")
        whole = folder / f"{v['id']}.mp4.part"
        with open(whole, "wb") as out:
            for p in v["pieces"]:
                with open(parts / p["name"], "rb") as src:
                    shutil.copyfileobj(src, out, 1 << 20)
        if _sha(whole) != v["sha256"]:
            whole.unlink(missing_ok=True)
            raise RuntimeError("A video didn't match its fingerprint after joining, so it wasn't used. Try again.")
        whole.replace(folder / f"{v['id']}.mp4")
        for p in v["pieces"]:
            (parts / p["name"]).unlink(missing_ok=True)
    shutil.rmtree(parts, ignore_errors=True)
    return videos.listing()["saved"]


def _unpack(data: bytes, dest: Path) -> None:
    z = zipfile.ZipFile(io.BytesIO(data))
    top = z.namelist()[0].split("/")[0]
    dest.mkdir(parents=True, exist_ok=True)
    for name in z.namelist():
        if name.endswith("/"):
            continue
        out = (dest / Path(name).relative_to(top)).resolve()
        if not out.is_relative_to(dest.resolve()):     # never write outside the folder
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(z.read(name))
