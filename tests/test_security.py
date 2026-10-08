"""Attack tests: each request below plays an attacker and must be refused."""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RECRUIT_DATA", tempfile.mkdtemp())
os.environ["RECRUIT_NO_WARMUP"] = "1"

from recruit import profiles, security, store  # noqa: E402
from recruit.server import serve  # noqa: E402


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = serve("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        cls.httpd.RequestHandlerClass.app.port = cls.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.alice = profiles.create(f"Alice-{uuid.uuid4().hex[:8]}")
        cls.bob = profiles.create(f"Bob-{uuid.uuid4().hex[:8]}")
        with security.as_profile(cls.alice["id"]):
            assert security.set_pin("482915") is None
        with security.as_profile(cls.bob["id"]):
            assert security.set_pin("736281") is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def req(self, method, path, body=None, headers=None, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if body is not None:
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        c.request(method, path, body=json.dumps(body) if isinstance(body, dict) else body, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, dict(r.getheaders()), data

    def login(self, pid, pin):
        s, h, _ = self.req("POST", "/api/unlock", {"profile": pid, "pin": pin})
        self.assertEqual(s, 200)
        return h["Set-Cookie"].split(";")[0]

    def test_0_every_route_answers_without_a_server_error(self):
        """Call every /api route (GET and an empty POST) as a logged-in Soldier: nothing may crash (5xx).
        Catches a route that uses a module it never imported -- the unit tests call modules directly."""
        import re
        routes = sorted(set(re.findall(r'if r == "(/api/[^"]+)"', (ROOT / "recruit" / "server.py").read_text())))
        self.assertGreater(len(routes), 40)
        skip = {"/api/quit", "/api/chat", "/api/simplify", "/api/voice", "/api/lock", "/api/profiles/delete", "/api/pin/remove",
                "/api/history/clear", "/api/library/reload", "/api/restore", "/api/update"}      # slow, or ends the session
        cookie = self.login(self.alice["id"], "482915")
        # Routes like letter drafts and the mock board call the AI. On a machine with a real model installed that
        # can take longer than the request timeout, so the test sometimes failed; here the AI answers "no model".
        from unittest import mock
        no_ai = RuntimeError("no AI model in this test")
        with mock.patch("recruit.engine.stream", side_effect=no_ai), mock.patch("recruit.engine.quick", return_value=""):
            for r in routes:
                if r in skip:
                    continue
                for method, body in (("GET", None), ("POST", {})):
                    try:
                        status = self.req(method, r, body, {"Cookie": cookie})[0]
                    except TimeoutError:
                        self.fail(f"{method} {r} timed out")
                    self.assertLess(status, 500, f"{method} {r} -> {status}")

    def test_0_page_scripts_load_while_locked(self):
        """The lock screen lives in web/js/core.js, so the page's scripts load before anyone unlocks -- nothing else does."""
        import re
        page = self.req("GET", "/")[2].decode()
        scripts = re.findall(r'<script src="(/js/[a-z]+\.js)"></script>', page)
        self.assertEqual(scripts[0], "/js/core.js")
        self.assertEqual(scripts[-1], "/js/me.js")
        for src in scripts:
            self.assertEqual(self.req("GET", src)[0], 200, src)
        self.assertEqual(self.req("GET", "/js/../index.html")[0], 401)
        self.assertEqual(self.req("GET", "/api/log")[0], 401)

    def test_1_dns_rebinding_host_refused(self):
        self.assertEqual(self.req("GET", "/api/status", host="evil.example:80")[0], 421)

    def test_2_cross_site_post_refused(self):
        self.assertEqual(self.req("POST", "/api/log", {"text": "x"}, {"Origin": "http://evil.example"})[0], 403)

    def test_3_non_json_post_refused(self):
        s, _, _ = self.req("POST", "/api/restore", '{"recruit_backup":1}', {"Content-Type": "text/plain"})
        self.assertEqual(s, 415)

    def test_4_preflight_refused(self):
        s, h, _ = self.req("OPTIONS", "/api/log")
        self.assertEqual(s, 405)
        self.assertNotIn("Access-Control-Allow-Origin", h)

    def test_5_path_traversal_refused(self):
        cookie = self.login(self.alice["id"], "482915")
        for p in ("/../recruit/store.py", "/..%2frecruit%2fstore.py", "/%2e%2e/run.py", "/web/../run.py"):
            self.assertIn(self.req("GET", p)[0], (401, 404), p)                      # locked: refused
            self.assertEqual(self.req("GET", p, headers={"Cookie": cookie})[0], 404, p)  # unlocked: still refused

    def test_6_security_headers(self):
        _, h, _ = self.req("GET", "/")
        self.assertIn("script-src 'self'", h.get("Content-Security-Policy", ""))
        self.assertEqual(h.get("X-Frame-Options"), "DENY")

    def test_7_locked_without_session_and_wrong_pin(self):
        self.assertEqual(self.req("GET", "/api/log")[0], 401)
        self.assertEqual(self.req("POST", "/api/unlock", {"profile": self.alice["id"], "pin": "000000"})[0], 401)
        cookie = self.login(self.alice["id"], "482915")
        self.assertEqual(self.req("GET", "/api/log", headers={"Cookie": cookie})[0], 200)
        stored = (profiles.folder(self.alice["id"]) / "security.json").read_text()
        self.assertNotIn("482915", stored)                                         # PIN never stored

    def test_8_profiles_are_isolated(self):
        a = self.login(self.alice["id"], "482915")
        b = self.login(self.bob["id"], "736281")
        self.assertEqual(self.req("POST", "/api/log", {"text": "Alice private note"}, {"Cookie": a})[0], 200)
        _, _, bob_log = self.req("GET", "/api/log", headers={"Cookie": b})
        self.assertNotIn("Alice private note", bob_log.decode())                  # Bob can't see Alice's logbook
        _, _, alice_log = self.req("GET", "/api/log", headers={"Cookie": a})
        self.assertIn("Alice private note", alice_log.decode())
        # a forged / foreign cookie never opens anyone's data
        self.assertEqual(self.req("GET", "/api/log", headers={"Cookie": "recruit_session=forged"})[0], 401)
        self.assertIsNotNone(profiles.get(self.alice["id"]))

    def test_9_lockout_after_repeated_wrong_pins(self):
        p = profiles.create(f"Carol-{uuid.uuid4().hex[:8]}")
        with security.as_profile(p["id"]):
            self.assertIsNone(security.set_pin("739164"))
        for _ in range(5):
            security.unlock(p["id"], "000000")
        self.assertGreater(security.lockout_remaining(p["id"]), 0)
        token, _ = security.unlock(p["id"], "739164")          # even the right PIN waits during a lockout
        self.assertIsNone(token)

    def test_10_lan_mode_requires_pins_on_every_profile(self):
        profiles.create(f"NoPin-{uuid.uuid4().hex[:8]}")
        with self.assertRaises(SystemExit):
            serve("127.0.0.1", 0, lan=True)

    def test_11_weak_pins_rejected(self):
        self.assertIn("6 to 12", security.valid_new_pin("123") or "")
        self.assertIn("easy", security.valid_new_pin("111111") or "")
        self.assertIn("easy", security.valid_new_pin("123456") or "")



    def test_12_backup_carries_family_setting_to_new_device(self):
        dana = profiles.create(f"Dana-{uuid.uuid4().hex[:8]}", kind="family")
        evan = profiles.create(f"Evan-{uuid.uuid4().hex[:8]}")                  # new device: created as a Soldier
        for p, pin in ((dana, "583917"), (evan, "694028")):
            with security.as_profile(p["id"]):
                self.assertIsNone(security.set_pin(pin))
        d = self.login(dana["id"], "583917")
        self.assertEqual(self.req("POST", "/api/log", {"text": "Dana's note"}, {"Cookie": d})[0], 200)
        self.assertEqual(self.req("POST", "/api/backup", {"password": "short"}, {"Cookie": d})[0], 400)  # weak password
        s, _, raw = self.req("POST", "/api/backup", {"password": "blue river tank 42"}, {"Cookie": d})
        self.assertEqual(s, 200)
        sealed = json.loads(raw)["file"]
        self.assertTrue(sealed["recruit_backup_sealed"])
        self.assertNotIn("Dana", json.dumps(sealed))                        # nothing readable in the file
        from recruit import backup as _backup
        backup_file = _backup.open_any(sealed, "blue river tank 42")
        self.assertEqual(backup_file["kind"], "family")
        e = self.login(evan["id"], "694028")
        self.assertEqual(self.req("POST", "/api/restore", {"file": sealed, "password": "wrong password!"},
                                  {"Cookie": e})[0], 400)                    # wrong password: refused
        s, _, out = self.req("POST", "/api/restore", {"file": sealed, "password": "blue river tank 42"}, {"Cookie": e})
        self.assertEqual((s, json.loads(out)["kind"]), (200, "family"))
        self.assertEqual(profiles.get(evan["id"])["kind"], "family")          # family tools come back
        self.assertIn("Dana's note", self.req("GET", "/api/log", headers={"Cookie": e})[2].decode())
        # a backup made before this fix has no "kind": the profile keeps its own setting
        old = {k: v for k, v in backup_file.items() if k != "kind"}
        old["json"] = dict(old["json"], **{"config.json": {"online": True, "model": "evil"}})   # a doctored plain backup
        before = store.config()
        profiles.set_kind(evan["id"], "soldier")
        self.assertEqual(self.req("POST", "/api/restore", old, {"Cookie": e})[0], 200)
        self.assertEqual(profiles.get(evan["id"])["kind"], "soldier")
        self.assertEqual(store.config(), before)                              # device settings untouched

    def test_13_files_are_encrypted_on_disk_and_only_the_pin_opens_them(self):
        from recruit import vault
        p = profiles.create(f"Fay-{uuid.uuid4().hex[:8]}")
        folder = profiles.folder(p["id"])
        with security.as_profile(p["id"]):
            store.write_lines("log.jsonl", [{"text": "plain before the PIN"}])   # written before any PIN
            self.assertIsNone(security.set_pin("581937"))
        c = self.login(p["id"], "581937")
        self.assertEqual(self.req("POST", "/api/log", {"text": "Fay secret 4471"}, {"Cookie": c})[0], 200)
        raw = (folder / "log.jsonl").read_bytes()
        self.assertTrue(raw.startswith(b"RCV1"))
        self.assertNotIn(b"Fay secret", raw)                                  # nothing readable on disk
        self.assertNotIn(b"plain before", raw)                                # old data sealed too
        self.assertNotIn(b"581937", (folder / "security.json").read_bytes())  # PIN never stored
        log = self.req("GET", "/api/log", headers={"Cookie": c})[2].decode()
        self.assertIn("Fay secret 4471", log)
        self.assertIn("plain before the PIN", log)
        with security.as_profile(p["id"]):                                    # no key: refuses, never "empty"
            with self.assertRaises(vault.VaultError):
                store.read_lines("log.jsonl")

    def test_14_tampered_or_swapped_files_are_refused(self):
        from recruit import vault
        p = profiles.create(f"Gus-{uuid.uuid4().hex[:8]}")
        with security.as_profile(p["id"]):
            self.assertIsNone(security.set_pin("640275"))
        token, _ = security.unlock(p["id"], "640275")
        key = security.session_key(token)
        folder = profiles.folder(p["id"])
        with security.as_profile(p["id"], key):
            store.write_json("profile.json", {"name": "Gus"})
            store.write_lines("log.jsonl", [{"text": "x"}])
            raw = bytearray((folder / "log.jsonl").read_bytes())
            raw[-1] ^= 1                                                      # one flipped bit
            (folder / "log.jsonl").write_bytes(bytes(raw))
            with self.assertRaises(vault.VaultError):
                store.read_lines("log.jsonl")
            (folder / "log.jsonl").write_bytes((folder / "profile.json").read_bytes())   # renamed into place
            with self.assertRaises(vault.VaultError):
                store.read_lines("log.jsonl")

    def test_15_pin_change_keeps_data_and_pin_removal_decrypts(self):
        p = profiles.create(f"Hal-{uuid.uuid4().hex[:8]}")
        folder = profiles.folder(p["id"])
        with security.as_profile(p["id"]):
            self.assertIsNone(security.set_pin("362918"))
        token, _ = security.unlock(p["id"], "362918")
        with security.as_profile(p["id"], security.session_key(token)):
            store.write_lines("log.jsonl", [{"text": "Hal note"}])
            self.assertIsNone(security.set_pin("907153", "362918"))
        self.assertIsNone(security.unlock(p["id"], "362918")[0])              # old PIN no longer opens it
        token, _ = security.unlock(p["id"], "907153")
        with security.as_profile(p["id"], security.session_key(token)):
            self.assertEqual(store.read_lines("log.jsonl")[0]["text"], "Hal note")
            self.assertIsNone(security.remove_pin("907153"))
        self.assertIn(b"Hal note", (folder / "log.jsonl").read_bytes())       # no PIN: plain again
        with security.as_profile(p["id"]):
            self.assertEqual(store.read_lines("log.jsonl")[0]["text"], "Hal note")

    def test_16_profiles_with_a_pin_from_before_encryption_get_encrypted_on_unlock(self):
        import secrets as _secrets
        p = profiles.create(f"Ivy-{uuid.uuid4().hex[:8]}")
        folder = profiles.folder(p["id"])
        with security.as_profile(p["id"]):                                    # as an older Recruit left it:
            store.write_lines("log.jsonl", [{"text": "Ivy legacy"}])          # a PIN hash, plain files
            salt = _secrets.token_bytes(16)
            store.write_json("security.json", {"salt": salt.hex(), "hash": security._hash("517302", salt),
                                               "iterations": security.ITERATIONS})
        self.assertIn(b"Ivy legacy", (folder / "log.jsonl").read_bytes())
        token, _ = security.unlock(p["id"], "517302")
        self.assertTrue((folder / "log.jsonl").read_bytes().startswith(b"RCV1"))
        with security.as_profile(p["id"], security.session_key(token)):
            self.assertEqual(store.read_lines("log.jsonl")[0]["text"], "Ivy legacy")

    def test_17_forgot_pin_recovery_code_keeps_data_encrypted(self):
        s, h, raw = self.req("POST", "/api/profiles/create", {"name": f"Joe-{uuid.uuid4().hex[:8]}", "pin": "742691"})
        r = json.loads(raw)
        code, pid = r["recovery"], r["profile"]["id"]
        self.assertRegex(code, r"^[2-9A-Z]{5}(-[2-9A-Z]{5}){3}$")
        c = h["Set-Cookie"].split(";")[0]
        self.assertEqual(self.req("POST", "/api/log", {"text": "Joe private 9921"}, {"Cookie": c})[0], 200)
        # forgot the PIN: wrong code refused (and counted), right code sets a new PIN with the data intact
        self.assertEqual(self.req("POST", "/api/recover", {"profile": pid, "code": "AAAAA-AAAAA-AAAAA-AAAAA",
                                                             "pin": "385162"})[0], 401)
        s, h, raw = self.req("POST", "/api/recover", {"profile": pid, "code": code.lower().replace("-", " "),
                                                        "pin": "385162"})
        self.assertEqual(s, 200)
        new_code = json.loads(raw)["recovery"]
        self.assertNotEqual(new_code, code)
        c2 = h["Set-Cookie"].split(";")[0]
        self.assertIn("Joe private 9921", self.req("GET", "/api/log", headers={"Cookie": c2})[2].decode())
        self.assertEqual(self.req("GET", "/api/log", headers={"Cookie": c})[0], 401)       # old session ended
        self.assertIsNone(security.unlock(pid, "742691")[0])                                # old PIN gone
        self.assertIsNotNone(security.unlock(pid, "385162")[0])
        self.assertEqual(self.req("POST", "/api/recover", {"profile": pid, "code": code, "pin": "516273"})[0], 401)  # used code
        self.assertTrue((profiles.folder(pid) / "log.jsonl").read_bytes().startswith(b"RCV1"))
        self.assertNotIn(new_code.replace("-", "").encode(), (profiles.folder(pid) / "security.json").read_bytes())

    def test_admin_pin_guards_device_actions(self):
        """Installing an update needs the device admin PIN -- a profile PIN isn't enough."""
        path = security._admin_path()
        path.unlink(missing_ok=True)
        cookie = self.login(self.alice["id"], "482915")
        post = lambda r, b: self.req("POST", r, b, {"Cookie": cookie})
        s, _, raw = post("/api/update", {"zip": "", "sig": "", "admin": "482915"})
        self.assertEqual(s, 403)
        self.assertIn("admin PIN first", json.loads(raw)["error"])
        self.assertEqual(post("/api/admin/pin", {"new": "111111"})[0], 400)                # too easy
        self.assertEqual(post("/api/admin/pin", {"new": "905172"})[0], 200)
        self.assertNotIn(b"905172", path.read_bytes())                                       # stored as a hash only
        self.assertEqual(post("/api/admin/pin", {"new": "604183", "current": "000000"})[0], 400)  # change needs the old one
        self.assertEqual(post("/api/update", {"zip": "", "sig": "", "admin": "482915"})[0], 403)  # profile PIN refused
        self.assertEqual(post("/api/library/reload", {})[0], 403)
        self.assertEqual(post("/api/library/reload", {"admin": "905172"})[0], 200)
        self.assertNotEqual(post("/api/update", {"zip": "", "sig": "", "admin": "905172"})[0], 403)  # passes the PIN gate
        # library-only answers are a device setting: profile PIN refused, admin PIN accepted, shown in status
        self.assertEqual(post("/api/admin/library-only", {"on": True, "admin": "482915"})[0], 403)
        self.assertEqual(post("/api/admin/library-only", {"on": True, "admin": "905172"})[0], 200)
        self.assertTrue(json.loads(self.req("GET", "/api/status", headers={"Cookie": cookie})[2])["library_only"])
        self.assertEqual(post("/api/admin/library-only", {"on": False, "admin": "905172"})[0], 200)
        self.assertFalse(store.config().get("library_only"))
        try:
            for _ in range(5):
                post("/api/update", {"admin": "123987"})
            self.assertIn("Too many", security.check_admin("905172"))                       # throttled even for the right PIN
        finally:
            path.unlink(missing_ok=True)



class IntegrityAndUpdateTests(unittest.TestCase):
    """Library tamper check and signed offline updates (recruit/integrity.py), with a throwaway signing key."""

    def setUp(self):
        import base64
        import tempfile
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from recruit import integrity
        self.integrity, self.b64 = integrity, base64
        self.key = Ed25519PrivateKey.generate()
        self.pub = self.key.public_key()
        self.tmp = Path(tempfile.mkdtemp())

    def sign(self, data: bytes) -> str:
        return self.b64.b64encode(self.key.sign(data)).decode()

    def test_library_tamper_check(self):
        ig, lib = self.integrity, self.tmp / "library"
        lib.mkdir()
        (lib / "AR_1-1_Test.md").write_text("# AR 1-1\n\nOriginal text.\n", encoding="utf-8")
        self.assertEqual(ig.check_library(lib, self.pub)["status"], "unrecorded")
        manifest = ig.write_manifest(lib)
        self.assertEqual(ig.check_library(lib, self.pub)["status"], "ok")
        (lib / "AR_1-1_Test.md").write_text("# AR 1-1\n\nEdited text.\n", encoding="utf-8")
        r = ig.check_library(lib, self.pub)
        self.assertEqual((r["status"], r["changed"]), ("changed", ["AR_1-1_Test.md"]))
        # a signed list: rewriting the fingerprints to match the edit breaks the signature
        (lib / "integrity.json.sig").write_text(self.sign(manifest.read_bytes()))
        ig.write_manifest(lib)
        self.assertEqual(ig.check_library(lib, self.pub)["status"], "bad_signature")

    def _zip(self, version="99.0.0", extra=None) -> bytes:
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("Cursiv-Recruit/recruit/__init__.py", f'__version__ = "{version}"\n')
            z.writestr("Cursiv-Recruit/web/app.js", "// new\n")
            for name, data in (extra or {}).items():
                z.writestr(name, data)
        return buf.getvalue()

    def _root(self) -> Path:
        root = self.tmp / "app"
        (root / "recruit").mkdir(parents=True)
        (root / "recruit" / "__init__.py").write_text('__version__ = "1.0.0"\n')
        return root

    def test_signed_update_installs(self):
        root, data = self._root(), self._zip()
        r = self.integrity.install_update(data, self.sign(data), root, self.pub)
        self.assertEqual((r["version"], r["current"], r["restart"]), ("99.0.0", "1.0.0", True))
        self.assertEqual((root / "web" / "app.js").read_text(), "// new\n")
        self.assertEqual(self.integrity.current_version(root), "99.0.0")

    def test_bad_updates_are_refused(self):
        root, data = self._root(), self._zip()
        cases = {
            "tampered": (data + b"x", self.sign(data)),
            "unsigned": (data, ""),
            "other key": (data, self.b64.b64encode(__import__("cryptography.hazmat.primitives.asymmetric.ed25519",
                          fromlist=["x"]).Ed25519PrivateKey.generate().sign(data)).decode()),
            "downgrade": (self._zip("0.9.0"), self.sign(self._zip("0.9.0"))),
        }
        for name, (z, sig) in cases.items():
            with self.assertRaises(ValueError, msg=name):
                self.integrity.install_update(z, sig, root, self.pub)
        for bad in ({"Cursiv-Recruit/../evil.py": "x"}, {"Cursiv-Recruit/autorun.bat": "x"}, {"elsewhere/a.txt": "x"}):
            z = self._zip(extra=bad)
            with self.assertRaises(ValueError, msg=str(bad)):
                self.integrity.install_update(z, self.sign(z), root, self.pub)
        self.assertEqual(self.integrity.current_version(root), "1.0.0")     # nothing was installed
        self.assertFalse((root / "web").exists())


if __name__ == "__main__":
    unittest.main()
