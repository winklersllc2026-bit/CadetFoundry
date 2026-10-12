"""
Put the whole Cadet Foundry system on a USB drive: plug it into any Windows computer, double-click, and it runs —
nothing is installed on that computer, and every profile and class record stays on the drive.

    python tools/make_usb.py E:\\                 app + its own Python + the library
    python tools/make_usb.py E:\\ --for "SFC Rivera, Lincoln High"   who the drive is issued to (in its signed record)
    python tools/make_usb.py E:\\ --restore "class-....zip"          a replacement drive: the class from a USB backup
    python tools/make_usb.py E:\\ --with-ai       also the offline AI (Ollama + one model, copied from this computer)
    python tools/make_usb.py E:\\ --with-ai --model qwen2.5:3b
    python tools/make_usb.py E:\\ --with-ai --all-gpu      also NVIDIA/AMD graphics libraries (about 2.7 GB more)

Sizes: the app about 50 MB; with the AI about 0.1 GB for the engine plus the model (qwen2.5:1.5b 0.9 GB, 3b 1.9 GB).

Run it again to update the drive: the app is replaced, the data (Cadet Foundry Data) is never touched.

On the drive:
    Start Cadet Foundry.bat            starts it (Cadet phones can be turned on from the Home screen)
    start-cadet-foundry-usb.sh         Linux / Mac (uses that computer's python3)
    START HERE.html                    which file does what (opens in any browser)
    NOTICE - READ FIRST.txt            the copyright notice (issued.py: a copied drive shows it in the app)
    Cadet Foundry\\                     the app, with python\\ (and ollama\\ with --with-ai)
    Cadet Foundry Data\\                      profiles and class records (each profile encrypted with its own PIN)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))
import build  # noqa: E402  (site/build.py: the same file list and bundled Python as the installer)
sys.path.insert(0, str(ROOT))
from cadetfoundry import integrity  # noqa: E402

APP_ITEMS = ["cadetfoundry", "web", "tools", "library", "books", "faith", "python", "run.py", "README.md", "LIBRARY.md",
             "SECURITY.md", "install-cadetfoundry.bat", "install-cadetfoundry.sh", "start-cadetfoundry.bat", "start-cadetfoundry.sh"]
OLD_APP_ITEMS = ["vanguard", "install-vanguard.bat", "install-vanguard.sh", "start-vanguard.bat", "start-vanguard.sh",
                 "start-classroom.bat", "start-classroom.sh"]                # the classroom is opened from the app now

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

START_SH = """#!/bin/sh
# Cadet Foundry from this USB drive on Linux or a Mac (uses this computer's python3 and its cryptography package).
here="$(cd "$(dirname "$0")/.." && pwd)"     # this file is in "Mac and Linux"; the drive is one level up
export CADETFOUNDRY_DATA="$here/Cadet Foundry Data"
cd "$here/Cadet Foundry" || exit 1
if ! python3 -c "import sys, cryptography; sys.exit(int(cryptography.__version__.split('.')[0]) < 50)" 2>/dev/null; then
  echo "Cadet Foundry needs Python 3.10+ with the 'cryptography' package, version 50 or newer:"
  echo "  python3 -m pip install --user --upgrade 'cryptography>=50'"
  exit 1
fi
exec python3 run.py "$@"
"""

START_HERE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cadet Foundry — start here</title>
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
<h1>✦ Cadet Foundry — start here</h1>
<p class="sub">Leadership. Learning. Character. Version {version}. Everything on this drive works with no internet.</p>

<h2>Which one do I open?</h2>

<div class="box"><h3>▶ <span class="file">Start Cadet Foundry.bat</span> — start here</h3>
Cadet Foundry runs from this drive and opens in this computer's browser. At first <b>only this computer can use it</b> —
good for looking around, preparing lessons, checking records, or one person studying.<br>
<b>Teaching a class?</b> On your Home screen press <b>📱 Open class to phones</b>, or press <b>▶ Start class</b> — its first
step opens class to phones and shows the <b>QR code</b> to put on the projector. Cadets scan it with their phones, tablets or
laptops on the same Wi-Fi and pick a name and a PIN.<br>
If Windows asks whether to allow Python on networks, choose <b>Allow</b> (private networks). If Cadets can't connect, the
school Wi-Fi may block devices from reaching each other — ask IT, or use a phone hotspot or a small travel router.</div>

<div class="box"><h3>💾 Drives for your Cadets</h3>
In Cadet Foundry: <b>👤 Me → Create a Cadet flash drive</b>. Each Cadet's drive works at home on any Windows computer, and
their class work comes back to you when you plug it in. Please don't copy this drive — see <span class="file">NOTICE - READ FIRST.txt</span>.</div>

<div class="box"><h3>🏠 One home for your class</h3>
This drive <b>is</b> your class: profiles, records and lessons are saved on it. Start Cadet Foundry from this drive
everywhere — at school and at home — and don't also install it on a computer, because the two wouldn't stay in step.
On your own computer, say yes when Cadet Foundry asks to keep a backup there: the newest five copies of your class are
kept, so losing the drive doesn't mean losing your class.</div>

<div class="box"><h3>📁 <span class="file">Mac and Linux</span> — not Windows</h3>
For a Mac or Linux computer: open a terminal in that folder and run <code>sh start-cadet-foundry-usb.sh</code>,
then open class to phones from your Home screen as usual. That computer needs Python 3 with the
<code>cryptography</code> package. Windows computers don't need this folder.</div>


<h2>The first time</h2>
<ol>
<li>Open <span class="file">Start Cadet Foundry.bat</span>.</li>
<li>Instructor: choose <b>I'm the instructor — set up this class</b>. Pick a <b>Class PIN</b> (it opens your class — don't share it with Cadets), then your name and your own PIN.</li>
<li>Your <b>Home</b> screen walks you through the rest: make your class, then press <b>▶ Start class</b>, tick today's lesson, study cards, scenarios, questions and videos, and press <b>🖥️ Present today's class</b> to click through it on the projector. No internet needed. Cadet phones are optional (<b>Turn phones on</b>).</li>
<li>Write down each <b>backup code</b> Cadet Foundry shows — it's the way back if a PIN is forgotten.</li>
</ol>

<h2>While it runs and when you're done</h2>
<ul>
<li>A black window stays open while Cadet Foundry runs — <b>leave it open</b>.</li>
<li>To stop: <b>Close to phones</b> on your Home screen when class ends, then <b>Me → Quit Cadet Foundry</b> or close the black window. Wait a moment, then unplug the drive.</li>
<li>The offline AI (if this drive has it) starts and stops with Cadet Foundry. Its first answer can take a minute.</li>
</ul>

<h2>Your data</h2>
<ul>
<li>Everything — profiles, class records, lessons, settings — is in <span class="file">Cadet Foundry Data</span>. Each profile is encrypted with its own PIN, and class records also need the Class PIN, so a lost drive doesn't expose anyone's data.</li>
<li><b>Back it up:</b> copy the <span class="file">Cadet Foundry Data</span> folder somewhere safe now and then.</li>
<li><b>Move everyone to an installed computer:</b> with Cadet Foundry closed on both, copy <span class="file">Cadet Foundry Data</span> into
<code>C:\\Users\\&lt;name&gt;\\.cadetfoundry</code> on that computer (before anyone makes profiles there — it replaces them).</li>
<li><b>Move one person:</b> Me → <i>Download encrypted backup</i>, then restore it on the other computer.</li>
</ul>

<h2>Other things on this drive</h2>
<ul>
<li><span class="file">Cadet Foundry</span> — the app itself. Don't change it.</li>
<li><span class="file">demo</span> (if present) — the printable demo card and the Raspberry Pi demo-box guide (<span class="file">README-PI.txt</span>).</li>
</ul>
<p class="tip"><b>© 2026 the Cadet Foundry project. All rights reserved.</b> This drive was issued for one JROTC program's use
during the pilot. Please don't copy it or share it — copying or sharing it without permission is against the Terms of use
and copyright law. Instructors who want their own copy: support@cadetfoundry.org.</p>
<p class="tip">Cadet Foundry is designed to support JROTC instruction. It is not an official JROTC, Army or school product, does not
replace your instructor or your program's curriculum, and makes no claim of endorsement. A free community project — the Cadet Foundry project.</p>
</div></body></html>
"""


def _retry(fn, *args, tries: int = 15, wait: float = 2.0, **kw):
    """Windows antivirus briefly locks a freshly written .exe while it scans it ("being used by another process").
    Wait and try again instead of failing; say what's going on after a few tries."""
    import time
    for n in range(tries):
        try:
            return fn(*args, **kw)
        except PermissionError:
            if n == tries - 1:
                raise PermissionError(f"{args[-1] if args else ''} is still in use. Close anything that has the USB drive "
                                      "open (Cadet Foundry, File Explorer previews) and run this again.") from None
            if n == 2:
                print("  waiting for Windows to finish checking a file (antivirus scan) …")
            time.sleep(wait)


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
            _retry(shutil.copy2, blob, target)
        total += blob.stat().st_size
    return total


def main(argv: list[str]) -> int:
    values = {argv[i + 1] for i, a in enumerate(argv[:-1]) if a in ("--model", "--for", "--restore")}
    args = [a for a in argv if not a.startswith("--") and a not in values]
    if not args:
        print(__doc__)
        return 1
    drive = Path(args[0])
    if not drive.exists():
        print(f"{drive} doesn't exist. Plug in the USB drive and give its letter, e.g. E:\\")
        return 1
    model = argv[argv.index("--model") + 1] if "--model" in argv else "qwen2.5:3b"
    issued_to = argv[argv.index("--for") + 1] if "--for" in argv else ""
    restore_from = Path(argv[argv.index("--restore") + 1]) if "--restore" in argv else None
    if restore_from and not restore_from.is_file():
        print(f"{restore_from} isn't there. Give the path of a class backup (class-....zip). Nothing was changed.")
        return 1
    app = drive / "Cadet Foundry"
    # A drive made before the rename (0.2.5): its folders move to the new names -- data, offline AI and videos kept
    for old, new in (("Vanguard", "Cadet Foundry"), ("VanguardData", "Cadet Foundry Data")):
        if (drive / old).is_dir() and not (drive / new).exists():
            _retry((drive / old).rename, drive / new)
            print(f"Renamed {old} -> {new}")
    for leftover in drive.glob("*-sample"):               # a sample class's throwaway folder (rebuilt each time anyway)
        if (leftover / "SAMPLE_DATA.txt").exists():
            _retry(shutil.rmtree, leftover)

    # The manuals aren't in git (library/ is ignored), so a fresh copy of the code can be missing them. A drive built
    # from it said "Missing: ...pdf" in the app (found 2026-10-11). Stop here instead.
    lib = integrity.check_library()
    if lib.get("missing"):
        print(f"This computer's library is missing {len(lib['missing'])} file(s): {', '.join(lib['missing'][:5])}"
              f"{' …' if len(lib['missing']) > 5 else ''}\nCopy them into {integrity.LIBRARY} (or run tools/fetch_library.py),"
              " then make the drive again. Nothing was changed on the drive.")
        return 1

    print("Building the app …")
    with tempfile.TemporaryDirectory() as tmp:
        z = Path(tmp) / "cadetfoundry.zip"
        build.make_zip(z)
        stage = Path(tmp) / "stage"
        with zipfile.ZipFile(z) as zf:
            zf.extractall(stage)
        shutil.rmtree(stage / "CadetFoundry" / "tests", ignore_errors=True)
        if not build.bundle_python(stage / "CadetFoundry"):
            print("Couldn't add Python — nothing was changed on the drive.")
            return 1
        print(f"Copying to {app} …")
        app.mkdir(parents=True, exist_ok=True)
        for old in OLD_APP_ITEMS:                        # left in a drive's app folder from before the rename
            target = app / old
            if target.is_dir():
                _retry(shutil.rmtree, target)
            elif target.exists():
                _retry(target.unlink)
        for item in APP_ITEMS:                           # replace the app; never Cadet Foundry Data or ollama\
            target = app / item
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
            src = stage / "CadetFoundry" / item
            if src.is_dir():
                _retry(shutil.copytree, src, target, dirs_exist_ok=True)
            elif src.exists():
                _retry(shutil.copy2, src, target)
        # Official videos saved with tools/fetch_videos.py play from the drive offline. Copy only what's missing:
        # they're large and never change once saved.
        vids = ROOT / "videos"
        if vids.is_dir():
            (app / "videos").mkdir(exist_ok=True)
            for f in sorted(vids.glob("dvids-*.mp4")):
                if not (app / "videos" / f.name).exists():
                    _retry(shutil.copy2, f, app / "videos" / f.name)
            # DVIDS API terms (Caching): a video removed from DVIDS (fetch_videos.py deletes it here) goes from the
            # drive too
            for f in (app / "videos").glob("dvids-*.mp4"):
                if not (vids / f.name).exists():
                    f.unlink()
            if (vids / "status.json").exists():
                _retry(shutil.copy2, vids / "status.json", app / "videos" / "status.json")

    # No installer on a drive (owner, 2026-10-12): a drive is run from the drive, never installed from -- one home for
    # the class -- and the installer is only given out with an access code. Older drives lose theirs.
    shutil.rmtree(app / "downloads", ignore_errors=True)
    for old in [*drive.glob("Install Vanguard*.exe"), *drive.glob("Install Cadet Foundry*.exe")]:
        _retry(old.unlink)
    shutil.rmtree(drive / "Make more flash drives", ignore_errors=True)   # the old copier: Cadet drives come from the app
    (drive / "Cadet Foundry Data").mkdir(exist_ok=True)
    if restore_from:                              # a replacement drive: the class from a USB backup (usb_home.py)
        from cadetfoundry import usb_home
        try:
            print(f"Restored {usb_home.restore(restore_from, drive / 'Cadet Foundry Data')} files of your class.")
        except ValueError as e:
            print(str(e))
            return 1
    (drive / "NOTICE - READ FIRST.txt").write_bytes(
        (ROOT / "cadetfoundry" / "legal" / "NOTICE.txt").read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
    # Issued by the project: the drive's serial number and who it's for, signed with the owner's release key (issued.py).
    # A copy of this drive on another flash drive shows the copyright notice in the app.
    from cadetfoundry import issued
    key_path = Path.home() / ".vanguard-release" / "release_key.pem"
    serial = issued.volume_serial(drive)
    if key_path.exists() and serial:
        sys.path.insert(0, str(ROOT / "tools"))
        import sign
        issued.write(app, serial, issued_to, time.strftime("%Y-%m-%d"), sign.load_key(key_path))
        who = issued_to or '(no name given: add --for "Name, School")'
        print(f"Issued to: {who} · drive {serial}")
    else:
        print("Note: the drive isn't marked as issued (no release key on this computer, or no drive serial), so the app "
              "on it will show the copyright notice.")
    for old in ("Start Vanguard (classroom).bat", "Start Vanguard.bat"):    # older names (0.1; before the rename)
        (drive / old).unlink(missing_ok=True)
    (drive / "Start Classroom.bat").unlink(missing_ok=True)             # the classroom opens from the app now (0.2.6)
    for name, args_ in (("Start Cadet Foundry.bat", ""),):
        (drive / name).write_bytes(START_BAT.replace("{args}", args_).replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii"))
    (drive / "start-vanguard-usb.sh").unlink(missing_ok=True)          # moved into "Mac and Linux" (0.2.2)
    (drive / "Mac and Linux").mkdir(exist_ok=True)
    (drive / "Mac and Linux" / "start-vanguard-usb.sh").unlink(missing_ok=True)   # the name before the rename
    (drive / "Mac and Linux" / "start-cadet-foundry-usb.sh").write_bytes(START_SH.encode("ascii"))
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
            _retry(shutil.copytree, src, dest, ignore=skip, dirs_exist_ok=True)
            if (app / "_models_keep").exists():
                (app / "_models_keep").rename(dest / "models")
            try:
                size = copy_model(model, dest / "models")
                print(f"  {model}: {size / 2**30:.1f} GB")
            except FileNotFoundError as e:
                print("  " + str(e))

    used = sum(f.stat().st_size for f in app.rglob("*") if f.is_file())
    print(f"\nDone. {app} uses {used / 2**30:.2f} GB. Plug the drive into a Windows computer and double-click "
          "\"Start Cadet Foundry.bat\".")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
