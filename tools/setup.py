"""
One-time setup for a Cadet Foundry device (needs internet once; afterwards everything runs offline).

    python tools/setup.py            asks a few yes/no questions (Enter = the suggested answer)
    python tools/setup.py --yes      everything, no questions
    python tools/setup.py --yes --no-ai --no-voice

Steps: faith texts -> official library -> offline voice -> offline AI (Ollama + a small model)
-> desktop shortcut -> self-check. Each step can fail without stopping the others; a summary
at the end says what worked. install-cadetfoundry.bat (Windows) and install-cadetfoundry.sh (Linux) run this.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINDOWS = platform.system() == "Windows"
OLLAMA_URL = "http://127.0.0.1:11434"
# Small models only: these devices run the AI on the processor. 3B is the default: in testing (Oct 2026) the 1.5B
# model mixed up facts and looped, 3B stayed with the source. 1.5B is for very old or slow devices (--model=1.5b);
# it answers about twice as fast.
MODELS = {"small": "qwen2.5:1.5b", "medium": "qwen2.5:3b"}


def ask(question: str, default: bool, assume: bool) -> bool:
    if assume:
        return default
    try:
        a = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    except EOFError:
        return default
    return default if not a else a.startswith("y")


def run(cmd: list[str], **kw) -> bool:
    print("  $", " ".join(cmd))
    try:
        return subprocess.run(cmd, cwd=ROOT, **kw).returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        print("   ", e)
        return False


def py(*args: str) -> bool:
    return run([sys.executable, *args])


def pip(*pkgs: str) -> bool:
    return py("-m", "pip", "install", "--quiet", "--disable-pip-version-check", *pkgs)


# ── steps ───────────────────────────────────────────────────────────────────

def faith() -> bool:
    return py("tools/fetch_faith.py")


def library() -> bool:
    pip("pypdf")                                   # converts the official PDFs to text, on this machine only
    return py("tools/fetch_library.py")


def books() -> bool:
    return py("tools/fetch_books.py")


def voice() -> bool:
    return py("tools/install_voice.py")


def ollama_running() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3):
            return True
    except Exception:
        return False


def ollama_exe() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    if WINDOWS:                                    # winget installs here; PATH updates only in new windows
        p = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        return str(p) if p.exists() else None
    return None


def ai(model: str) -> bool:
    exe = ollama_exe()
    if not exe:
        if WINDOWS and shutil.which("winget"):
            run(["winget", "install", "-e", "--id", "Ollama.Ollama", "--accept-package-agreements",
                 "--accept-source-agreements"])
        elif not WINDOWS and shutil.which("curl"):
            print("  Installing Ollama with its official script (ollama.com) …")
            run(["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"])
        exe = ollama_exe()
    if not exe:
        print("  Ollama isn't installed. Get it from https://ollama.com/download, then run this again.")
        return False
    if not ollama_running():
        subprocess.Popen([exe, "serve"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            if ollama_running():
                break
            time.sleep(1)
    return run([exe, "pull", model])


def shortcut() -> bool:
    if WINDOWS:
        # The real Desktop folder (it may be moved into OneDrive), the app's icon, and a minimized server window.
        target, icon = ROOT / "start-cadetfoundry.bat", ROOT / "web" / "icon.ico"
        ps = ("$d=[Environment]::GetFolderPath('Desktop');"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Cadet Foundry.lnk'));"
              f"$s.TargetPath='{target}';$s.WorkingDirectory='{ROOT}';$s.IconLocation='{icon},0';"
              "$s.WindowStyle=7;$s.Description='Cadet Foundry';$s.Save()")
        return run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])
    apps = Path.home() / ".local" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    entry = apps / "cadetfoundry.desktop"
    entry.write_text("[Desktop Entry]\nType=Application\nName=Cadet Foundry\nComment=Offline study companion\n"
                     f"Exec=sh \"{ROOT / 'start-cadetfoundry.sh'}\"\nPath={ROOT}\nIcon={ROOT / 'web' / 'icon.svg'}\nTerminal=false\n", encoding="utf-8")
    print(f"  Added {entry} (shows in the app menu)")
    return True


def self_check() -> bool:
    code = ("import sys; sys.path.insert(0, '.'); from cadetfoundry.knowledge import Library; "
            "s = Library().stats(); print(f\"  {s['cards']} study cards, {len(s['documents'])} library documents, "
            "{s['passages']} passages\")")
    return py("-c", code)


# Every release before 50.0.0 has published advisories (OSV); an older copy already on the computer gets upgraded.
CRYPTOGRAPHY = "cryptography>=50.0.0"


def encryption() -> bool:
    """The 'cryptography' package (PyCA, AES via OpenSSL) encrypts each profile's files with its PIN."""
    pip(CRYPTOGRAPHY)                               # a floor, not an exact pin: Pi / Linux / Mac each need their own wheel
    ok = py("-c", "from cryptography.hazmat.primitives.ciphers.aead import AESGCM")
    print("  ✓ files of profiles with a PIN will be encrypted" if ok else
          "  ✗ couldn't install it — PINs will lock the app, but files won't be encrypted")
    return ok


def main(argv: list[str]) -> int:
    if sys.version_info < (3, 10):
        print("Cadet Foundry needs Python 3.10 or newer.")
        return 1
    yes = "--yes" in argv or "-y" in argv
    print("Cadet Foundry setup — needs internet once. Afterwards the device can stay offline.\n")
    plan = [("Encryption (cryptography)", encryption)]          # always: PINs encrypt each Soldier's files
    if ask("Download the faith library (public-domain scriptures, ~32 MB)?", True, yes):
        plan.append(("Faith library", faith))
    if ask("Download the official Army publications and the UCMJ (~150 MB while downloading)?", True, yes):
        plan.append(("Official library", library))
    if ask("Download the free books (Army history, founding documents, classics, ~7 MB)?", True, yes):
        plan.append(("Books", books))
    if "--no-voice" not in argv and ask("Install offline voice (talk to Cadet Foundry, ~40 MB)?", True, yes):
        plan.append(("Offline voice", voice))
    if "--no-ai" not in argv and ask("Install the offline AI (Ollama + a small model, ~2 GB)?", True, yes):
        model = MODELS["small"] if ("--model=1.5b" in argv or (not yes and not ask(
            "  Use the recommended 3B model? (say no only on a very old or slow device)", True, yes))) else MODELS["medium"]
        plan.append((f"Offline AI ({model})", lambda: ai(model)))
    if "--no-shortcut" not in argv and ask("Add a Cadet Foundry shortcut?", True, yes):
        plan.append(("Shortcut", shortcut))
    plan.append(("Self-check", self_check))
    results = []
    for name, step in plan:
        print(f"\n▶ {name}")
        try:
            ok = step()
        except Exception as e:                     # one failed step never stops the rest
            print("  ", e)
            ok = False
        results.append((name, ok))
    print("\nSummary")
    for name, ok in results:
        print(f"  {'✓' if ok else '✗'} {name}")
    print("\nStart Cadet Foundry with the shortcut, start-cadetfoundry.bat (Windows) or sh start-cadetfoundry.sh (Linux).")
    print("Then set a PIN — it encrypts your files — and write down your recovery code. See SECURITY.md.")
    return 0 if all(ok for _n, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
