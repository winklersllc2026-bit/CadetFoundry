"""
Release signing for Recruit updates and the library (run on the BUILD machine only).

    python tools/sign.py keygen                 make your signing key (once)
    python tools/sign.py sign site/dist/Cursiv-Recruit-0.9.0.zip     -> ...zip.sig
    python tools/sign.py library                fingerprint library/ and sign the list

The private key is written OUTSIDE the project (default ~/.cursiv-recruit-release/release_key.pem) so it
never ends up in git, a zip or a device. Back it up somewhere safe: without it you can't sign updates,
and anyone who has it can. The public key goes into recruit/data/release_key.pub, which ships with the app.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from recruit import integrity  # noqa: E402

DEFAULT_KEY = Path.home() / ".cursiv-recruit-release" / "release_key.pem"


def _arg(argv: list[str], flag: str, default: Path) -> Path:
    return Path(argv[argv.index(flag) + 1]) if flag in argv else default


def load_key(path: Path):
    from cryptography.hazmat.primitives import serialization
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def keygen(argv: list[str]) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    path = _arg(argv, "--key", DEFAULT_KEY)
    if path.exists() and "--force" not in argv:
        print(f"{path} already exists. Use --force only if you mean to replace it — devices with the old public key "
              "will then refuse your updates until they get the new one.")
        return 1
    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                       serialization.NoEncryption()))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    integrity.PUBLIC_KEY.write_text(base64.b64encode(pub).decode() + "\n")
    print(f"Private key: {path}  (keep it safe and OFF every device)\nPublic key:  {integrity.PUBLIC_KEY} (commit this)")
    return 0


def sign_file(path: Path, key) -> Path:
    sig = path.with_name(path.name + ".sig")
    sig.write_text(base64.b64encode(key.sign(path.read_bytes())).decode() + "\n")
    return sig


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("keygen", "sign", "library"):
        print(__doc__)
        return 1
    if argv[0] == "keygen":
        return keygen(argv[1:])
    key = load_key(_arg(argv, "--key", DEFAULT_KEY))
    if argv[0] == "sign":
        print("wrote", sign_file(Path(argv[1]), key))
    else:
        manifest = integrity.write_manifest()
        print("wrote", manifest, "and", sign_file(manifest, key))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
