"""Authorization regression tests (security review, Phase 8): every instructor route, every device-wide change.

Routes are found by reading the server's source, so a new /api/instructor/... route is covered automatically. A hidden
button is never an authorization check: each request below goes straight to the server.
"""
import http.client
import json
import os
import re
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
os.environ["CADETFOUNDRY_NO_WARMUP"] = "1"

from cadetfoundry import profiles, security, store, vault  # noqa: E402
from cadetfoundry.server import Handler, serve  # noqa: E402

ADMIN = "905172"
SOURCE = (ROOT / "cadetfoundry" / "server.py").read_text(encoding="utf-8")
INSTRUCTOR_ROUTES = sorted(set(re.findall(r'r == "(/api/instructor/[a-z0-9/_.-]+)"', SOURCE)) - {"/api/instructor/unlock"})
DEVICE_ROUTES = ["/api/admin/ai-mode", "/api/update", "/api/addons/install", "/api/addons/remove-videos", "/api/library/reload"]


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class AuthorizationTests(unittest.TestCase):
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
        cls.inst = profiles.create(f"Rivera-{tag}", "instructor")
        cls.cadet = profiles.create(f"Ellis-{tag}", "cadet")
        cls.other = profiles.create(f"Chen-{tag}", "cadet")
        for p, pin in ((cls.inst, "736281"), (cls.cadet, "482915"), (cls.other, "592047")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        for p in (cls.inst, cls.cadet, cls.other):
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
        c.close()
        try:
            return r.status, json.loads(data or b"{}"), ck
        except ValueError:
            return r.status, {}, ck

    def sign_in(self, p, pin, class_pin=False):
        ck = self.req("POST", "/api/unlock", {"profile": p["id"], "pin": pin})[2]
        self.assertTrue(ck)
        if class_pin:
            self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, ck)[0], 200)
        return ck

    def test_routes_were_found(self):
        self.assertGreater(len(INSTRUCTOR_ROUTES), 25)

    def test_every_instructor_route_refuses_anyone_without_the_class_pin(self):
        cadet = self.sign_in(self.cadet, "482915")
        inst_no_class_pin = self.sign_in(self.inst, "736281")
        for route in INSTRUCTOR_ROUTES:
            for method in ("GET", "POST"):
                with self.subTest(route=route, method=method):
                    self.assertEqual(self.req(method, route)[0], 401)                      # no session
                    self.assertEqual(self.req(method, route, cookie=cadet)[0], 403)        # a Cadet
                    st = self.req(method, route, cookie=inst_no_class_pin)[0]
                    self.assertEqual(st, 403)                                              # no Class PIN yet

    def test_a_cadet_cannot_change_the_device_or_lock_the_instructor_out(self):
        cadet = self.sign_in(self.cadet, "482915")
        for route in DEVICE_ROUTES:
            for _ in range(3):
                with self.subTest(route=route):
                    st, r, _ = self.req("POST", route, {"admin": "000000", "mode": "off", "name": "ai"}, cadet)
                    self.assertEqual(st, 403, r)
        for _ in range(6):                               # the Class PIN change too
            self.assertEqual(self.req("POST", "/api/admin/pin", {"new": "246813", "current": "000000"}, cadet)[0], 403)
        # none of those counted as Class PIN guesses: the instructor still gets in right away
        self.assertIsNone(security.check_admin(ADMIN))
        self.sign_in(self.inst, "736281", class_pin=True)

    def test_the_first_class_pin_is_only_set_on_this_computer(self):
        with mock.patch.object(security, "admin_set", lambda: False), \
                mock.patch.object(Handler, "_local", lambda self: False):
            cadet = self.sign_in(self.cadet, "482915")
            st, r, _ = self.req("POST", "/api/admin/pin", {"new": "246813"}, cadet)
            self.assertEqual(st, 403)

    def test_a_cadet_sees_only_their_own_work(self):
        inst = self.sign_in(self.inst, "736281", class_pin=True)
        self.req("POST", "/api/instructor/lesson", {"title": "Courtesies", "questions": "Q: Who salutes first?\n* Junior\n- Senior"}, inst)
        lesson = self.req("GET", "/api/instructor/lessons", cookie=inst)[1]["lessons"][0]
        r = self.req("POST", "/api/instructor/assign-lesson", {"lesson": lesson["id"], "everyone": False, "units": [],
                                                               "cadets": [self.other["id"]], "due": ""}, inst)[1]
        aid = (r.get("assignment") or r).get("id") or self.req("GET", "/api/instructor/lessons", cookie=inst)[1]["assignments"][0]["id"]
        cadet = self.sign_in(self.cadet, "482915")
        self.assertEqual(self.req("GET", "/api/lessons", cookie=cadet)[1].get("assignments"), [])  # not assigned to them
        st, r, _ = self.req("GET", f"/api/lesson?a={aid}", cookie=cadet)                        # someone else's
        self.assertNotEqual(st, 200)
        st, r, _ = self.req("POST", "/api/lesson/submit", {"a": aid, "answers": {"0": 0}}, cadet)
        self.assertNotEqual(st, 200)
        # the answer key never reaches a Cadet, even the one assigned
        other = self.sign_in(self.other, "592047")
        st, r, _ = self.req("GET", f"/api/lesson?a={aid}", cookie=other)
        self.assertEqual(st, 200)
        self.assertNotIn("answer", json.dumps(r["lesson"]["questions"]))
        self.assertIsNone(r.get("answers"))
        # another Cadet's progress and records are instructor-only
        self.assertEqual(self.req("GET", f"/api/instructor/progress?id={self.other['id']}", cookie=cadet)[0], 403)

    def test_live_answers_are_counts_only_for_everyone(self):
        inst = self.sign_in(self.inst, "736281", class_pin=True)
        st, _, _ = self.req("POST", "/api/instructor/live-quiz", {"action": "start", "q": "2 + 2?", "a": "4",
                                                                  "choices": ["3", "5"], "mode": "mc"}, inst)
        self.assertEqual(st, 200)
        try:
            c1, c2 = self.sign_in(self.cadet, "482915"), self.sign_in(self.other, "592047")
            self.assertEqual(self.req("POST", "/api/live/quiz/answer", {"choice": "4"}, c1)[0], 200)
            seen = self.req("GET", "/api/live/quiz", cookie=c2)[1]
            self.assertFalse(seen.get("answered"))           # c2 doesn't see c1's answer as theirs
            self.assertNotIn(self.cadet["id"], json.dumps(seen))
            mine = self.req("GET", "/api/instructor/live-quiz", cookie=inst)[1]
            self.assertNotIn(self.cadet["id"], json.dumps(mine))   # the instructor sees counts, not who
            self.assertEqual(self.req("POST", "/api/live/quiz/answer", {"choice": "3"}, c1)[0], 400)  # no second answer
        finally:
            self.req("POST", "/api/instructor/live-quiz", {"action": "stop"}, inst)


if __name__ == "__main__":
    unittest.main()
