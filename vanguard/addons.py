"""
Optional add-ons, installed from inside Cadet Foundry (Me tab) with a progress bar -- no console window, no setup script.

    Offline AI: Ollama (ollama.com) + the qwen2.5 3B model (about 2 GB). On Windows the official installer is
                downloaded, its Authenticode signature checked (must be valid and signed by Ollama), then run
                silently. Then the model is pulled through Ollama's own API.
    Voice:      the Vosk speech recognizer (pip) + its small English model (about 40 MB, alphacephei.com).

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
import urllib.request
import zipfile
from pathlib import Path

from vanguard import engine, voice

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

def install(name: str) -> dict:
    if name not in ("ai", "voice"):
        raise ValueError("Unknown add-on.")
    with _lock:
        if _job.get("state") == "running":
            raise ValueError("Another add-on is installing — wait for it to finish.")
        _job.clear()
        _job.update({"name": name, "state": "running", "step": "Starting…", "pct": 0, "msg": ""})
    threading.Thread(target=_run, args=(name,), daemon=True).start()
    return dict(_job)


def _set(**kw) -> None:
    with _lock:
        _job.update(kw)


def _run(name: str) -> None:
    try:
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
    ps = ("$s = Get-AuthenticodeSignature -LiteralPath $env:VANGUARD_CHECK; "
          "Write-Output $s.Status; Write-Output $s.SignerCertificate.Subject")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, timeout=60, creationflags=HIDDEN, env={**os.environ, "VANGUARD_CHECK": str(exe)})
    except (OSError, subprocess.SubprocessError):
        return False
    lines = r.stdout.splitlines()
    return len(lines) >= 2 and lines[0].strip() == "Valid" and "ollama" in lines[1].lower()


def _install_ai() -> None:
    if not ollama_exe() and _tags() is None:
        if not WINDOWS:
            raise RuntimeError("Install Ollama from ollama.com (or run install-vanguard.sh), then try again.")
        tmp = Path(tempfile.mkdtemp(prefix="vanguard-"))
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
            tmp = Path(tempfile.mkdtemp(prefix="vanguard-"))
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
        tmp = Path(tempfile.mkdtemp(prefix="vanguard-"))
        try:
            z = tmp / "model.zip"
            _download(VOICE_MODEL[0], z, "Downloading the English voice model", 30, 90, sha256=VOICE_MODEL[1])
            _set(step="Unpacking the voice model", pct=92)
            _unpack(z.read_bytes(), dest)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


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
