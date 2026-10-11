"""
Check Cadet Foundry's pinned third-party packages against the OSV vulnerability database (needs internet).

    python tools/check_deps.py

Reads the exact versions in site/bundle-requirements.txt (bundled into the Windows installer) and the voice
add-on's vosk pin, asks api.osv.dev about each, and exits 1 if any has a known vulnerability. Only package
names and version numbers are sent. Run it before every release (SECURITY.md, Dependencies).
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vanguard.addons import VOSK  # noqa: E402


def pins() -> list[tuple[str, str]]:
    found = re.findall(r"^([A-Za-z0-9_.-]+)==([\w.]+)", (ROOT / "site" / "bundle-requirements.txt").read_text(), re.M)
    return found + [tuple(VOSK.split("=="))]


def known_vulns(name: str, version: str) -> list[str]:
    body = json.dumps({"package": {"name": name, "ecosystem": "PyPI"}, "version": version}).encode()
    req = urllib.request.Request("https://api.osv.dev/v1/query", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [v["id"] for v in json.loads(r.read()).get("vulns", [])]


def main() -> int:
    bad = 0
    for name, version in pins():
        ids = known_vulns(name, version)
        print(f"{name} {version}: " + (", ".join(ids) if ids else "no known vulnerabilities"))
        bad += bool(ids)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
