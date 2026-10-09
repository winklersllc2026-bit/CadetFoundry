"""Phase 10: pilot setup, snapshots, anonymous Cadet survey, instructor feedback, the pilot report."""
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

from vanguard import profiles, security, store, vault  # noqa: E402
from vanguard.server import serve  # noqa: E402

ADMIN = "905172"
PILOT_FILES = ("pilot.json", "pilot_snapshots.json", "feedback_cadets.json", "feedback_instructor.json")


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class PilotTests(unittest.TestCase):
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
        cls.a = profiles.create(f"Nia-{tag}")
        cls.t = profiles.create(f"Sfc-{tag}", "instructor")
        for p, pin in ((cls.a, "482915"), (cls.t, "736281")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None
        cls.saved = {n: (store.DATA / "program" / n).read_bytes() for n in PILOT_FILES if (store.DATA / "program" / n).exists()}

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        for n in PILOT_FILES:                                     # leave the shared test data as it was
            path = store.DATA / "program" / n
            if n in cls.saved:
                path.write_bytes(cls.saved[n])
            else:
                path.unlink(missing_ok=True)
        for p in (cls.a, cls.t):
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
        c.close()
        return r.status, json.loads(data or b"{}")

    def login(self, pid, pin):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/api/unlock", body=json.dumps({"profile": pid, "pin": pin}),
                  headers={"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"})
        r = c.getresponse()
        r.read()
        c.close()
        return r.getheader("Set-Cookie").split(";")[0]

    def test_pilot_from_setup_to_report(self):
        nia, sfc = self.login(self.a["id"], "482915"), self.login(self.t["id"], "736281")
        for path in ("/api/instructor/pilot", "/api/instructor/pilot/snapshot", "/api/instructor/pilot/survey",
                     "/api/instructor/pilot/feedback"):
            self.assertEqual(self.req("POST", path, {}, nia)[0], 403)
        self.assertEqual(self.req("GET", "/api/instructor/pilot", cookie=nia)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, sfc)[0], 200)
        # setup: dates are checked
        self.assertEqual(self.req("POST", "/api/instructor/pilot", {"start": "2026-10-20", "end": "2026-10-01"}, sfc)[0], 400)
        s, cfg = self.req("POST", "/api/instructor/pilot", {"school": "Central High", "instructor": "SFC Ruiz", "start": "2026-09-01",
                                                            "end": "2026-11-10", "cadets_planned": "37", "metrics": ["lessons", "service"]}, sfc)
        self.assertEqual((s, cfg["program"], cfg["metrics"]), (200, "Army JROTC", ["lessons", "service"]))
        # a baseline snapshot, then activity, then the report shows the change
        self.assertEqual(self.req("POST", "/api/instructor/pilot/snapshot", {}, sfc)[0], 200)
        # the survey is closed until the instructor opens it
        self.assertFalse(self.req("GET", "/api/pilot/survey", cookie=nia)[1]["open"])
        answers = {"learn": 4, "lead": 5, "progress": 3, "easy": 4, "again": 5}
        self.assertEqual(self.req("POST", "/api/pilot/survey", {"answers": answers}, nia)[0], 400)
        self.req("POST", "/api/instructor/pilot/survey", {"open": True}, sfc)
        self.assertEqual(self.req("POST", "/api/pilot/survey", {"answers": {**answers, "easy": 9}}, nia)[0], 400)
        self.assertEqual(self.req("POST", "/api/pilot/survey", {"answers": answers, "comment": "More scenarios please"}, nia)[0], 200)
        self.assertEqual(self.req("POST", "/api/pilot/survey", {"answers": answers}, nia)[0], 400)      # once only
        self.assertTrue(self.req("GET", "/api/pilot/survey", cookie=nia)[1]["done"])
        # anonymous: no name or id is stored with the answers
        raw = (store.DATA / "program" / "feedback_cadets.json").read_text(encoding="utf-8")
        self.assertNotIn(self.a["id"], raw)
        self.assertNotIn(self.a["name"], raw)
        # instructor feedback, including the spec's key question
        self.assertEqual(self.req("POST", "/api/instructor/pilot/feedback", {"satisfaction": 4, "use_again": "sure"}, sfc)[0], 400)
        s, fb = self.req("POST", "/api/instructor/pilot/feedback", {"satisfaction": 4, "minutes_saved": "45", "use_again": "yes",
                                                                    "comment": "Grading time went down."}, sfc)
        self.assertEqual(s, 200)
        s, rep = self.req("GET", "/api/instructor/pilot", cookie=sfc)
        self.assertEqual(s, 200)
        self.assertEqual(rep["config"]["school"], "Central High")
        self.assertIsNotNone(rep["baseline"])
        self.assertGreaterEqual(rep["feedback"]["cadet_responses"], 1)
        self.assertIn("More scenarios please", rep["feedback"]["cadet_comments"])
        self.assertEqual(rep["feedback"]["latest_instructor"]["use_again"], "yes")
        self.assertIsNotNone(rep["weeks"])


if __name__ == "__main__":
    unittest.main()
