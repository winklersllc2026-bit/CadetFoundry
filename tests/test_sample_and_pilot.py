"""Batch 1 (2026-10-11): the sample class, Pilot mode and End pilot.

The sample class is a separate Vanguard process with its own throwaway folder; these tests start the real thing, use
it the way a visitor would, and check the real data folder is never touched. End pilot runs inside the sample too, so
it deletes made-up Cadets on realistic data -- never anything in the shared test folder.
"""
import http.client
import http.server
import threading
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import engine, profiles, sample, store, vault  # noqa: E402


class _Parent(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


class SampleFolderTests(unittest.TestCase):
    def test_only_a_marked_sample_folder_is_ever_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "VanguardData"
            real.mkdir()
            (real / "library_index.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(store, "DATA", real):
                target = sample.folder()
                self.assertEqual(target.name, "VanguardData-sample")
                target.mkdir()
                (target / "someone's file.txt").write_text("keep me", encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    sample._prepare(target)                    # not marked: refused, nothing deleted
                self.assertTrue((target / "someone's file.txt").exists())
                (target / "someone's file.txt").unlink()
                (target / sample.MARKER).write_text("x", encoding="utf-8")
                (target / "old.json").write_text("x", encoding="utf-8")
                sample._prepare(target)                        # marked: rebuilt from scratch
                self.assertFalse((target / "old.json").exists())
                self.assertTrue((target / sample.MARKER).exists())
                self.assertTrue((target / "library_index.json").exists())   # public index reused, nothing else


class SampleLifetimeTests(unittest.TestCase):
    def test_a_sample_closes_when_the_vanguard_that_opened_it_is_gone(self):
        class FakeServer:
            closed = threading.Event()

            def shutdown(self):
                self.closed.set()
        gone = FakeServer()
        with mock.patch.object(sample, "BACK", "http://127.0.0.1:1/"):    # nothing listens on port 1
            sample.watch_idle(gone, every=0.05)
            self.assertTrue(gone.closed.wait(5))
        alive = FakeServer()
        alive.closed = threading.Event()
        parent = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Parent)
        threading.Thread(target=parent.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(sample, "BACK", f"http://127.0.0.1:{parent.server_address[1]}/"):
                sample.touch()
                sample.watch_idle(alive, every=0.05)
                self.assertFalse(alive.closed.wait(1))                    # its Vanguard answers: it stays open
        finally:
            parent.shutdown()
            parent.server_close()


class PilotModeTests(unittest.TestCase):
    def test_pilot_mode_keeps_every_question_on_this_device(self):
        online = {"online": True, "groq_key": "test-not-a-real-key"}
        with mock.patch.object(store, "config", lambda: dict(online)):
            self.assertTrue(engine.online_ready())
        with mock.patch.object(store, "config", lambda: {**online, "pilot_mode": True}):
            self.assertFalse(engine.online_ready())
            with mock.patch.object(engine, "local_models", lambda: None):
                self.assertFalse(engine.status()["online_enabled"])    # the Ask notice doesn't claim it's online

    def test_pilot_mode_is_a_true_false_setting(self):
        with mock.patch.object(store, "config", lambda: {}), mock.patch.object(store, "write_json") as w:
            store.save_config({"pilot_mode": "yes please"})
            self.assertNotIn("pilot_mode", w.call_args[0][1])


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class SampleClassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.addClassCleanup(sample.stop_child)            # even if setup fails, no sample is left running
        cls.before = [p["id"] for p in profiles.all_profiles()]
        # a stand-in for the Vanguard that opens the sample: the sample checks it's still there
        cls.parent = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Parent)
        threading.Thread(target=cls.parent.serve_forever, daemon=True).start()
        cls.addClassCleanup(cls.parent.server_close)
        cls.addClassCleanup(cls.parent.shutdown)
        cls.back = f"http://127.0.0.1:{cls.parent.server_address[1]}/"
        cls.url = sample.start(cls.back)
        cls.port = int(cls.url.rstrip("/").rsplit(":", 1)[1])
        end = time.time() + 120
        while time.time() < end:
            st = sample._ask(cls.port, "/api/sample/status") or {}
            if st.get("ready") or st.get("error"):
                break
            time.sleep(0.5)
        cls.status = st

    @classmethod
    def tearDownClass(cls):
        sample.stop_child()
        proc = sample._child.get("proc")
        if proc:
            proc.wait(timeout=20)
        import shutil
        shutil.rmtree(sample.folder(), ignore_errors=True)

    def call(self, method, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        h = {"Host": f"127.0.0.1:{self.port}", "Cookie": cookie}
        if method == "POST":
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body or {}) if method == "POST" else None, headers=h)
        r = c.getresponse()
        data = r.read()
        ck = (r.getheader("Set-Cookie") or "").split(";")[0]
        c.close()
        try:
            return r.status, json.loads(data or b"{}"), ck
        except ValueError:
            return r.status, {}, ck

    def get(self, path, cookie=""):
        return self.call("GET", path, cookie=cookie)

    def enter(self):
        st, r, ck = self.call("POST", "/api/sample/enter")
        self.assertEqual(st, 200, r)
        return ck

    def test_1_the_sample_class_is_built_and_opens_straight_to_the_instructor(self):
        self.assertTrue(self.status.get("ready"), self.status)
        ck = self.enter()
        self.assertTrue(ck.startswith("vanguard_sample="))             # never replaces the real Vanguard's sign-in
        self.assertTrue(self.get("/api/lock", ck)[1]["sample"])
        ov = self.get("/api/instructor/overview", ck)[1]
        self.assertEqual(len(ov["cadets"]), len(sample.CADETS))
        self.assertTrue(all(c["name"].endswith("Sample") for c in ov["cadets"]))
        self.assertEqual({u["name"] for u in ov["units"]}, {"1st Period", "Alpha Squad", "Bravo Squad"})
        dash = self.get("/api/instructor/dashboard", ck)[1]
        self.assertGreater(dash["lesson_completion_pct"], 0)
        self.assertGreater(dash["scenarios"], 0)
        self.assertTrue(any(r["lessons_overdue"] for r in dash["rows"]))   # someone is behind, like a real class
        pl = self.get("/api/instructor/pilot", ck)[1]
        self.assertEqual(pl["config"]["school"], "Sample High School")
        self.assertGreaterEqual(len(pl["snapshots"]), 2)

    def test_1b_pilot_metrics_and_after_class_feedback(self):
        ck = self.enter()
        m = self.get("/api/instructor/pilot", ck)[1]["metrics"]
        self.assertEqual(m["cadets"], len(sample.CADETS))
        self.assertEqual(m["rating"], 4.5)                                     # the sample's two made-up ratings
        self.assertEqual((m["rating_days"], m["would_continue"]), (2, "yes"))
        self.assertTrue(0 < m["assignments_completed"] <= m["assignments"])
        self.assertEqual(m["assignments_pct"], round(100 * m["assignments_completed"] / m["assignments"]))
        self.assertTrue(0 < m["cadets_with_scenario"] <= m["cadets"])
        for bad in ({"useful": 0}, {"useful": 9}, {"useful": "x"}, {"useful": 3, "again": "sometimes"}):
            self.assertEqual(self.call("POST", "/api/instructor/pilot/daily", bad, ck)[0], 400, bad)
        st, row, _ = self.call("POST", "/api/instructor/pilot/daily",
                               {"useful": 2, "again": "maybe", "confusing": "TESTCONFUSING the planner"}, ck)
        self.assertEqual(st, 200, row)
        m = self.get("/api/instructor/pilot", ck)[1]["metrics"]
        self.assertEqual((m["rating_days"], m["rating"], m["would_continue"]), (3, 3.7, "maybe"))
        raw = (sample.folder() / "program" / "feedback_daily.json").read_bytes()
        self.assertNotIn(b"TESTCONFUSING", raw)                                # sealed at rest, like the pilot
        cadet = self.call("POST", "/api/unlock", {"profile": self.get("/api/instructor/overview", ck)[1]["cadets"][0]["id"],
                                                  "pin": sample.CADET_PIN})[2]
        self.assertEqual(self.call("POST", "/api/instructor/pilot/daily", {"useful": 5}, cadet)[0], 403)

    def test_2_the_real_data_folder_is_never_touched(self):
        self.assertEqual([p["id"] for p in profiles.all_profiles()], self.before)
        self.assertNotEqual(sample.folder(), store.DATA)
        self.assertTrue((sample.folder() / sample.MARKER).exists())

    def test_3_the_sample_cant_change_the_device_or_open_to_the_network(self):
        ck = self.enter()
        self.assertEqual(self.call("POST", "/api/instructor/classroom", {"open": True}, ck)[0], 403)
        st, r, _ = self.call("POST", "/api/admin/ai-mode", {"mode": "off", "admin": sample.CLASS_PIN}, ck)
        self.assertEqual(st, 403, r)
        self.assertEqual(self.call("POST", "/api/sample/start", {}, ck)[0], 400)   # no sample inside the sample

    def test_4_pilot_mode_shows_whats_stored(self):
        ck = self.enter()
        st = self.call("POST", "/api/instructor/pilot/mode", {"on": True}, ck)[1]
        self.assertTrue(st["pilot_mode"])
        self.assertFalse(st["online_ai"])
        self.assertEqual((st["cadets"], st["instructors"], st["lessons"]), (len(sample.CADETS), 1, 2))
        self.assertGreater(st["assignments"], 0)
        self.assertTrue(self.get("/api/instructor/pilot", ck)[1]["stored"]["pilot_mode"])

    def test_5_end_pilot_removes_the_pilot_and_keeps_the_instructors_work(self):
        ck = self.enter()
        before = self.get("/api/instructor/overview", ck)[1]
        old_code = next(iter(json.loads((sample.folder() / "program" / "join_codes.json").read_text(encoding="utf-8"))))
        self.assertEqual(self.get(f"/api/join-code?c={old_code}")[1].get("name") is not None, True)
        cadet_ck = self.call("POST", "/api/unlock", {"profile": before["cadets"][0]["id"], "pin": sample.CADET_PIN})[2]
        self.assertEqual(self.get("/api/lessons", cadet_ck)[0], 200)
        # refused: a Cadet, no DELETE, the wrong Class PIN
        self.assertEqual(self.call("POST", "/api/instructor/pilot/end", {"admin": sample.CLASS_PIN, "confirm": "DELETE"},
                                   cadet_ck)[0], 403)
        self.assertEqual(self.call("POST", "/api/instructor/pilot/end", {"admin": sample.CLASS_PIN}, ck)[0], 400)
        self.assertEqual(self.call("POST", "/api/instructor/pilot/end", {"admin": "135792", "confirm": "DELETE"}, ck)[0], 403)
        self.assertEqual(len(self.get("/api/instructor/overview", ck)[1]["cadets"]), len(sample.CADETS))   # nothing gone
        # ended
        st, out, _ = self.call("POST", "/api/instructor/pilot/end", {"admin": sample.CLASS_PIN, "confirm": "DELETE"}, ck)
        self.assertEqual(st, 200, out)
        self.assertEqual(out["cadets"], len(sample.CADETS))
        self.assertEqual([p["kind"] for p in out["remaining_profiles"]], ["instructor"])
        self.assertEqual(self.get("/api/lessons", cadet_ck)[0], 401)          # their sessions ended
        after = self.get("/api/instructor/overview", ck)[1]
        self.assertEqual(after["cadets"], [])
        self.assertEqual(len(after["units"]), 3)                              # classes kept...
        self.assertIsNone(self.get(f"/api/join-code?c={old_code}")[1].get("name"))   # ...with new join codes
        stored = self.get("/api/instructor/pilot", ck)[1]
        self.assertEqual((stored["stored"]["cadets"], stored["stored"]["assignments"], stored["stored"]["lessons"]),
                         (0, 0, 2))                                           # the instructor's lessons stay
        self.assertEqual(stored["config"], {})                                # the pilot's setup is gone
        self.assertEqual(stored["snapshots"], [])
        self.assertEqual(stored["metrics"]["rating_days"], 0)                 # after-class feedback went too
        self.assertFalse((sample.folder() / "program" / "feedback_daily.json").exists())
        left = {p.name for p in (sample.folder() / "profiles").iterdir() if p.is_dir()}
        self.assertEqual(len(left), 1)                                        # only the instructor's folder

    def test_6_leaving_closes_the_sample(self):
        st, r, _ = self.call("POST", "/api/sample/leave")
        self.assertEqual(st, 200)
        self.assertEqual(r["back"], self.back)
        sample._child["proc"].wait(timeout=20)
        self.assertIsNotNone(sample._child["proc"].poll())


if __name__ == "__main__":
    unittest.main()
