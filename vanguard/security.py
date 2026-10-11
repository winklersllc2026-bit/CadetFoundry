"""
Security for Vanguard's local server.

Threats handled here:
  * Other websites in the same browser sending commands to Vanguard (CSRF):
    POSTs must be JSON (forces a CORS preflight, which Vanguard never answers),
    and any Origin header must be Vanguard's own.
  * DNS-rebinding (a hostile site pointing its name at 127.0.0.1 to read data):
    the Host header must be Vanguard's own address.
  * Someone picking up the device / another Soldier on a shared device: every
    profile can have its own PIN, stored only as a salted PBKDF2-SHA256 hash.
    A session (random token in an HttpOnly, SameSite=Strict cookie) is bound to
    exactly one profile and expires after inactivity; wrong guesses are
    throttled per profile with growing lockouts that survive restarts.
  * LAN mode (other devices on the network) is only allowed when every profile has a PIN.

  * Someone copying the files off the device: a profile with a PIN has its files encrypted
    (AES-256-GCM) with a data key that only its PIN unlocks (vanguard/vault.py). The key lives
    in memory only while the profile is unlocked.

Full-disk encryption (BitLocker / LUKS) is still recommended for the device itself. See SECURITY.md.
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import secrets
import threading
import time

from vanguard import profiles, store, vault

ITERATIONS = 400_000
COOKIE = "vanguard_session"
_lock = threading.Lock()
# token -> [profile id, last activity, data key, class key, program private key (instructor, after the Instructor PIN)]
_sessions: dict[str, list] = {}


@contextlib.contextmanager
def as_profile(pid: str, key: bytes | None = None, class_key: bytes | None = None):
    tok, ktok, ctok = store.use_profile(profiles.folder(pid)), store.use_key(key), store.use_class_key(class_key)
    try:
        yield
    finally:
        store.reset_class_key(ctok)
        store.reset_key(ktok)
        store.reset_profile(tok)


def _ensure_class_key(st: dict, key: bytes | None) -> bytes | None:
    """The active profile's class key (see store.CLASS_FILES), created on first use, and kept sealed to the current
    program public key so the instructor can read class records. None for a profile without encryption."""
    if key is None or not vault.AVAILABLE:
        return None
    if st.get("class_vault"):
        ck = vault.open_sealed(key, bytes.fromhex(st["class_vault"]), "class key")
    else:
        ck = vault.new_key()
        st["class_vault"] = vault.seal(key, ck, "class key").hex()
        _save(st)                                   # saved first; store reads still fall back to the data key
        store.reseal_folder(store.active_profile_dir(), key, ck, only=store.CLASS_FILES)
    pub = program_public()
    if pub and (st.get("class_for") or {}).get("to") != vault.key_id(pub):
        st["class_for"] = vault.seal_to(pub, ck, "class key")
        _save(st)
    return ck


def _encrypt_profile(st: dict, pin: str) -> bytes | None:
    """Give the active profile a data key locked by `pin` and seal its files. Saves the locked key
    first: if this is interrupted, the folder holds a mix of plain and sealed files, which still open."""
    if not vault.AVAILABLE:
        return None
    key = vault.new_key()
    st["vault"] = vault.wrap(key, pin)
    _save(st)
    store.reseal_folder(store.active_profile_dir(), None, key)
    _ensure_class_key(st, key)
    return key


def _state() -> dict:
    return store.read_json("security.json", {})


def _save(st: dict) -> None:
    store.write_json("security.json", st)


# ── PIN (for the active profile) ───────────────────────────────────────────

def pin_set() -> bool:
    return bool(_state().get("hash"))


def has_pin(pid: str) -> bool:
    with as_profile(pid):
        return pin_set()


def all_have_pins() -> bool:
    """Every profile on this device has a PIN (true for a brand-new device with no profiles yet -- in LAN mode the
    server then requires a PIN on every profile it creates, so it stays true)."""
    return all(has_pin(p["id"]) for p in profiles.all_profiles())


def idle_minutes() -> int:
    return int(_state().get("idle_minutes", 15))


def _hash(pin: str, salt: bytes, iterations: int = ITERATIONS) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations).hex()


def valid_new_pin(pin: str) -> str | None:
    if not pin or not pin.isdigit() or not 6 <= len(pin) <= 12:
        return "Use a PIN of 6 to 12 digits."
    if len(set(pin)) == 1 or pin in "0123456789012" or pin in "9876543210987":
        return "That PIN is too easy to guess (repeated or sequential digits)."
    return None


def set_pin(new: str, current: str = "") -> str | None:
    """Set or change the active profile's PIN. Returns an error message, or None on success."""
    with _lock:
        st = _state()
        if st.get("hash") and not _verify(current, st):
            return "Your current PIN is wrong."
        err = valid_new_pin(new)
        if err:
            return err
        salt = secrets.token_bytes(16)
        if st.get("vault"):                  # changing the PIN: re-lock the same data key, files untouched
            st["vault"] = vault.wrap(vault.unwrap(st["vault"], current), new)
        st.update({"salt": salt.hex(), "hash": _hash(new, salt), "iterations": ITERATIONS})
        _save(st)
        if not st.get("vault"):
            _encrypt_profile(st, new)
    return None


def remove_pin(current: str) -> str | None:
    with _lock:
        st = _state()
        if st.get("hash") and not _verify(current, st):
            return "Your PIN is wrong."
        if st.get("vault"):                  # no PIN, no encryption: decrypt the files first
            key = vault.unwrap(st["vault"], current)
            folder = store.active_profile_dir()
            if st.get("class_vault"):
                ck = vault.open_sealed(key, bytes.fromhex(st["class_vault"]), "class key")
                store.reseal_folder(folder, ck, None, only=store.CLASS_FILES)
                store.reseal_folder(folder, key, None, skip=store.CLASS_FILES)
            else:
                store.reseal_folder(folder, key, None)
        for k in ("salt", "hash", "iterations", "vault", "recovery", "class_vault", "class_for"):
            st.pop(k, None)
        _save(st)
        pid = store.active_profile_dir().name
        for entry in _sessions.values():
            if entry[0] == pid:
                entry[2] = entry[3] = None
    return None


def verify_current(pin: str) -> bool:
    return _verify(pin, _state())


def set_idle_minutes(minutes) -> int:
    minutes = max(1, min(240, int(minutes)))
    with _lock:
        st = _state()
        st["idle_minutes"] = minutes
        _save(st)
    return minutes


def _verify(pin: str, st: dict) -> bool:
    if not st.get("hash"):
        return True
    try:
        h = _hash(pin or "", bytes.fromhex(st["salt"]), int(st.get("iterations", ITERATIONS)))
    except Exception:
        return False
    return hmac.compare_digest(h, st["hash"])


# ── Instructor PIN (for actions that change the whole device, not one profile) ──
# Kept in the data folder, outside every profile, as a salted PBKDF2 hash. Installing an update needs it,
# so one Soldier's profile PIN can't change the app for everyone on a shared device.

def _admin_path():
    return store.DATA / "admin.json"


def _admin() -> dict:
    try:
        return json.loads(_admin_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _admin_save(st: dict) -> None:
    path = _admin_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(st), encoding="utf-8")
    tmp.replace(path)


def admin_set() -> bool:
    return bool(_admin().get("hash"))


# The program key pair (vault.new_program_keys): public key in the clear, private key locked by the Instructor PIN.
def _program_path():
    return store.DATA / "program.json"


def _program() -> dict:
    try:
        return json.loads(_program_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _program_save(prog: dict) -> None:
    path = _program_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(prog), encoding="utf-8")
    tmp.replace(path)


def program_public() -> bytes | None:
    pub = _program().get("public")
    return bytes.fromhex(pub) if pub else None


def _new_program(pin: str) -> None:
    if vault.AVAILABLE:
        priv, pub = vault.new_program_keys()
        _program_save({"public": pub.hex(), "private": vault.wrap(priv, pin)})


def check_admin(pin: str) -> str | None:
    """None if `pin` is the Instructor PIN, else a plain reason. Wrong guesses are throttled."""
    with _lock:
        st = _admin()
        if not st.get("hash"):
            return "Set the Class PIN on this computer first (👤 Me → Class PIN)."
        wait = int(st.get("locked_until", 0) - time.time())
        if wait > 0:
            return f"Too many wrong Class PINs. Wait {wait} seconds and try again."
        if _verify(str(pin or ""), st):
            if st.get("failures"):
                st["failures"] = 0
                st.pop("locked_until", None)
                _admin_save(st)
            if not _program():                     # a device set up before program keys existed
                _new_program(str(pin))
            return None
        fails = int(st.get("failures", 0)) + 1
        st["failures"] = fails
        if fails >= 5:
            st["locked_until"] = time.time() + min(3600, 30 * 2 ** (fails - 5))
        _admin_save(st)
        return "That Class PIN isn't right."


def set_admin_pin(new: str, current: str = "") -> str | None:
    if admin_set():
        err = check_admin(current)
        if err:
            return err
    err = valid_new_pin(new)
    if err:
        return err
    salt = secrets.token_bytes(16)
    with _lock:
        prog = _program() if admin_set() else {}
        if prog:                                   # changing the PIN: same key pair, locked by the new PIN
            prog["private"] = vault.wrap(vault.unwrap(prog["private"], current), new)
            _program_save(prog)
        _admin_save({"salt": salt.hex(), "iterations": ITERATIONS, "hash": _hash(new, salt)})
    if not prog:
        # A first (or reset) Instructor PIN gets a fresh program key. Cadets' class keys are re-shared to it at
        # their next sign-in; a roster sealed with an old key can't be read and starts over.
        _new_program(new)
    return None


# ── unlocking, with throttling (per profile) ───────────────────────────────

def lockout_remaining(pid: str) -> int:
    with as_profile(pid):
        return max(0, int(_state().get("locked_until", 0) - time.time()))


def unlock(pid: str, pin: str) -> tuple[str | None, str]:
    """(session token or None, message)."""
    if not profiles.get(pid):
        return None, "No such profile."
    with _lock, as_profile(pid):
        st = _state()
        wait = int(st.get("locked_until", 0) - time.time())
        if wait > 0:
            return None, f"Too many wrong PINs. Wait {wait} seconds and try again."
        if _verify(pin, st):
            if st.get("failures") or st.get("locked_until"):
                st["failures"] = 0
                st.pop("locked_until", None)
                _save(st)
            key = None
            if st.get("vault"):
                key = vault.unwrap(st["vault"], pin)
            elif st.get("hash"):             # PIN set before encryption existed: encrypt now
                key = _encrypt_profile(st, pin)
            ck = _ensure_class_key(st, key)
            token = secrets.token_urlsafe(32)
            _sessions[token] = [pid, time.time(), key, ck, None]
            return token, "ok"
        fails = int(st.get("failures", 0)) + 1
        st["failures"] = fails
        if fails >= 5:                      # 30s, 60s, 120s ... up to 1 hour
            st["locked_until"] = time.time() + min(3600, 30 * 2 ** (fails - 5))
        _save(st)
        left = 5 - fails
        return None, ("That PIN isn't right." + (f" {left} tries left before a short wait." if left > 0 else " Wait a little, then try again."))


def session_profile(token: str | None) -> str | None:
    """The profile this session is unlocked for, or None (expired / unknown)."""
    if not token:
        return None
    with _lock:
        entry = _sessions.get(token)
        if not entry:
            return None
        pid, last = entry[0], entry[1]
        if not profiles.get(pid):
            _sessions.pop(token, None)
            return None
        with as_profile(pid):
            limit = idle_minutes() * 60 if pin_set() else 7 * 24 * 3600
        if time.time() - last > limit:
            _sessions.pop(token, None)
            return None
        entry[1] = time.time()
        return pid


def session_key(token: str | None) -> bytes | None:
    """The data key of an unlocked session (None for a profile without a PIN)."""
    entry = _sessions.get(token or "")
    return entry[2] if entry else None


def session_class_key(token: str | None) -> bytes | None:
    entry = _sessions.get(token or "")
    return entry[3] if entry else None


def drop_program_keys() -> None:
    """After a program restore the program key may have changed: every instructor enters the Instructor PIN again."""
    with _lock:
        for entry in _sessions.values():
            entry[4] = None


def session_program_key(token: str | None) -> bytes | None:
    """The program private key, only in an instructor's session after the Instructor PIN was entered."""
    entry = _sessions.get(token or "")
    return entry[4] if entry else None


def unlock_program(token: str | None, pin: str) -> str | None:
    """An instructor's session opens the class records: needs an instructor profile AND the Instructor PIN."""
    entry = _sessions.get(token or "")
    if not entry or (profiles.get(entry[0]) or {}).get("kind") != "instructor":
        return "Only an instructor profile can open class records."
    err = check_admin(pin)
    if err:
        return err
    try:
        priv = vault.unwrap(_program()["private"], pin)
    except (vault.VaultError, KeyError):
        return "The program key is missing or damaged."
    with _lock:
        entry[4] = priv
    return None


def lock(token: str | None) -> None:
    with _lock:
        _sessions.pop(token or "", None)


def end_sessions(pid: str, keep: str | None = None) -> None:
    """Sign out every session of a profile (e.g. after its PIN changes), optionally keeping one."""
    with _lock:
        for t in [t for t, e in _sessions.items() if e[0] == pid and t != keep]:
            _sessions.pop(t, None)


def cookie_header(token: str) -> str:
    return f"{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/"


def token_from_cookie(cookie_header_value: str | None) -> str | None:
    for part in (cookie_header_value or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return None


# ── request checks ──────────────────────────────────────────────────────────

SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
                                "form-action 'self'; object-src 'none'"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    # microphone only for Vanguard's own page (offline voice input); never location or camera
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(self), payment=(), usb=()",
}


def host_ok(host: str | None, port: int, lan: bool, local_ip: str | None = None) -> bool:
    """Block DNS rebinding: the Host header must name Vanguard itself, with Vanguard's port.

    This computer: 127.0.0.1, localhost or [::1]. Classroom mode also accepts this computer's own IP address -- the
    exact address the device connected to (local_ip, from the socket), which is what the QR code and the Join screen
    show. A domain name is refused in classroom mode: DNS rebinding (a website pointing its own name at this
    computer, so a Cadet's browser treats Vanguard as that site) needs one. Security review, 2026-10-11 -- before,
    classroom mode accepted any Host."""
    h = (host or "").strip()
    if h.startswith("["):                                   # [IPv6]:port
        name, _, rest = h.partition("]")
        name, p = name + "]", rest[1:] if rest.startswith(":") else ""
    elif h.count(":") == 1:
        name, p = h.split(":")
    else:
        name, p = h, ""
    if p != str(port) and not (p == "" and port == 80):
        return False
    name = name.lower()
    if name in ("127.0.0.1", "localhost", "[::1]"):
        return True
    if not lan or not local_ip:
        return False
    lip = local_ip.lower()
    if lip.startswith("::ffff:"):                          # an IPv4 client on a dual-stack socket
        lip = lip[7:]
    return name in (lip, f"[{lip}]")


def origin_ok(origin: str | None, host: str | None) -> bool:
    """Browsers send Origin on cross-site requests. If present, it must be Vanguard itself."""
    if not origin:
        return True
    return origin in (f"http://{host}",)


# ── recovery codes: the Soldier's own spare key ───────────────────────────
# A second copy of the profile's data key, locked by a random code shown to the Soldier once. With it
# they can set a new PIN when they forget the old one. Nobody else -- not the device owner, not
# Vanguard -- can open a profile without the PIN or the code; that's what makes the encryption real.
_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"          # no 0/O or 1/I to misread
_CODE_LEN = 20                                                  # 100 bits


def _normal_code(code: str) -> str:
    return "".join(c for c in (code or "").upper() if c in _CODE_ALPHABET)


def _new_recovery(st: dict, key: bytes) -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))
    st["recovery"] = vault.wrap(key, raw)
    return "-".join(raw[i:i + 5] for i in range(0, _CODE_LEN, 5))


def has_recovery() -> bool:
    return bool(_state().get("recovery"))


def make_recovery_code(pin: str) -> str | None:
    """A new recovery code for the active profile (replaces any old one). Needs the current PIN."""
    if not vault.AVAILABLE:
        return None
    with _lock:
        st = _state()
        if not st.get("vault") or not _verify(pin, st):
            return None
        code = _new_recovery(st, vault.unwrap(st["vault"], pin))
        _save(st)
    return code


def recover(pid: str, code: str, new_pin: str) -> tuple[str | None, str, str | None]:
    """Forgot the PIN: open the profile with its recovery code and set a new PIN.
    Returns (session token or None, message, the NEW recovery code). Wrong codes count toward the
    same lockout as wrong PINs, so the code can't be guessed either."""
    if not profiles.get(pid):
        return None, "No such profile.", None
    with _lock, as_profile(pid):
        st = _state()
        wait = int(st.get("locked_until", 0) - time.time())
        if wait > 0:
            return None, f"Too many wrong tries. Try again in {wait} seconds.", None
        if not st.get("recovery"):
            return None, "This profile has no backup code.", None
        err = valid_new_pin(new_pin)
        if err:
            return None, err, None
        try:
            key = vault.unwrap(st["recovery"], _normal_code(code))
        except vault.VaultError:
            fails = int(st.get("failures", 0)) + 1
            st["failures"] = fails
            if fails >= 5:
                st["locked_until"] = time.time() + min(3600, 30 * 2 ** (fails - 5))
            _save(st)
            return None, "That backup code doesn't match.", None
        salt = secrets.token_bytes(16)
        st.update({"salt": salt.hex(), "hash": _hash(new_pin, salt), "iterations": ITERATIONS,
                   "vault": vault.wrap(key, new_pin), "failures": 0})
        st.pop("locked_until", None)
        new_code = _new_recovery(st, key)                # the old code has been used; issue a fresh one
        _save(st)
        ck = _ensure_class_key(st, key)
    end_sessions(pid)
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = [pid, time.time(), key, ck, None]
    return token, "ok", new_code
