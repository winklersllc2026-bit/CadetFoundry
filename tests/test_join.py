"""0.2: join codes, "My Cadets", the class Join screen and the 30-second Cadet join.

Each class, platoon and squad has a join code. A Cadet who types it (or scans the class QR code) is placed in that
unit and gets its lessons -- with no instructor clicks -- and the code never opens anything else.
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
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import instructor, profiles, security, store, vault  # noqa: E402
from vanguard.server import serve  # noqa: E402

ADMIN = "905172"


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class JoinCodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = serve("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        cls.httpd.RequestHandlerClass.app.port = cls.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.made_admin = not security.admin_set()
        if cls.made_admin:
            assert security.set_admin_pin(ADMIN) is None
        tag = uuid.uuid4().hex[:6]
        cls.t1 = profiles.create(f"Rivera-{tag}", "instructor")
        cls.t2 = profiles.create(f"Okafor-{tag}", "instructor")
        for p, pin in ((cls.t1, "736281"), (cls.t2, "638192")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None
        cls.made = [cls.t1, cls.t2]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        for p in cls.made:
            profiles.delete(p["id"])
        if cls.made_admin:
            (store.DATA / "admin.json").unlink(missing_ok=True)

    def req(self, method, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Host": f"127.0.0.1:{self.port}", "Cookie": cookie}
        if body is not None:
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        cookie_out = (r.getheader("Set-Cookie") or "").split(";")[0]
        c.close()
        try:
            return r.status, json.loads(data or b"{}"), cookie_out
        except ValueError:
            return r.status, data, cookie_out

    def instructor(self, p, pin):
        _, _, ck = self.req("POST", "/api/unlock", {"profile": p["id"], "pin": pin})
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, ck)[0], 200)
        return ck

    def new_cadet(self, join=""):
        name = f"Cadet {uuid.uuid4().hex[:6]}"
        st, r, ck = self.req("POST", "/api/profiles/create", {"name": name, "pin": "482915", "kind": "cadet", "join": join})
        if r.get("ok"):
            self.made.append(r["profile"])
        return st, r, ck

    def test_a_cadet_joins_a_unit_with_its_code_and_gets_its_lessons(self):
        t1 = self.instructor(self.t1, "736281")
        st, unit, _ = self.req("POST", "/api/instructor/unit", {"action": "add", "name": "Alpha Platoon", "kind": "platoon"}, t1)
        self.assertEqual(st, 200)
        code = unit["code"]
        self.assertEqual(len(code), instructor.JOIN_LEN)
        self.assertTrue(set(code) <= set(instructor.JOIN_ALPHABET))
        self.assertEqual(unit["owner"], self.t1["id"])                   # the instructor who made it teaches it
        # a lesson for the platoon before anyone is in it
        _, lesson, _ = self.req("POST", "/api/instructor/lesson", {"title": "Drill basics", "content": "Attention."}, t1)
        self.assertEqual(self.req("POST", "/api/instructor/assign-lesson", {"lesson": lesson["id"], "units": [unit["id"]]}, t1)[0], 200)

        # anyone can see which unit a code joins (for the signup form) -- and nothing else
        st, r, _ = self.req("GET", "/api/join-code?c=" + code.lower())
        self.assertEqual((st, r), (200, {"name": "Alpha Platoon"}))
        self.assertEqual(self.req("GET", "/api/join-code?c=ZZZZZZ")[1], {})

        # a wrong code refuses the profile (nothing is made); the right one, typed any way, works
        st, r, _ = self.new_cadet("WRONG1")
        self.assertEqual(st, 400)
        self.assertIn("join code", r["error"])
        st, r, cadet = self.new_cadet(f" {code[:3].lower()}-{code[3:]} ")
        self.assertEqual(st, 200, r)
        self.assertEqual(r["joined"], "Alpha Platoon")
        pid = r["profile"]["id"]
        # the unit's lesson is there right away, before the instructor opens anything
        mine = self.req("GET", "/api/lessons", cookie=cadet)[1]["assignments"]
        self.assertEqual([a["title"] for a in mine], ["Drill basics"])
        self.assertEqual(self.req("GET", "/api/lock", cookie=cadet)[1]["current"]["joined"], "Alpha Platoon")
        # the Cadet still can't reach anything of the instructor's
        self.assertEqual(self.req("GET", "/api/instructor/overview", cookie=cadet)[0], 403)

        # the instructor's roster files the join; "My Cadets" is this instructor's units only
        ov = self.req("GET", "/api/instructor/overview", cookie=t1)[1]
        self.assertEqual(next(c for c in ov["cadets"] if c["id"] == pid)["unit"], unit["id"])
        self.assertEqual(ov["me"], self.t1["id"])
        self.assertIn(pid, [x["id"] for x in self.req("GET", "/api/instructor/dashboard?unit=mine", cookie=t1)[1]["rows"]])
        t2 = self.instructor(self.t2, "638192")
        self.assertNotIn(pid, [x["id"] for x in self.req("GET", "/api/instructor/dashboard?unit=mine", cookie=t2)[1]["rows"]])
        self.assertIn(pid, [x["id"] for x in self.req("GET", "/api/instructor/dashboard", cookie=t2)[1]["rows"]])
        # handing the unit to the other instructor moves it to their "My Cadets"
        self.assertEqual(self.req("POST", "/api/instructor/unit", {"action": "owner", "id": unit["id"], "owner": self.t2["id"]}, t1)[0], 200)
        self.assertIn(pid, [x["id"] for x in self.req("GET", "/api/instructor/dashboard?unit=mine", cookie=t2)[1]["rows"]])

        # a new code: the old one stops working
        st, r, _ = self.req("POST", "/api/instructor/unit", {"action": "code", "id": unit["id"]}, t1)
        self.assertNotEqual(r["code"], code)
        self.assertEqual(self.req("GET", "/api/join-code?c=" + code)[1], {})
        self.assertEqual(self.new_cadet(code)[0], 400)
        # removing the unit removes its code
        self.req("POST", "/api/instructor/unit", {"action": "delete", "id": unit["id"]}, t1)
        self.assertEqual(self.req("GET", "/api/join-code?c=" + r["code"])[1], {})

    def test_a_signed_in_cadet_joins_from_me_and_codes_are_for_cadets_only(self):
        t1 = self.instructor(self.t1, "736281")
        unit = self.req("POST", "/api/instructor/unit", {"action": "add", "name": "Bravo", "kind": "class"}, t1)[1]
        _, r, cadet = self.new_cadet()
        self.assertEqual(r["joined"], "")
        self.assertEqual(self.req("POST", "/api/join", {"code": "nope"}, cadet)[0], 400)
        st, r, _ = self.req("POST", "/api/join", {"code": unit["code"]}, cadet)
        self.assertEqual((st, r["joined"]), (200, "Bravo"))
        self.assertEqual(self.req("POST", "/api/join", {"code": unit["code"]}, t1)[0], 400)        # not for instructors

    def test_join_screen_is_public_and_shows_codes_only_to_an_open_instructor(self):
        st, page, _ = self.req("GET", "/join")
        self.assertEqual(st, 200)
        self.assertIn(b"/js/qr.js", page)
        self.assertEqual(self.req("GET", "/js/qr.js")[0], 200)
        st, c, _ = self.req("GET", "/api/classroom")
        self.assertEqual(st, 200)
        self.assertFalse(c["lan"])                     # this test server is this computer only
        self.assertNotIn("units", c)                   # no codes without an instructor's open class
        t1 = self.instructor(self.t1, "736281")
        self.req("POST", "/api/instructor/unit", {"action": "add", "name": "Charlie", "kind": "squad"}, t1)
        units = self.req("GET", "/api/classroom", cookie=t1)[1]["units"]
        self.assertTrue(units and all(set(u) == {"id", "name", "code"} for u in units))

    def test_phones_cant_make_profiles_before_the_instructor_sets_up(self):
        """The instructor's laptop is the first device: until a Class PIN exists, other devices can't sign up."""
        from unittest import mock
        from vanguard.server import Handler
        with mock.patch.object(Handler, "_local", lambda self: False),                 mock.patch.object(security, "admin_set", lambda: False):
            st, r, _ = self.new_cadet()
            self.assertEqual(st, 403)
            self.assertIn("instructor", r["error"])
            st, r, _ = self.req("POST", "/api/profiles/create", {"name": "Sneaky", "pin": "482915", "kind": "instructor",
                                                                "admin": "111222"})
            self.assertEqual(st, 403)                     # nor claim the Class PIN from a phone


class QrTests(unittest.TestCase):
    def test_qr_maker_draws_a_valid_symbol(self):
        """Structure checks (decoding with a real reader was done when it was written: versions 1-10 all scan)."""
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node isn't installed")
        js = ("const QR = require(" + json.dumps(str(ROOT / "web" / "js" / "qr.js")) + ");"
              "process.stdout.write(JSON.stringify(['http://192.168.1.23:8780/?join=K7M2QD', 'x'.repeat(150)]"
              ".map(t => QR.make(t).map(r => r.map(c => c ? 1 : 0)))));")
        for m in json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout):
            n = len(m)
            self.assertEqual((n - 17) % 4, 0)
            for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):           # the three finder patterns
                self.assertEqual([m[r0][c0 + i] for i in range(7)], [1] * 7)
                self.assertEqual([m[r0 + 2][c0 + i] for i in range(7)], [1, 0, 1, 1, 1, 0, 1])
            self.assertEqual([m[6][i] for i in range(8, n - 8)], [(i + 1) % 2 for i in range(n - 16)])   # timing
            self.assertEqual(m[n - 8][8], 1)                                # the dark module


if __name__ == "__main__":
    unittest.main()
