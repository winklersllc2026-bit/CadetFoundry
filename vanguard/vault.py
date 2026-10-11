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

Uses the `cryptography` package (PyCA; AES via OpenSSL). Without it Cadet Foundry still runs, but PINs only
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
    sealed = AESGCM(_kek(pin, salt, SCRYPT)).encrypt(nonce, key, b"vanguard data key")
    return {"kdf": "scrypt", **SCRYPT, "salt": salt.hex(), "nonce": nonce.hex(), "key": sealed.hex()}


def unwrap(box: dict, pin: str) -> bytes:
    params = {k: int(box[k]) for k in ("n", "r", "p")}
    try:
        return AESGCM(_kek(pin, bytes.fromhex(box["salt"]), params)).decrypt(
            bytes.fromhex(box["nonce"]), bytes.fromhex(box["key"]), b"vanguard data key")
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
    data = AESGCM(_kek(password, salt, SCRYPT)).encrypt(nonce, payload, b"vanguard backup")
    return {"vanguard_backup_sealed": 1, "kdf": "scrypt", **SCRYPT, "salt": salt.hex(), "nonce": nonce.hex(),
            "data": base64.b64encode(data).decode("ascii")}


def open_backup(box: dict, password: str) -> bytes:
    import base64
    try:
        params = {k: int(box[k]) for k in ("n", "r", "p")}
        if params["n"] > 2 ** 20 or params["r"] > 16 or params["p"] > 4:      # a hostile file can't stall the device
            raise ValueError("cost too high")
        return AESGCM(_kek(password, bytes.fromhex(box["salt"]), params)).decrypt(
            bytes.fromhex(box["nonce"]), base64.b64decode(box["data"]), b"vanguard backup")
    except (InvalidTag, ValueError, KeyError, TypeError) as e:
        raise VaultError("Wrong backup password, or the file is damaged.") from e


# ── program keys: what lets the instructor read class records ────────────────
# The instructor's key pair (X25519). The public key is stored in the clear so any Cadet's session can seal that
# Cadet's class key to it; the private key is locked by the Instructor PIN (wrap/unwrap above). The instructor can
# then open class records only -- never a Cadet's private files, which stay under the Cadet's own key.

def new_program_keys() -> tuple[bytes, bytes]:
    """(private, public), 32 raw bytes each."""
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    priv = X25519PrivateKey.generate()
    return (priv.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption()),
            priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw))


def _derive(secret: bytes, info: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(secret)


def seal_to(public: bytes, data: bytes, label: str) -> dict:
    """Encrypt `data` so only the holder of the matching private key can read it (ephemeral X25519 + AES-GCM)."""
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    eph = X25519PrivateKey.generate()
    eph_pub = eph.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    key = _derive(eph.exchange(X25519PublicKey.from_public_bytes(public)), b"vanguard box|" + eph_pub + public)
    nonce = secrets.token_bytes(12)
    return {"eph": eph_pub.hex(), "nonce": nonce.hex(), "to": hashlib.sha256(public).hexdigest()[:16],
            "data": AESGCM(key).encrypt(nonce, data, label.encode("utf-8")).hex()}


def open_from(private: bytes, box: dict, label: str) -> bytes:
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    try:
        priv = X25519PrivateKey.from_private_bytes(private)
        public = priv.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
        eph_pub = bytes.fromhex(box["eph"])
        key = _derive(priv.exchange(X25519PublicKey.from_public_bytes(eph_pub)), b"vanguard box|" + eph_pub + public)
        return AESGCM(key).decrypt(bytes.fromhex(box["nonce"]), bytes.fromhex(box["data"]), label.encode("utf-8"))
    except (InvalidTag, ValueError, KeyError) as e:
        raise VaultError("not sealed to this key, or damaged") from e


def key_id(public: bytes) -> str:
    return hashlib.sha256(public).hexdigest()[:16]


def program_data_key(private: bytes) -> bytes:
    """A symmetric key for the instructor's own files (rosters, notes), derived from the program private key."""
    return _derive(private, b"vanguard program data")
