"""
Put the whole Vanguard system on a USB drive: plug it into any Windows computer, double-click, and it runs —
nothing is installed on that computer, and every profile and class record stays on the drive.

    python tools/make_usb.py E:\\                 app + its own Python + the library
    python tools/make_usb.py E:\\ --with-ai       also the offline AI (Ollama + one model, copied from this computer)
    python tools/make_usb.py E:\\ --with-ai --model qwen2.5:3b
    python tools/make_usb.py E:\\ --with-ai --all-gpu      also NVIDIA/AMD graphics libraries (about 2.7 GB more)

Sizes: the app about 50 MB; with the AI about 0.1 GB for the engine plus the model (qwen2.5:1.5b 0.9 GB, 3b 1.9 GB).

Run it again to update the drive: the app is replaced, the data (VanguardData) is never touched.

On the drive:
    Start Vanguard.bat                 this computer only
    Start Vanguard (classroom).bat     Cadets on the classroom network can connect too
    start-vanguard-usb.sh              Linux / Mac (uses that computer's python3)
    README-USB.txt
    Vanguard\\                          the app, with python\\ (and ollama\\ with --with-ai)
    VanguardData\\                      profiles and class records (each profile encrypted with its own PIN)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))
import build  # noqa: E402  (site/build.py: the same file list and bundled Python as the installer)

APP_ITEMS = ["vanguard", "web", "tools", "library", "books", "faith", "python", "run.py", "README.md", "LIBRARY.md",
             "SECURITY.md", "install-vanguard.bat", "install-vanguard.sh", "start-vanguard.bat", "start-vanguard.sh"]

START_BAT = r"""@echo off
title Vanguard
rem Vanguard from this USB drive. Nothing is installed on this computer; all data stays on the drive.
cd /d "%~dp0Vanguard"
set "VANGUARD_DATA=%~dp0VanguardData"
if exist "%~dp0Vanguard\ollama\ollama.exe" set "VANGUARD_OLLAMA=%~dp0Vanguard\ollama\ollama.exe"
echo.
echo   VANGUARD - running from this USB drive
echo   Keep this window open while you use Vanguard.
echo   To stop: Me ^> Quit Vanguard, or close this window. Then unplug the drive.
echo.
"%~dp0Vanguard\python\python.exe" run.py {args} %*
if errorlevel 1 pause
"""

START_SH = """#!/bin/sh
# Vanguard from this USB drive on Linux or a Mac (uses this computer's python3 and its cryptography package).
here="$(cd "$(dirname "$0")" && pwd)"
export VANGUARD_DATA="$here/VanguardData"
cd "$here/Vanguard" || exit 1
if ! python3 -c "import cryptography" 2>/dev/null; then
  echo "Vanguard needs Python 3.10+ with the 'cryptography' package: python3 -m pip install --user cryptography"
  exit 1
fi
exec python3 run.py "$@"
"""

README = """VANGUARD ON A USB DRIVE
=======================

Windows
  1. Plug in the drive and open it.
  2. Double-click "Start Vanguard.bat" (this computer only)
     or "Start Vanguard (classroom).bat" (Cadets on the classroom network can connect; the window shows the address).
  3. Keep the black window open while you use Vanguard.
  4. To stop: Me > Quit Vanguard, or close the window. Wait a moment, then unplug the drive.

  If Windows warns about the file, choose "More info" > "Run anyway". Nothing is installed on the computer.

Linux / Mac
  sh start-vanguard-usb.sh            (or: sh start-vanguard-usb.sh --lan for the classroom)

Your data
  Everything - profiles, class records, lessons, settings - is in the VanguardData folder on this drive.
  Each profile's files are encrypted with that person's PIN, and class records also need the Instructor PIN,
  so a lost drive doesn't expose anyone's data. Still: keep the drive somewhere safe, and make a backup copy of the
  VanguardData folder (or use Me > Download encrypted backup) now and then.

Speed
  A USB 3 drive in a USB 3 port is much faster. The offline AI (if this drive has it) loads its model from the
  drive the first time it answers, which can take a minute.

Updating
  Run tools/make_usb.py again from the computer that builds Vanguard - the app is replaced and VanguardData is kept -
  or use Me > Install an update with a signed update file.
"""


def ollama_install() -> Path | None:
    for p in (Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama",
              Path(os.environ.get("ProgramFiles", "")) / "Ollama"):
        if (p / "ollama.exe").exists():
            return p
    return None


def copy_model(name: str, dest_models: Path) -> int:
    """Copy one Ollama model (its manifest and the blobs it names) from this computer's model folder."""
    src = Path(os.environ.get("OLLAMA_MODELS") or Path.home() / ".ollama" / "models")
    repo, _, tag = name.partition(":")
    manifest = src / "manifests" / "registry.ollama.ai" / "library" / repo / (tag or "latest")
    if not manifest.exists():
        raise FileNotFoundError(f"The model {name} isn't on this computer (ollama pull {name} first).")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    digests = [data["config"]["digest"]] + [layer["digest"] for layer in data.get("layers", [])]
    out = dest_models / manifest.relative_to(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, out)
    total = 0
    for d in digests:
        blob = src / "blobs" / d.replace(":", "-")
        target = dest_models / "blobs" / blob.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != blob.stat().st_size:
            print(f"  copying {blob.name[:19]}… ({blob.stat().st_size / 2**30:.2f} GB)")
            shutil.copy2(blob, target)
        total += blob.stat().st_size
    return total


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    drive = Path(args[0])
    if not drive.exists():
        print(f"{drive} doesn't exist. Plug in the USB drive and give its letter, e.g. E:\\")
        return 1
    model = argv[argv.index("--model") + 1] if "--model" in argv else "qwen2.5:3b"
    app = drive / "Vanguard"

    print("Building the app …")
    with tempfile.TemporaryDirectory() as tmp:
        z = Path(tmp) / "vanguard.zip"
        build.make_zip(z)
        stage = Path(tmp) / "stage"
        with zipfile.ZipFile(z) as zf:
            zf.extractall(stage)
        shutil.rmtree(stage / "Vanguard" / "tests", ignore_errors=True)
        if not build.bundle_python(stage / "Vanguard"):
            print("Couldn't add Python — nothing was changed on the drive.")
            return 1
        print(f"Copying to {app} …")
        app.mkdir(parents=True, exist_ok=True)
        for item in APP_ITEMS:                           # replace the app; never VanguardData or ollama\
            target = app / item
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            src = stage / "Vanguard" / item
            if src.is_dir():
                shutil.copytree(src, target)
            elif src.exists():
                shutil.copy2(src, target)

    (drive / "VanguardData").mkdir(exist_ok=True)
    for name, args_ in (("Start Vanguard.bat", ""), ("Start Vanguard (classroom).bat", "--lan")):
        (drive / name).write_bytes(START_BAT.replace("{args}", args_).replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    (drive / "start-vanguard-usb.sh").write_bytes(START_SH.encode("ascii"))
    (drive / "README-USB.txt").write_bytes(README.replace("\n", "\r\n").encode("utf-8"))

    if "--with-ai" in argv:
        src = ollama_install()
        if not src:
            print("Offline AI not added: Ollama isn't installed on this computer (ollama.com), so there's nothing to copy.")
        else:
            print(f"Copying Ollama and {model} …")
            dest = app / "ollama"
            # Only the engine: not the tray app, uninstaller or logs. NVIDIA/AMD libraries (about 2.7 GB) only with
            # --all-gpu -- school laptops rarely have those cards; the processor and Vulkan libraries run everywhere.
            skip_gpu = "--all-gpu" not in argv
            def skip(_dir, names):
                return [n for n in names if n.lower().startswith(("unins", "ollama app")) or n.lower().endswith((".log", ".tmp"))
                        or (skip_gpu and n.lower().startswith(("cuda_", "rocm")))]
            if dest.exists():
                for keep in ("models",):                  # an earlier model copy stays; the program is replaced
                    if (dest / keep).exists():
                        (dest / keep).rename(app / f"_{keep}_keep")
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=skip)
            if (app / "_models_keep").exists():
                (app / "_models_keep").rename(dest / "models")
            try:
                size = copy_model(model, dest / "models")
                print(f"  {model}: {size / 2**30:.1f} GB")
            except FileNotFoundError as e:
                print("  " + str(e))

    used = sum(f.stat().st_size for f in app.rglob("*") if f.is_file())
    print(f"\nDone. {app} uses {used / 2**30:.2f} GB. Plug the drive into a Windows computer and double-click "
          "\"Start Vanguard.bat\".")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
