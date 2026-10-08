"""
Security for Recruit's local server.

Threats handled here:
  * Other websites in the same browser sending commands to Recruit (CSRF):
    POSTs must be JSON (forces a CORS preflight, which Recruit never answers),
    and any Origin header must be Recruit's own.
  * DNS-rebinding (a hostile site pointing its name at 127.0.0.1 to read data):
    the Host header must be Recruit's own address.
  * Someone picking up the device / another Soldier on a shared device: every
    profile can have its own PIN, stored only as a salted PBKDF2-SHA256 hash.
    A session (random token in an HttpOnly, SameSite=Strict cookie) is bound to
    exactly one profile and expires after inactivity; wrong guesses are
    throttled per profile with growing lockouts that survive restarts.
  * LAN mode (other devices on the network) is only allowed when every profile has a PIN.

  * Someone copying the files off the device: a profile with a PIN has its files encrypted
    (AES-256-GCM) with a data key that only its PIN unlocks (recruit/vault.py). The key lives
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

from recruit import profiles, store, vault

ITERATIONS = 400_000
COOKIE = "recruit_session"
_lock = threading.Lock()
_sessions: dict[str, list] = {}          # token -> [profile id, last activity, data key or None]


@contextlib.contextmanager
def as_profile(pid: str, key: bytes | None = None):
    tok, ktok = store.use_profile(profiles.folder(pid)), store.use_key(key)
    try:
        yield
    finally:
        store.reset_key(ktok)
        store.reset_profile(tok)


def _encrypt_profile(st: dict, pin: str) -> bytes | None:
    """Give the active profile a data key locked by `pin` and seal its files. Saves the locked key
    first: if this is interrupted, the folder holds a mix of plain and sealed files, which still open."""
    if not vault.AVAILABLE:
        return None
    key = vault.new_key()
    st["vault"] = vault.wrap(key, pin)
    _save(st)
    store.reseal_folder(store.active_profile_dir(), None, key)
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
    ps = profiles.all_profiles()
    return bool(ps) and all(has_pin(p["id"]) for p in ps)


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
            store.reseal_folder(store.active_profile_dir(), key, None)
        for k in ("salt", "hash", "iterations", "vault", "recovery"):
            st.pop(k, None)
        _save(st)
        pid = store.active_profile_dir().name
        for entry in _sessions.values():
            if entry[0] == pid:
                entry[2] = None
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


# ── device admin PIN (for actions that change the whole device, not one profile) ──
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


def check_admin(pin: str) -> str | None:
    """None if `pin` is the device admin PIN, else a plain reason. Wrong guesses are throttled."""
    with _lock:
        st = _admin()
        if not st.get("hash"):
            return "Set a device admin PIN first (Me tab → Device admin PIN)."
        wait = int(st.get("locked_until", 0) - time.time())
        if wait > 0:
            return f"Too many wrong admin PINs. Try again in {wait} seconds."
        if _verify(str(pin or ""), st):
            if st.get("failures"):
                st["failures"] = 0
                st.pop("locked_until", None)
                _admin_save(st)
            return None
        fails = int(st.get("failures", 0)) + 1
        st["failures"] = fails
        if fails >= 5:
            st["locked_until"] = time.time() + min(3600, 30 * 2 ** (fails - 5))
        _admin_save(st)
        return "Wrong admin PIN."


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
        _admin_save({"salt": salt.hex(), "iterations": ITERATIONS, "hash": _hash(new, salt)})
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
            return None, f"Too many wrong PINs. Try again in {wait} seconds."
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
            token = secrets.token_urlsafe(32)
            _sessions[token] = [pid, time.time(), key]
            return token, "ok"
        fails = int(st.get("failures", 0)) + 1
        st["failures"] = fails
        if fails >= 5:                      # 30s, 60s, 120s ... up to 1 hour
            st["locked_until"] = time.time() + min(3600, 30 * 2 ** (fails - 5))
        _save(st)
        left = 5 - fails
        return None, ("Wrong PIN." + (f" {left} tries before a lockout." if left > 0 else " Locked for a while."))


def session_profile(token: str | None) -> str | None:
    """The profile this session is unlocked for, or None (expired / unknown)."""
    if not token:
        return None
    with _lock:
        entry = _sessions.get(token)
        if not entry:
            return None
        pid, last, _key = entry
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
    # microphone only for Recruit's own page (offline voice input); never location or camera
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(self), payment=(), usb=()",
}


def host_ok(host: str | None, port: int, lan: bool) -> bool:
    """Block DNS rebinding: only Recruit's own addresses (any address in LAN mode, which requires PINs)."""
    if lan:
        return True
    return (host or "") in (f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}")


def origin_ok(origin: str | None, host: str | None) -> bool:
    """Browsers send Origin on cross-site requests. If present, it must be Recruit itself."""
    if not origin:
        return True
    return origin in (f"http://{host}",)


# ── recovery codes: the Soldier's own spare key ───────────────────────────
# A second copy of the profile's data key, locked by a random code shown to the Soldier once. With it
# they can set a new PIN when they forget the old one. Nobody else -- not the device owner, not
# Recruit -- can open a profile without the PIN or the code; that's what makes the encryption real.
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
            return None, "This profile has no recovery code.", None
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
            return None, "That recovery code doesn't match.", None
        salt = secrets.token_bytes(16)
        st.update({"salt": salt.hex(), "hash": _hash(new_pin, salt), "iterations": ITERATIONS,
                   "vault": vault.wrap(key, new_pin), "failures": 0})
        st.pop("locked_until", None)
        new_code = _new_recovery(st, key)                # the old code has been used; issue a fresh one
        _save(st)
    end_sessions(pid)
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = [pid, time.time(), key]
    return token, "ok", new_code
