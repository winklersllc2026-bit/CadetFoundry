"""
Install offline voice input for Vanguard (needs internet once).

    python tools/install_voice.py

Installs the Vosk speech recognizer (Apache 2.0 license) and its small English
model (~40 MB, from alphacephei.com, the Vosk project). After this, speech-to-text
runs entirely on the device.
"""
import hashlib
import io
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vanguard.addons import VOICE_MODEL, VOSK  # noqa: E402  (same pinned versions + fingerprint as the in-app add-on)

DEST = ROOT / "voice-model"
MODEL_URL, MODEL_SHA256 = VOICE_MODEL


def main() -> int:
    print("Installing the vosk package …")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", VOSK])
    if r.returncode != 0:
        print("Couldn't install vosk with pip.")
        return 1
    if DEST.exists() and any(DEST.iterdir()):
        print(f"Model already installed in {DEST}")
        return 0
    print("Downloading the small English model (~40 MB) …")
    with urllib.request.urlopen(urllib.request.Request(MODEL_URL, headers={"User-Agent": "Vanguard"}), timeout=300) as resp:
        data = resp.read()
    if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
        print("The model download doesn't match its known fingerprint — not installing it.")
        return 1
    z = zipfile.ZipFile(io.BytesIO(data))
    top = z.namelist()[0].split("/")[0]
    DEST.mkdir(exist_ok=True)
    for name in z.namelist():
        if name.endswith("/"):
            continue
        rel = Path(name).relative_to(top)
        out = (DEST / rel).resolve()
        if not out.is_relative_to(DEST.resolve()):          # never write outside the folder
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(z.read(name))
    print(f"Voice input installed. Restart Vanguard; a 🎤 button appears next to Send.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
