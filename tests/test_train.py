"""Phase 6: Train -- personal improvement, not pass/fail."""
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

from vanguard import profiles, security, store, train, vault  # noqa: E402
from vanguard.server import serve  # noqa: E402

ADMIN = "905172"
PUSH = {"id": "pushups", "name": "Push-ups", "unit": "reps", "better": "higher"}
MILE = {"id": "mile", "name": "One-mile run", "unit": "time", "better": "lower"}


def rows(eid, *pairs):
    return [{"id": f"r{i}", "event": eid, "date": d, "value": v} for i, (d, v) in enumerate(pairs)]


class TrainMathTests(unittest.TestCase):
    def test_values(self):
        self.assertEqual(train.parse_value("time", "8:30"), 510)
        self.assertEqual(train.parse_value("time", "1:02:05"), 3725)
        self.assertEqual(train.parse_value("time", "95"), 95)
        self.assertEqual(train.show_value("time", 510), "8:30")
        self.assertEqual(train.parse_value("reps", "25"), 25)
        for unit, bad in (("time", "8:75"), ("time", "abc"), ("reps", "-3"), ("reps", "lots")):
            with self.assertRaises(ValueError):
                train.parse_value(unit, bad)

    def test_spec_example_pushups(self):
        # spec §12: January 21, February 25, March 29 -> improvement +8
        s = train.stats(PUSH, rows("pushups", ("2026-01-10", 21), ("2026-02-10", 25), ("2026-03-10", 29)))
        self.assertEqual((s["first"], s["previous"], s["latest"], s["best"], s["improvement_shown"]), ("21", "25", "29", "29", "+8"))
        self.assertEqual(s["improvement_pct"], 38)
        self.assertTrue(s["latest_is_best"])

    def test_lower_is_better_counts_as_improvement(self):
        s = train.stats(MILE, rows("mile", ("2026-09-01", 540), ("2026-10-01", 510)), {"target": 480})
        self.assertEqual((s["improvement_shown"], s["best"], s["goal"], s["goal_reached"]), ("+0:30", "8:30", "8:00", False))
        worse = train.stats(MILE, rows("mile", ("2026-09-01", 510), ("2026-10-01", 540)))
        self.assertEqual(worse["improvement_shown"], "−0:30")
        self.assertEqual(worse["best"], "8:30")

    def test_no_pass_fail_language(self):
        s = train.stats(PUSH, rows("pushups", ("2026-01-10", 21), ("2026-02-10", 18)))
        self.assertNotRegex(json.dumps(s).lower(), r"\b(pass|fail|failed|passing|failing)\b")

    def test_suggested_events_until_the_instructor_chooses(self):
        from unittest import mock
        with mock.patch.object(store, "DATA", Path(tempfile.mkdtemp())):             # a program with no events yet
            evs = train.events()
            self.assertEqual([e["id"] for e in evs], [e["id"] for e in train.SUGGESTED])
            self.assertTrue(all(e["suggested"] for e in evs))
            train.add_event("Shuttle run", "time", "lower")                          # the instructor's choice wins
            self.assertFalse(any(e.get("suggested") for e in train.events()))
            self.assertIn("Shuttle run", [e["name"] for e in train.events()])


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class TrainFlowTests(unittest.TestCase):
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
        cls.a, cls.b = profiles.create(f"Al-{tag}"), profiles.create(f"Bea-{tag}")
        cls.t = profiles.create(f"Coach-{tag}", "instructor")
        for p, pin in ((cls.a, "482915"), (cls.b, "573920"), (cls.t, "736281")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        for p in (cls.a, cls.b, cls.t):
            profiles.delete(p["id"])
        if cls.made_admin:
            (store.DATA / "admin.json").unlink(missing_ok=True)

    def req(self, method, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
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

    def test_cadet_and_instructor_flow(self):
        al, bea, coach = self.login(self.a["id"], "482915"), self.login(self.b["id"], "573920"), self.login(self.t["id"], "736281")
        # Cadets can't touch instructor fitness routes
        self.assertEqual(self.req("GET", "/api/instructor/train", cookie=al)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/train/event", {"name": "x", "unit": "reps", "better": "higher"}, al)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/train/record", {"event": "pushups", "results": {self.b["id"]: "99"}}, al)[0], 403)
        # a Cadet logs results and a goal
        ev = self.req("GET", "/api/train", cookie=al)[1]["events"][0]["event"]
        self.assertEqual(self.req("POST", "/api/train/add", {"event": ev, "value": "20", "date": "2026-09-01"}, al)[0], 200)
        self.assertEqual(self.req("POST", "/api/train/add", {"event": ev, "value": "lots"}, al)[0], 400)
        self.assertEqual(self.req("POST", "/api/train/add", {"event": ev, "value": "20", "date": "2999-01-01"}, al)[0], 400)
        s, mine = self.req("POST", "/api/train/goal", {"event": ev, "target": "30"}, al)
        self.assertEqual(s, 200)
        self.assertTrue(vault.is_sealed((profiles.folder(self.a["id"]) / "fitness.jsonl").read_bytes()))
        self.assertEqual(self.req("GET", "/api/train", cookie=bea)[1]["events"][0]["count"], 0)       # only your own
        # test day: the instructor records results for both Cadets
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, coach)[0], 200)
        s, out = self.req("POST", "/api/instructor/train/record", {"event": ev, "date": "2026-10-01",
                                                                   "results": {self.a["id"]: "26", self.b["id"]: "15",
                                                                               self.t["id"]: "50"}}, coach)
        self.assertEqual(s, 200)
        self.assertEqual(sorted(out["saved"]), sorted([self.a["id"], self.b["id"]]))
        self.assertIn(self.t["id"], out["errors"])                                         # instructors aren't Cadets
        st = next(e for e in self.req("GET", "/api/train", cookie=al)[1]["events"] if e["event"] == ev)
        self.assertEqual((st["first"], st["latest"], st["improvement_shown"], st["goal"]), ("20", "26", "+6", "30"))
        # a Cadet can't delete what the instructor recorded, only their own entries
        by_teacher = next(h for h in st["history"] if h["by"] == "instructor")["id"]
        own = next(h for h in st["history"] if h["by"] == "self")["id"]
        self.assertEqual(self.req("POST", "/api/train/delete", {"id": by_teacher}, al)[0], 404)
        self.assertEqual(self.req("POST", "/api/train/delete", {"id": own}, al)[0], 200)
        # the instructor sees each Cadet's improvement
        ov = self.req("GET", "/api/instructor/train", cookie=coach)[1]
        bea_ev = next(c for c in ov["cadets"] if c["id"] == self.b["id"])["events"]
        self.assertEqual(next(e for e in bea_ev if e["event"] == ev)["latest"], "15")
        # the instructor sets the program's events
        s, new = self.req("POST", "/api/instructor/train/event", {"name": "Shuttle run", "unit": "time", "better": "lower"}, coach)
        self.assertEqual(s, 200)
        self.addCleanup(train._path().unlink, missing_ok=True)
        self.assertIn("Shuttle run", [e["name"] for e in self.req("GET", "/api/train", cookie=al)[1]["events"]])
        self.assertEqual(self.req("POST", "/api/instructor/train/event", {"name": "Bad", "unit": "parsecs", "better": "higher"}, coach)[0], 400)
        self.req("POST", "/api/instructor/train/event", {"action": "remove", "id": new["id"]}, coach)
        self.assertNotIn("Shuttle run", [e["name"] for e in self.req("GET", "/api/train", cookie=al)[1]["events"]])


if __name__ == "__main__":
    unittest.main()
