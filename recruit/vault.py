"""
Encryption at rest for each Soldier's files.

Every profile with a PIN has its own random 256-bit data key. The data key is stored only "wrapped"
(encrypted) by a key derived from the PIN with scrypt, a deliberately slow, memory-hard function that
makes guessing PINs from a copied disk expensive. While a profile is unlocked, the data key lives only
in the server's memory; it is never written to disk unwrapped.

Files are sealed with AES-256-GCM, which both hides and authenticates them: a file that was changed,
truncated or copied in from another profile or under another name fails to open instead of being read.

    sealed file = b"RCV1" + 12-byte nonce + ciphertext (with tag)
    associated data = the file's name, so files can't be swapped or renamed into place

Uses the `cryptography` package (PyCA; AES via OpenSSL). Without it Recruit still runs, but PINs only
lock the app, not the files -- SECURITY.md says so and the status shows it.
"""
from __future__ import annotations

import hashlib
import secrets

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    AVAILABLE = True
except ImportError:                          # pragma: no cover -- setup installs it
    AESGCM = None
    InvalidTag = Exception
    AVAILABLE = False

MAGIC = b"RCV1"
# scrypt cost: 2**15 x 8 x 128 bytes = 32 MB of memory, about a tenth of a second per attempt.
SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1}


class VaultError(RuntimeError):
    """A sealed file can't be opened: wrong key, tampered with, or the profile is locked."""


def new_key() -> bytes:
    return secrets.token_bytes(32)


def _kek(pin: str, salt: bytes, params: dict) -> bytes:
    return hashlib.scrypt(pin.encode("utf-8"), salt=salt, n=params["n"], r=params["r"], p=params["p"],
                          maxmem=2 ** 26, dklen=32)


def wrap(key: bytes, pin: str) -> dict:
    """Lock the data key with the PIN. Returns what's stored in security.json."""
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    sealed = AESGCM(_kek(pin, salt, SCRYPT)).encrypt(nonce, key, b"recruit data key")
    return {"kdf": "scrypt", **SCRYPT, "salt": salt.hex(), "nonce": nonce.hex(), "key": sealed.hex()}


def unwrap(box: dict, pin: str) -> bytes:
    params = {k: int(box[k]) for k in ("n", "r", "p")}
    try:
        return AESGCM(_kek(pin, bytes.fromhex(box["salt"]), params)).decrypt(
            bytes.fromhex(box["nonce"]), bytes.fromhex(box["key"]), b"recruit data key")
    except (InvalidTag, ValueError, KeyError) as e:
        raise VaultError("wrong PIN or damaged key") from e


def is_sealed(data: bytes) -> bool:
    return data[:4] == MAGIC


def seal(key: bytes, data: bytes, name: str) -> bytes:
    nonce = secrets.token_bytes(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, data, name.encode("utf-8"))


def open_sealed(key: bytes | None, data: bytes, name: str) -> bytes:
    if key is None:
        raise VaultError(f"{name} is encrypted and the profile is locked")
    try:
        return AESGCM(key).decrypt(data[4:16], data[16:], name.encode("utf-8"))
    except InvalidTag as e:
        raise VaultError(f"{name} failed its integrity check (changed, damaged, or from another profile)") from e


# ── password-sealed backups ─────────────────────────────────────────────────
# A backup can leave the device (USB stick, another computer), where it can be attacked offline for as
# long as someone likes, so it needs a real password, not a 6-digit PIN.
MIN_BACKUP_PASSWORD = 10


def backup_password_problem(password: str) -> str | None:
    if len(password or "") < MIN_BACKUP_PASSWORD:
        return f"Use a backup password of at least {MIN_BACKUP_PASSWORD} characters — three or four words works well."
    if len(set(password)) < 5:
        return "That backup password is too easy to guess."
    return None


def seal_backup(payload: bytes, password: str) -> dict:
    import base64
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    data = AESGCM(_kek(password, salt, SCRYPT)).encrypt(nonce, payload, b"recruit backup")
    return {"recruit_backup_sealed": 1, "kdf": "scrypt", **SCRYPT, "salt": salt.hex(), "nonce": nonce.hex(),
            "data": base64.b64encode(data).decode("ascii")}


def open_backup(box: dict, password: str) -> bytes:
    import base64
    try:
        params = {k: int(box[k]) for k in ("n", "r", "p")}
        if params["n"] > 2 ** 20 or params["r"] > 16 or params["p"] > 4:      # a hostile file can't stall the device
            raise ValueError("cost too high")
        return AESGCM(_kek(password, bytes.fromhex(box["salt"]), params)).decrypt(
            bytes.fromhex(box["nonce"]), base64.b64decode(box["data"]), b"recruit backup")
    except (InvalidTag, ValueError, KeyError, TypeError) as e:
        raise VaultError("Wrong backup password, or the file is damaged.") from e
