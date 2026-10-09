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
    START HERE.html                    which file does what (opens in any browser)
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

START_HERE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vanguard — start here</title>
<style>
body { margin: 0; background: #f6f4ee; color: #1b1a17; font: 17px/1.6 system-ui, "Segoe UI", sans-serif; }
.w { max-width: 860px; margin: 0 auto; padding: 28px 18px 60px; }
h1 { margin: 0; font-size: 32px; } h2 { margin: 30px 0 10px; font-size: 22px; border-bottom: 2px solid #cdb57c; padding-bottom: 4px; }
.sub { color: #555; margin: 4px 0 22px; }
.box { background: #fff; border: 1px solid #ddd5c0; border-radius: 12px; padding: 16px 18px; margin: 12px 0; }
.box h3 { margin: 0 0 6px; font-size: 19px; } .file { font-family: Consolas, monospace; background: #efe8d6; padding: 2px 7px; border-radius: 6px; }
table { border-collapse: collapse; width: 100%; font-size: 15px; } th, td { border: 1px solid #ddd5c0; padding: 8px; text-align: left; vertical-align: top; }
th { background: #efe8d6; } .tip { color: #444; font-size: 15px; } code { font-family: Consolas, monospace; background: #efe8d6; padding: 1px 6px; border-radius: 5px; }
</style></head><body><div class="w">
<h1>✦ Vanguard — start here</h1>
<p class="sub">Leadership. Learning. Character. Version {version}. Everything on this drive works with no internet.</p>

<h2>Which one do I open?</h2>

<div class="box"><h3>▶ <span class="file">Start Vanguard.bat</span> — just this computer</h3>
Vanguard runs from this drive and opens in this computer's browser. <b>Only this computer can use it.</b><br>
Use it to look around, prepare lessons, check records, or for one person studying.</div>

<div class="box"><h3>▶ <span class="file">Start Vanguard (classroom).bat</span> — the whole class</h3>
This computer becomes the classroom's Vanguard. <b>Cadets use it from their own phones, tablets or laptops</b> on the
same Wi-Fi: the black window shows the address to type (for example <code>http://10.0.0.65:8780</code>).<br>
Every profile needs a PIN in classroom mode. If Windows asks whether to allow Python on networks, choose
<b>Allow</b> (private networks). If Cadets can't connect, the school Wi-Fi may block devices from reaching each other —
ask IT, or use a phone hotspot or the Vanguard demo box.</div>

<div class="box"><h3>▶ <span class="file">start-vanguard-usb.sh</span> — Linux or Mac</h3>
The same as <i>Start Vanguard</i>, for a Linux computer or a Mac. Open a terminal in this drive and run
<code>sh start-vanguard-usb.sh</code> — or <code>sh start-vanguard-usb.sh --lan</code> for the whole class.
That computer needs Python 3 with the <code>cryptography</code> package.</div>

<div class="box"><h3>⬇ <span class="file">Install Vanguard … on this computer.exe</span> — keep it on a computer</h3>
Installs Vanguard on this Windows computer (a Vanguard icon on the desktop and in the Start menu). After that the drive
isn't needed. If Windows says <i>"Windows protected your PC"</i>, choose <b>More info → Run anyway</b>.</div>

<table>
<tr><th></th><th>Start Vanguard</th><th>Start Vanguard (classroom)</th><th>Install …exe</th></tr>
<tr><td>Who can use it</td><td>This computer only</td><td>This computer + Cadets' devices on the same Wi-Fi</td><td>That computer (classroom mode from its menu)</td></tr>
<tr><td>Where the data lives</td><td colspan="2">On this drive (<span class="file">VanguardData</span>)</td><td>On that computer</td></tr>
<tr><td>Installs anything?</td><td colspan="2">No — runs from the drive</td><td>Yes</td></tr>
<tr><td>Best for</td><td>Preparing, one person</td><td>Teaching a class</td><td>A computer used every day</td></tr>
</table>

<h2>The first time</h2>
<ol>
<li>Open <span class="file">Start Vanguard.bat</span> (or the classroom one).</li>
<li>Instructor: tap <b>+ New profile</b>, choose <b>An instructor</b>, choose the <b>Instructor PIN</b> (it opens class records — don't share it) and your own PIN.</li>
<li>Open <b>🎓 Instructor</b> to add classes and Cadets' units. Cadets create their own profiles with their own PIN.</li>
<li>Write down each <b>recovery code</b> Vanguard shows — it's the way back if a PIN is forgotten.</li>
</ol>

<h2>While it runs and when you're done</h2>
<ul>
<li>A black window stays open while Vanguard runs — <b>leave it open</b>.</li>
<li>To stop: <b>Me → Quit Vanguard</b>, or close the black window. Wait a moment, then unplug the drive.</li>
<li>The offline AI (if this drive has it) starts and stops with Vanguard. Its first answer can take a minute.</li>
</ul>

<h2>Your data</h2>
<ul>
<li>Everything — profiles, class records, lessons, settings — is in <span class="file">VanguardData</span>. Each profile is encrypted with its own PIN, and class records also need the Instructor PIN, so a lost drive doesn't expose anyone's data.</li>
<li><b>Back it up:</b> copy the <span class="file">VanguardData</span> folder somewhere safe now and then.</li>
<li><b>Move everyone to an installed computer:</b> with Vanguard closed on both, copy <span class="file">VanguardData</span> into
<code>C:\\Users\\&lt;name&gt;\\.vanguard</code> on that computer (before anyone makes profiles there — it replaces them).</li>
<li><b>Move one person:</b> Me → <i>Download encrypted backup</i>, then restore it on the other computer.</li>
</ul>

<h2>Other things on this drive</h2>
<ul>
<li><span class="file">Vanguard</span> — the app itself. Don't change it.</li>
<li><span class="file">demo</span> (if present) — the printable demo card and the Raspberry Pi demo-box guide (<span class="file">README-PI.txt</span>).</li>
</ul>
<p class="tip">Vanguard is designed to support JROTC instruction. It is not an official JROTC, Army or school product, does not
replace your instructor or your program's curriculum, and makes no claim of endorsement. Built by Winklers LLC.</p>
</div></body></html>
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

    # The installer and zip ride along: on the drive's root for whoever holds it, and in Vanguard\downloads so a
    # Vanguard started from this drive (or a demo Pi set up from it) offers them on /download -- no internet needed.
    version = build.__version__
    setup, zipf = build.DIST / f"Vanguard-Setup-{version}.exe", build.DIST / f"Vanguard-{version}.zip"
    downloads = app / "downloads"
    shutil.rmtree(downloads, ignore_errors=True)
    for old in drive.glob("Install Vanguard*.exe"):
        old.unlink()
    if setup.exists() and zipf.exists():
        downloads.mkdir()
        for f in (setup, zipf):
            shutil.copy2(f, downloads / f.name)
        shutil.copy2(setup, drive / f"Install Vanguard {version} on this computer.exe")
    else:
        print(f"Note: no installer for {version} in site/dist — run  python site/build.py  first to put it on the drive.")
    (drive / "VanguardData").mkdir(exist_ok=True)
    for name, args_ in (("Start Vanguard.bat", ""), ("Start Vanguard (classroom).bat", "--lan")):
        (drive / name).write_bytes(START_BAT.replace("{args}", args_).replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    (drive / "start-vanguard-usb.sh").write_bytes(START_SH.encode("ascii"))
    (drive / "README-USB.txt").unlink(missing_ok=True)          # replaced by START HERE.html
    (drive / "START HERE.html").write_text(START_HERE.replace("{version}", build.__version__), encoding="utf-8")

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
