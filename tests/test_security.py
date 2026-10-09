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
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import profiles, security, store  # noqa: E402
from vanguard.server import serve  # noqa: E402


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
        routes = sorted(set(re.findall(r'if r == "(/api/[^"]+)"', (ROOT / "vanguard" / "server.py").read_text())))
        self.assertGreater(len(routes), 40)
        skip = {"/api/quit", "/api/chat", "/api/simplify", "/api/voice", "/api/lock", "/api/profiles/delete", "/api/pin/remove",
                "/api/history/clear", "/api/library/reload", "/api/restore", "/api/update"}      # slow, or ends the session
        cookie = self.login(self.alice["id"], "482915")
        # Routes like letter drafts and the mock board call the AI. On a machine with a real model installed that
        # can take longer than the request timeout, so the test sometimes failed; here the AI answers "no model".
        from unittest import mock
        no_ai = RuntimeError("no AI model in this test")
        with mock.patch("vanguard.engine.stream", side_effect=no_ai), mock.patch("vanguard.engine.quick", return_value=""):
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
        s, _, _ = self.req("POST", "/api/restore", '{"vanguard_backup":1}', {"Content-Type": "text/plain"})
        self.assertEqual(s, 415)

    def test_4_preflight_refused(self):
        s, h, _ = self.req("OPTIONS", "/api/log")
        self.assertEqual(s, 405)
        self.assertNotIn("Access-Control-Allow-Origin", h)

    def test_5_path_traversal_refused(self):
        cookie = self.login(self.alice["id"], "482915")
        for p in ("/../vanguard/store.py", "/..%2fvanguard%2fstore.py", "/%2e%2e/run.py", "/web/../run.py"):
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
        self.assertEqual(self.req("GET", "/api/log", headers={"Cookie": "vanguard_session=forged"})[0], 401)
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
        self.assertTrue(sealed["vanguard_backup_sealed"])
        self.assertNotIn("Dana", json.dumps(sealed))                        # nothing readable in the file
        from vanguard import backup as _backup
        backup_file = _backup.open_any(sealed, "blue river tank 42")
        self.assertEqual(backup_file["kind"], "guardian")
        e = self.login(evan["id"], "694028")
        self.assertEqual(self.req("POST", "/api/restore", {"file": sealed, "password": "wrong password!"},
                                  {"Cookie": e})[0], 400)                    # wrong password: refused
        s, _, out = self.req("POST", "/api/restore", {"file": sealed, "password": "blue river tank 42"}, {"Cookie": e})
        self.assertEqual((s, json.loads(out)["kind"]), (200, "guardian"))
        self.assertEqual(profiles.get(evan["id"])["kind"], "guardian")          # family tools come back
        self.assertIn("Dana's note", self.req("GET", "/api/log", headers={"Cookie": e})[2].decode())
        # a backup made before this fix has no "kind": the profile keeps its own setting
        old = {k: v for k, v in backup_file.items() if k != "kind"}
        old["json"] = dict(old["json"], **{"config.json": {"online": True, "model": "evil"}})   # a doctored plain backup
        before = store.config()
        profiles.set_kind(evan["id"], "cadet")
        self.assertEqual(self.req("POST", "/api/restore", old, {"Cookie": e})[0], 200)
        self.assertEqual(profiles.get(evan["id"])["kind"], "cadet")
        self.assertEqual(store.config(), before)                              # device settings untouched

    def test_13_files_are_encrypted_on_disk_and_only_the_pin_opens_them(self):
        from vanguard import vault
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
        from vanguard import vault
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
        with security.as_profile(p["id"]):                                    # as an older Vanguard left it:
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
        self.assertIn("Instructor PIN first", json.loads(raw)["error"])
        self.assertEqual(post("/api/admin/pin", {"new": "111111"})[0], 400)                # too easy
        self.assertEqual(post("/api/admin/pin", {"new": "905172"})[0], 200)
        self.assertNotIn(b"905172", path.read_bytes())                                       # stored as a hash only
        self.assertEqual(post("/api/admin/pin", {"new": "604183", "current": "000000"})[0], 400)  # change needs the old one
        self.assertEqual(post("/api/update", {"zip": "", "sig": "", "admin": "482915"})[0], 403)  # profile PIN refused
        self.assertEqual(post("/api/library/reload", {})[0], 403)
        self.assertEqual(post("/api/library/reload", {"admin": "905172"})[0], 200)
        self.assertNotEqual(post("/api/update", {"zip": "", "sig": "", "admin": "905172"})[0], 403)  # passes the PIN gate
        # the AI mode is an instructor setting: profile PIN refused, Instructor PIN accepted, shown in status
        self.assertEqual(store.ai_mode(), "library")                                         # default
        self.assertEqual(post("/api/admin/ai-mode", {"mode": "off", "admin": "482915"})[0], 403)
        self.assertEqual(post("/api/admin/ai-mode", {"mode": "sideways", "admin": "905172"})[0], 400)
        self.assertEqual(post("/api/admin/ai-mode", {"mode": "off", "admin": "905172"})[0], 200)
        self.assertEqual(json.loads(self.req("GET", "/api/status", headers={"Cookie": cookie})[2])["ai_mode"], "off")
        self.assertEqual(post("/api/admin/ai-mode", {"mode": "library", "admin": "905172"})[0], 200)
        self.assertEqual(store.ai_mode(), "library")
        try:
            for _ in range(5):
                post("/api/update", {"admin": "123987"})
            self.assertIn("Too many", security.check_admin("905172"))                       # throttled even for the right PIN
        finally:
            path.unlink(missing_ok=True)

    def test_first_instructor_sets_the_instructor_pin_on_this_computer(self):
        """A brand-new device: the first instructor profile chooses the Instructor PIN (from the laptop itself)."""
        from unittest import mock
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(store, "DATA", tmp), mock.patch.object(profiles, "ROOT", tmp / "profiles"):
            lock = json.loads(self.req("GET", "/api/lock")[2])
            self.assertFalse(lock["admin_set"])
            self.assertTrue(lock["on_this_computer"])
            s, _, raw = self.req("POST", "/api/profiles/create", {"name": "Ms. First", "kind": "instructor",
                                                                  "pin": "736281", "admin": "123"})
            self.assertEqual(s, 403)                                            # too short: nothing created
            self.assertEqual(profiles.all_profiles(), [])
            s, _, raw = self.req("POST", "/api/profiles/create", {"name": "Ms. First", "kind": "instructor",
                                                                  "pin": "736281", "admin": "905172"})
            self.assertEqual(s, 200, raw)
            self.assertIsNone(security.check_admin("905172"))
            self.assertIsNotNone(security.program_public())
            s, _, raw = self.req("POST", "/api/profiles/create", {"name": "Mr. Second", "kind": "instructor",
                                                                  "pin": "573920", "admin": "111222"})
            self.assertEqual(s, 403)                                            # now the PIN must match

    def test_basic_training_cards_only_for_cadets_who_plan_to_join(self):
        """Owner's rule: the adult-Soldier study guide (UCMJ, SHARP, weapons, BCT/AIT...) shows only for a Cadet who
        says they plan to join the military -- and only if the instructor hasn't turned it off."""
        alice = self.login(self.alice["id"], "482915")
        get = lambda path: self.req("GET", path, headers={"Cookie": alice})
        cats = lambda: {c["category"] for t in json.loads(get("/api/topics")[2]) for c in t["cards"]}
        self.addCleanup(store.save_config, {"categories": list(store.ALL_CATEGORIES)})
        with security.as_profile(self.alice["id"], security.session_key(alice.split("=")[1]),
                                 security.session_class_key(alice.split("=")[1])):
            store.save_profile({"military_track": ""})
        self.assertNotIn("basic", cats())
        self.assertEqual(get("/api/card?id=ucmj_basics")[0], 404)
        quiz = json.loads(get("/api/quiz?n=50")[2])
        self.assertFalse(any("UCMJ" in x["card"] for x in (quiz if isinstance(quiz, list) else quiz.get("cards", []))))
        self.assertNotIn("basic", json.loads(get("/api/status")[2])["categories"])
        # the Cadet opts in from their own profile
        s, _, _ = self.req("POST", "/api/profile", {"military_track": "yes"}, {"Cookie": alice})
        self.assertEqual(s, 200)
        self.assertIn("basic", cats())
        self.assertEqual(get("/api/card?id=ucmj_basics")[0], 200)
        # the instructor can turn categories off for everyone; a Cadet can't change that setting
        self.assertEqual(self.req("POST", "/api/instructor/categories", {"categories": ["leadership"]}, {"Cookie": alice})[0], 403)
        store.save_config({"categories": ["leadership", "citizenship", "health", "careers", "explore"]})
        self.assertFalse(cats() & {"basic", "military"})
        self.assertEqual(get("/api/card?id=ucmj_basics")[0], 404)
        self.req("POST", "/api/profile", {"military_track": ""}, {"Cookie": alice})

    def test_app_can_be_installed_from_the_lock_screen(self):
        """Phones 'Add to Home Screen' and computers 'Install app' before anyone signs in: the manifest and icons are
        public (they hold no data); everything else stays locked."""
        s, h, raw = self.req("GET", "/manifest.webmanifest")
        self.assertEqual(s, 200)
        self.assertIn("manifest+json", h.get("Content-Type", ""))
        self.assertEqual(json.loads(raw)["display"], "standalone")
        for icon in ("/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png"):
            s, h, raw = self.req("GET", icon)
            self.assertEqual((s, h.get("Content-Type"), raw[:4]), (200, "image/png", b"\x89PNG"), icon)
        self.assertEqual(self.req("GET", "/api/status")[0], 401)

    def test_instructor_routes_need_an_instructor_profile_and_the_instructor_pin(self):
        """Spec §47: a Cadet can never reach instructor data, other Cadets' records or program settings."""
        if not security.admin_set():
            self.assertIsNone(security.set_admin_pin("905172"))
            self.addCleanup((store.DATA / "admin.json").unlink, missing_ok=True)
        admin = "905172"
        alice = self.login(self.alice["id"], "482915")                      # a Cadet
        get = lambda path, cookie: self.req("GET", path, headers={"Cookie": cookie})
        post = lambda path, body, cookie: self.req("POST", path, body, {"Cookie": cookie})
        # a Cadet -- even one who knows the Instructor PIN -- gets nothing
        self.assertEqual(get("/api/instructor/overview", alice)[0], 403)
        self.assertEqual(get(f"/api/instructor/cadet?id={self.bob['id']}", alice)[0], 403)
        self.assertEqual(post("/api/instructor/unit", {"action": "add", "name": "Alpha"}, alice)[0], 403)
        self.assertEqual(post("/api/instructor/unlock", {"admin": admin}, alice)[0], 403)
        self.assertEqual(get("/api/instructor/overview", alice)[0], 403)
        # an instructor profile can only be created with the Instructor PIN
        name = f"Instr-{uuid.uuid4().hex[:6]}"
        s, _, raw = post("/api/profiles/create", {"name": name, "kind": "instructor", "pin": "736281"}, alice)
        self.assertEqual(s, 403)
        s, _, raw = post("/api/profiles/create", {"name": name, "kind": "instructor", "pin": "736281", "admin": admin}, alice)
        self.assertEqual(s, 200, raw)
        inst = next(p for p in profiles.all_profiles() if p["name"] == name)
        self.addCleanup(profiles.delete, inst["id"])
        self.assertEqual(inst["kind"], "instructor")
        teacher = self.login(inst["id"], "736281")
        # the instructor's own PIN isn't enough: class records need the Instructor PIN this session
        self.assertEqual(get("/api/instructor/overview", teacher)[0], 403)
        self.assertEqual(post("/api/instructor/unlock", {"admin": "000000"}, teacher)[0], 403)
        self.assertEqual(post("/api/instructor/unlock", {"admin": admin}, teacher)[0], 200)
        s, _, raw = get("/api/instructor/overview", teacher)
        self.assertEqual(s, 200)
        ov = json.loads(raw)
        self.assertIn(self.alice["id"], [c["id"] for c in ov["cadets"]])
        self.assertNotIn(inst["id"], [c["id"] for c in ov["cadets"]])     # instructors aren't Cadets
        s, _, raw = post("/api/instructor/unit", {"action": "add", "name": "Alpha Platoon", "kind": "platoon"}, teacher)
        self.assertEqual(s, 200)
        unit = json.loads(raw)["id"]
        self.assertEqual(post("/api/instructor/assign", {"cadet": self.alice["id"], "unit": unit, "let": 2}, teacher)[0], 200)
        self.assertEqual(post("/api/instructor/assign", {"cadet": self.alice["id"], "let": 9}, teacher)[0], 400)
        self.assertEqual(post("/api/instructor/assign", {"cadet": inst["id"], "let": 1}, teacher)[0], 400)
        s, _, raw = get(f"/api/instructor/cadet?id={self.alice['id']}", teacher)
        self.assertEqual(s, 200)
        rec = json.loads(raw)
        self.assertEqual(rec["status"], "shared")                         # Alice signed in after the program key
        self.assertTrue(set(rec) <= {"status", "questions_practiced", "questions_known", "last_study", "exams", "scenarios"})
        # the roster is sealed: reading the file off the disk shows only ciphertext
        self.assertNotIn(b"Alpha Platoon", (store.DATA / "program" / "roster.json").read_bytes())
        # signing out drops the program key with the session
        self.req("POST", "/api/lock", {}, {"Cookie": teacher})
        self.assertNotEqual(get("/api/instructor/overview", teacher)[0], 200)


class IntegrityAndUpdateTests(unittest.TestCase):
    """Library tamper check and signed offline updates (vanguard/integrity.py), with a throwaway signing key."""

    def setUp(self):
        import base64
        import tempfile
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from vanguard import integrity
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
            z.writestr("Vanguard/vanguard/__init__.py", f'__version__ = "{version}"\n')
            z.writestr("Vanguard/web/app.js", "// new\n")
            for name, data in (extra or {}).items():
                z.writestr(name, data)
        return buf.getvalue()

    def _root(self) -> Path:
        root = self.tmp / "app"
        (root / "vanguard").mkdir(parents=True)
        (root / "vanguard" / "__init__.py").write_text('__version__ = "1.0.0"\n')
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
        for bad in ({"Vanguard/../evil.py": "x"}, {"Vanguard/autorun.bat": "x"}, {"elsewhere/a.txt": "x"}):
            z = self._zip(extra=bad)
            with self.assertRaises(ValueError, msg=str(bad)):
                self.integrity.install_update(z, self.sign(z), root, self.pub)
        self.assertEqual(self.integrity.current_version(root), "1.0.0")     # nothing was installed
        self.assertFalse((root / "web").exists())


if __name__ == "__main__":
    unittest.main()
