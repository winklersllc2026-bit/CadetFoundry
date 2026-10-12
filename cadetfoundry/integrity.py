"""
Tamper check for the library, and signed offline updates.

Library: the installer records a SHA-256 fingerprint of every manual in library/integrity.json. At startup
Cadet Foundry recomputes them and reports any file that was changed, removed or added since. If the publisher also
signed that list (library/integrity.json.sig), the signature is checked too -- so someone who edits a manual
can't just rewrite the fingerprints to match.

Updates: an update is the normal download zip plus a signature file (.sig) made with the publisher's private
key (tools/sign.py, kept on the build machine -- never on a device). Cadet Foundry checks the signature with the
public key in cadetfoundry/data/release_key.pub, refuses older versions and unsafe paths, then installs.
Soldiers' data lives in its own folder (~/.cadetfoundry) and is never touched by an update.

Signatures are Ed25519 (the 'cryptography' package that setup already installs for encryption).
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import shutil
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "library"
PUBLIC_KEY = Path(__file__).resolve().parent / "data" / "release_key.pub"
MANIFEST = "integrity.json"
_SKIP = {MANIFEST, MANIFEST + ".sig", "README.md"}

# What an update may contain (inside the zip's "CadetFoundry/" folder). Anything else is refused. It must cover everything
# site/build.py puts in a release (tests/test_security.py builds a real release zip and installs it to check).
_ALLOWED_DIRS = ("cadetfoundry/", "web/", "tools/", "tests/", "library/", "faith/", "books/")
_ALLOWED_FILES = {"run.py", "start-cadetfoundry.bat", "start-cadetfoundry.sh", "start-classroom.bat", "start-classroom.sh",
                  "install-cadetfoundry.bat", "install-cadetfoundry.sh", "README.md", "LIBRARY.md", "SECURITY.md"}


# ── fingerprints ────────────────────────────────────────────────────────────

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fingerprints(library: Path = LIBRARY) -> dict[str, str]:
    return {p.relative_to(library).as_posix(): sha256(p) for p in sorted(library.rglob("*"))
            if p.is_file() and p.name not in _SKIP and not p.name.startswith((".", "_"))}


def write_manifest(library: Path = LIBRARY) -> Path:
    """Record the library's fingerprints (run by the installer after downloading)."""
    out = library / MANIFEST
    out.write_text(json.dumps({"created": time.strftime("%Y-%m-%d %H:%M"), "files": fingerprints(library)},
                              indent=1, sort_keys=True), encoding="utf-8")
    return out


# ── signatures ──────────────────────────────────────────────────────────────

def public_key():
    if not PUBLIC_KEY.exists():
        return None
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY.read_text().strip()))


def signature_ok(data: bytes, sig_b64: str, key=None) -> bool:
    try:
        key = key or public_key()
        if key is None:                             # no public key on this copy: nothing verifies (fail closed)
            return False
        sig = base64.b64decode(sig_b64.strip(), validate=True)    # strict: no junk around the signature
        if len(sig) != 64:                          # an Ed25519 signature is exactly 64 bytes
            return False
        key.verify(sig, data)
        return True
    except Exception:                               # bad signature, bad encoding, no cryptography package
        return False


# ── library check ───────────────────────────────────────────────────────────

def check_library(library: Path = LIBRARY, key=None) -> dict:
    manifest = library / MANIFEST
    if not manifest.exists():
        return {"status": "unrecorded", "changed": [], "missing": [], "added": [], "signed": False,
                "message": "No fingerprints recorded yet — they're made when the library is installed."}
    raw = manifest.read_bytes()
    sig = library / (MANIFEST + ".sig")
    signed = sig.exists()
    if signed and not signature_ok(raw, sig.read_text(), key):
        return {"status": "bad_signature", "changed": [], "missing": [], "added": [], "signed": True,
                "message": "The library's fingerprint list doesn't match its signature — it may have been altered."}
    want = json.loads(raw.decode("utf-8")).get("files", {})
    have = fingerprints(library)
    changed = sorted(n for n in want if n in have and have[n] != want[n])
    missing = sorted(n for n in want if n not in have)
    added = sorted(n for n in have if n not in want)
    ok = not (changed or missing)
    return {"status": "ok" if ok else "changed", "changed": changed, "missing": missing, "added": added,
            "signed": signed, "files": len(want),
            "message": (f"All {len(want)} library files match their fingerprints" + (" (signed list)." if signed else ".")
                        if ok else "Some library files were changed or removed since they were installed.")}


# ── signed updates ──────────────────────────────────────────────────────────

def _version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def current_version(root: Path = ROOT) -> str:
    m = re.search(r'__version__\s*=\s*"([^"]+)"', (root / "cadetfoundry" / "__init__.py").read_text(encoding="utf-8"))
    return m.group(1) if m else "0"


def inspect_update(zip_bytes: bytes, sig_b64: str, root: Path = ROOT, key=None) -> dict:
    """Check an update without installing it. Raises ValueError with a plain reason if it isn't safe."""
    if not signature_ok(zip_bytes, sig_b64, key):
        raise ValueError("The signature doesn't match this update — it wasn't made by the publisher or was changed. "
                         "Nothing was installed.")
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise ValueError("That isn't a Cadet Foundry update file.")
    files = []
    for info in z.infolist():
        name = info.filename
        if info.is_dir():
            continue
        if (not name.startswith("CadetFoundry/") or ".." in Path(name).parts or name.startswith("/") or "\\" in name
                or ":" in name or any(ord(c) < 32 for c in name)):   # ':' = a drive or a Windows alternate stream
            raise ValueError(f"Unsafe path in the update: {name}")
        rel = name[len("CadetFoundry/"):]
        if not (rel in _ALLOWED_FILES or rel.startswith(_ALLOWED_DIRS)):
            raise ValueError(f"Unexpected file in the update: {rel}")
        files.append((info, rel))
    try:
        init = z.read("CadetFoundry/cadetfoundry/__init__.py").decode("utf-8")
        new = re.search(r'__version__\s*=\s*"([^"]+)"', init).group(1)
    except (KeyError, AttributeError):
        raise ValueError("The update has no version number.")
    cur = current_version(root)
    if _version_tuple(new) <= _version_tuple(cur):
        raise ValueError(f"This update is version {new}; this device already has {cur}. Older or equal versions "
                         "aren't installed.")
    return {"version": new, "current": cur, "files": len(files), "_zip": z, "_files": files}


_PREVIOUS, _INCOMPLETE = ".update-previous", "_INCOMPLETE"


def install_update(zip_bytes: bytes, sig_b64: str, root: Path = ROOT, key=None) -> dict:
    """Install a signed update. Everything is unpacked first; every file it replaces is copied aside first; if any
    step fails the app is put back exactly as it was (and if Cadet Foundry stops part-way, finish_pending_update() puts it
    back at the next start). Fails closed: no signature, a wrong one, or no public key -> nothing changes."""
    info = inspect_update(zip_bytes, sig_b64, root, key)
    z, files = info.pop("_zip"), info.pop("_files")
    finish_pending_update(root)
    staging, previous = root / ".update-staging", root / _PREVIOUS
    shutil.rmtree(staging, ignore_errors=True)
    for zi, rel in files:                            # unpack everything first, so a failure leaves the app as it was
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(z.read(zi))
    shutil.rmtree(previous, ignore_errors=True)       # the files this update replaces, for rollback
    previous.mkdir(parents=True)
    added = [rel for _zi, rel in files if not (root / rel).exists()]
    (previous / _INCOMPLETE).write_text(json.dumps({"added": added}), encoding="utf-8")
    for _zi, rel in files:
        if (root / rel).exists():
            (previous / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, previous / rel)
    try:
        for _zi, rel in files:
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            (staging / rel).replace(dest)
    except OSError:
        _rollback_update(root)
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError("The update couldn't be installed (a file was in use?). Cadet Foundry was put back as it was.") from None
    (previous / _INCOMPLETE).unlink()
    shutil.rmtree(previous, ignore_errors=True)
    shutil.rmtree(staging, ignore_errors=True)
    rels = {rel for _zi, rel in files}
    if any(r.startswith("library/") for r in rels) and f"library/{MANIFEST}" not in rels and (root / "library").exists():
        write_manifest(root / "library")             # the update was signed, so its library files are the new baseline
    return {**info, "ok": True, "restart": True}


def _rollback_update(root: Path) -> None:
    """Put back every file an unfinished update replaced, and remove the ones it added."""
    previous = root / _PREVIOUS
    try:
        added = json.loads((previous / _INCOMPLETE).read_text(encoding="utf-8")).get("added", [])
    except (OSError, ValueError):
        added = []
    for f in previous.rglob("*"):
        if f.is_file() and f.name != _INCOMPLETE:
            rel = f.relative_to(previous)
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, root / rel)
    for rel in added:
        if ".." not in Path(rel).parts:
            (root / rel).unlink(missing_ok=True)
    shutil.rmtree(previous, ignore_errors=True)


def finish_pending_update(root: Path = ROOT) -> bool:
    """At start: an update that stopped part-way is rolled back. True if one was."""
    if (root / _PREVIOUS / _INCOMPLETE).exists():
        _rollback_update(root)
        shutil.rmtree(root / ".update-staging", ignore_errors=True)
        return True
    return False
