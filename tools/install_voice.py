"""
Install offline voice input for Recruit (needs internet once).

    python tools/install_voice.py

Installs the Vosk speech recognizer (Apache 2.0 license) and its small English
model (~40 MB, from alphacephei.com, the Vosk project). After this, speech-to-text
runs entirely on the device.
"""
import io
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "voice-model"
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"


def main() -> int:
    print("Installing the vosk package …")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "vosk"])
    if r.returncode != 0:
        print("Couldn't install vosk with pip.")
        return 1
    if DEST.exists() and any(DEST.iterdir()):
        print(f"Model already installed in {DEST}")
        return 0
    print("Downloading the small English model (~40 MB) …")
    with urllib.request.urlopen(urllib.request.Request(MODEL_URL, headers={"User-Agent": "Cursiv-Recruit"}), timeout=300) as resp:
        data = resp.read()
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
    print(f"Voice input installed. Restart Recruit; a 🎤 button appears next to Send.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
