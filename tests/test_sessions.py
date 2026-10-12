"""Authorization regression tests, part 2 (security review, Phase 8): sessions, replay, deleted profiles, double
submissions, exports and restores. Every request goes straight to the server, as a script on the network would.
"""
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
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
os.environ["CADETFOUNDRY_NO_WARMUP"] = "1"

from cadetfoundry import backup, profiles, security, store, vault  # noqa: E402
from cadetfoundry.server import Handler, serve  # noqa: E402

ADMIN = "905172"                                         # same Class PIN as test_authz (they share a data folder)


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_app = getattr(Handler, "app", None)
        cls.httpd = serve("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        Handler.app.port = cls.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.made_admin = not security.admin_set()
        if cls.made_admin:
            assert security.set_admin_pin(ADMIN) is None
        tag = uuid.uuid4().hex[:6]
        cls.inst = profiles.create(f"Okafor-{tag}", "instructor")
        cls.cadet = profiles.create(f"Ruiz-{tag}", "cadet")
        for p, pin in ((cls.inst, "736281"), (cls.cadet, "482915")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        for p in (cls.inst, cls.cadet):
            profiles.delete(p["id"])
        if cls.made_admin:
            (store.DATA / "admin.json").unlink(missing_ok=True)
        if cls.saved_app is not None:
            Handler.app = cls.saved_app

    def req(self, method, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = {"Host": f"127.0.0.1:{self.port}", "Cookie": cookie, "Content-Type": "application/json"}
        c.request(method, path, body=json.dumps(body if body is not None else {}) if method == "POST" else None, headers=h)
        r = c.getresponse()
        data = r.read()
        ck = (r.getheader("Set-Cookie") or "").split(";")[0]
        ctype = r.getheader("Content-Type") or ""
        c.close()
        try:
            return r.status, (json.loads(data or b"{}") if "json" in ctype else data), ck
        except ValueError:
            return r.status, {}, ck

    def sign_in(self, p, pin, class_pin=False):
        ck = self.req("POST", "/api/unlock", {"profile": p["id"], "pin": pin})[2]
        self.assertTrue(ck)
        if class_pin:
            self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, ck)[0], 200)
        return ck

    def signed_in(self, cookie) -> bool:
        return self.req("GET", "/api/lessons", cookie=cookie)[0] == 200

    # ── sessions ────────────────────────────────────────────────────────────

    def test_signing_out_ends_the_session_for_good(self):
        ck = self.sign_in(self.cadet, "482915")
        self.assertTrue(self.signed_in(ck))
        self.req("POST", "/api/lock", cookie=ck)
        self.assertFalse(self.signed_in(ck))                 # the old cookie, replayed, opens nothing

    def test_made_up_and_malformed_cookies_open_nothing(self):
        for cookie in ("", f"{security.COOKIE}=", f"{security.COOKIE}={uuid.uuid4().hex}", f"{security.COOKIE}=../../x",
                       "x=y; " + f"{security.COOKIE}=" + "A" * 5000, "garbage"):
            with self.subTest(cookie=cookie[:40]):
                self.assertEqual(self.req("GET", "/api/lessons", cookie=cookie)[0], 401)

    def test_an_idle_session_expires(self):
        ck = self.sign_in(self.cadet, "482915")
        token = security.token_from_cookie(ck)
        with security.as_profile(self.cadet["id"]):
            limit = security.idle_minutes() * 60
        security._sessions[token][1] -= limit + 5            # as if nobody touched it for longer than the limit
        self.assertFalse(self.signed_in(ck))
        self.assertNotIn(token, security._sessions)           # and its keys are gone from memory

    def test_changing_a_pin_signs_out_every_other_session(self):
        a, b = self.sign_in(self.cadet, "482915"), self.sign_in(self.cadet, "482915")
        st, r, new = self.req("POST", "/api/pin/set", {"new": "613579", "current": "482915"}, a)
        self.assertEqual(st, 200, r)
        try:
            self.assertFalse(self.signed_in(b))               # e.g. a phone left signed in somewhere
            self.assertTrue(self.signed_in(new))              # the device that changed it stays signed in
            self.assertEqual(self.req("POST", "/api/unlock", {"profile": self.cadet["id"], "pin": "482915"})[0], 401)
        finally:
            self.assertEqual(self.req("POST", "/api/pin/set", {"new": "482915", "current": "613579"}, new)[0], 200)

    def test_a_deleted_profiles_session_stops_working(self):
        gone = profiles.create(f"Gone-{uuid.uuid4().hex[:6]}", "cadet")
        with security.as_profile(gone["id"]):
            assert security.set_pin("358024") is None
        ck = self.sign_in(gone, "358024")
        self.assertEqual(self.req("POST", "/api/profiles/delete", {"pin": "000000"}, ck)[0], 401)   # needs its own PIN
        self.assertTrue(self.signed_in(ck))
        self.assertEqual(self.req("POST", "/api/profiles/delete", {"pin": "358024"}, ck)[0], 200)
        self.assertFalse(self.signed_in(ck))
        self.assertIsNone(profiles.get(gone["id"]))

    def test_knowing_the_class_pin_doesnt_make_a_cadet_an_instructor(self):
        ck = self.sign_in(self.cadet, "482915")
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, ck)[0], 403)
        self.assertIsNone(security.session_program_key(security.token_from_cookie(ck)))
        self.assertEqual(self.req("GET", "/api/instructor/overview", cookie=ck)[0], 403)

    def test_signing_out_closes_class_records_too(self):
        ck = self.sign_in(self.inst, "736281", class_pin=True)
        self.assertEqual(self.req("GET", "/api/instructor/overview", cookie=ck)[0], 200)
        self.req("POST", "/api/lock", cookie=ck)
        self.assertEqual(self.req("GET", "/api/instructor/overview", cookie=ck)[0], 401)
        again = self.sign_in(self.inst, "736281")             # a new sign-in needs the Class PIN again
        self.assertEqual(self.req("GET", "/api/instructor/overview", cookie=again)[0], 403)

    # ── work, exports, restores ─────────────────────────────────────────────

    def test_a_lesson_counts_once_even_when_submitted_at_the_same_moment(self):
        inst = self.sign_in(self.inst, "736281", class_pin=True)
        self.req("POST", "/api/instructor/lesson", {"title": f"Rank {uuid.uuid4().hex[:4]}",
                                                    "questions": "Q: Highest Cadet rank?\n* Cadet Colonel\n- Cadet Major"},
                 inst)
        lessons = self.req("GET", "/api/instructor/lessons", cookie=inst)[1]["lessons"]
        self.req("POST", "/api/instructor/assign-lesson", {"lesson": lessons[-1]["id"], "everyone": False, "units": [],
                                                           "cadets": [self.cadet["id"]], "due": ""}, inst)
        cadet = self.sign_in(self.cadet, "482915")
        mine = self.req("GET", "/api/lessons", cookie=cadet)[1]["assignments"]
        aid = mine[-1]["id"] if isinstance(mine[-1], dict) and "id" in mine[-1] else mine[-1]["a"]
        results = []

        def submit():
            results.append(self.req("POST", "/api/lesson/submit", {"a": aid, "answers": {"0": 0}}, cadet)[0])
        threads = [threading.Thread(target=submit) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count(200), 1, results)       # one counts; the rest are told it's already in
        self.assertEqual(results.count(400), 7, results)

    def test_the_class_report_is_instructor_only(self):
        route = "/api/instructor/report.csv"
        self.assertEqual(self.req("GET", route)[0], 401)
        self.assertEqual(self.req("GET", route, cookie=self.sign_in(self.cadet, "482915"))[0], 403)
        self.assertEqual(self.req("GET", route, cookie=self.sign_in(self.inst, "736281"))[0], 403)   # no Class PIN
        st, body, _ = self.req("GET", route, cookie=self.sign_in(self.inst, "736281", class_pin=True))
        self.assertEqual(st, 200)
        self.assertIsInstance(body, bytes)

    def test_a_personal_backup_cant_forge_grades_or_settings(self):
        """A Cadet controls their own backup file, so restoring one must not write class records or device settings."""
        token = security.token_from_cookie(self.sign_in(self.cadet, "482915"))
        with security.as_profile(self.cadet["id"], security.session_key(token), security.session_class_key(token)):
            before = store.read_json("assignments.json", {})
            crafted = {"cadetfoundry_backup": backup.VERSION, "kind": "instructor",
                       "json": {"assignments.json": {"x": {"state": "complete", "score": 99, "total": 1}},
                                "config.json": {"online_ai": True}, "study.json": {"ok": 1}, "daily.json": 7}}
            out = backup.restore(crafted)
            self.assertEqual(store.read_json("assignments.json", {}), before)
            for name in ("assignments.json", "config.json", "study.json", "daily.json"):
                self.assertNotIn(name, out["restored"])        # not restorable, or the wrong shape
            self.assertNotIn("kind", out)                      # never makes anyone an instructor
        self.assertEqual(profiles.get(self.cadet["id"])["kind"], "cadet")

    def test_one_cadets_damaged_records_dont_break_the_class_views(self):
        """Found by this review: a malformed study.json (e.g. from a hand-made backup) crashed the class overview and
        the class report for everyone."""
        token = security.token_from_cookie(self.sign_in(self.cadet, "482915"))
        ctx = (self.cadet["id"], security.session_key(token), security.session_class_key(token))
        with security.as_profile(*ctx):
            saved = store.read_json("study.json", {})
            store.write_json("study.json", {"q1": 5, "q2": "x", "q3": {"right": True, "last": "soon"}})
        try:
            inst = self.sign_in(self.inst, "736281", class_pin=True)
            st, ov, _ = self.req("GET", "/api/instructor/overview", cookie=inst)
            self.assertEqual(st, 200)
            self.assertIn(self.cadet["id"], [c["id"] for c in ov["cadets"]])
            self.assertEqual(self.req("GET", "/api/instructor/report.csv", cookie=inst)[0], 200)
        finally:
            with security.as_profile(*ctx):
                store.write_json("study.json", saved)


if __name__ == "__main__":
    unittest.main()
