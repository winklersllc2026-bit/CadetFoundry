"""Phase 5: leadership scenarios, the leadership log, and classroom voting."""
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import profiles, scenarios, security, store, vault  # noqa: E402
from vanguard.server import serve  # noqa: E402

ADMIN = "905172"


class ScenarioContentTests(unittest.TestCase):
    def test_practice_scenarios_parse_and_are_not_combat(self):
        b = scenarios.builtins()
        self.assertGreaterEqual(len(b), 8)
        banned = re.compile(r"\b(weapon|rifle|enemy|kill|shoot|combat|firefight|ambush|casualt)\w*", re.I)
        for sc in b:
            self.assertTrue(2 <= len(sc["choices"]) <= 4, sc["id"])
            self.assertTrue(all(c["outcome"] for c in sc["choices"]), sc["id"])
            self.assertIsNone(banned.search(scenarios.to_text(sc)), sc["id"])
            # no "wrong answer"/"you failed" verdicts: the owner's philosophy
            self.assertNotRegex(scenarios.to_text(sc), r"(?i)\b(wrong answer|you failed|bad leader)\b")

    def test_format_errors_are_plain(self):
        with self.assertRaises(ValueError) as e:
            scenarios.parse("Title: x\nSituation: y\nChoice: only one\nOutcome: z")
        self.assertIn("2 to 4 choices", str(e.exception))
        with self.assertRaises(ValueError):
            scenarios.parse("Title: x\nSituation: y\nChoice: a\nChoice: b\nOutcome: z")       # choice 1 has no outcome


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class ScenarioFlowTests(unittest.TestCase):
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
        cls.a, cls.b = profiles.create(f"Ava-{tag}"), profiles.create(f"Bo-{tag}")
        cls.t = profiles.create(f"Sgt-{tag}", "instructor")
        for p, pin in ((cls.a, "482915"), (cls.b, "573920"), (cls.t, "736281")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        scenarios.live_stop()
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

    def test_scenario_log_and_classroom_vote(self):
        ava, bo, sgt = self.login(self.a["id"], "482915"), self.login(self.b["id"], "573920"), self.login(self.t["id"], "736281")
        sid = "01_two_cadets_arguing"
        # the situation and choices -- no outcomes until a choice is made
        s, sc = self.req("GET", f"/api/scenario?id={sid}", cookie=ava)
        self.assertEqual(s, 200)
        self.assertNotIn("outcome", json.dumps(sc))
        s, ex = self.req("POST", "/api/scenario/choose", {"id": sid, "choice": 1}, ava)
        self.assertEqual(s, 200)
        self.assertTrue(ex["outcome"] and ex["principles"])
        self.assertEqual(self.req("POST", "/api/scenario/choose", {"id": sid, "choice": 9}, ava)[0], 400)
        # the reflection is required; then it goes into the leadership log
        self.assertEqual(self.req("POST", "/api/scenario/log", {"id": sid, "choice": 1}, ava)[0], 400)
        s, out = self.req("POST", "/api/scenario/log", {"id": sid, "choice": 1, "reasoning": "Fair and fast",
                                                        "reflection": "I'd say the first sentence calmly.",
                                                        "learned": "Listen first."}, ava)
        self.assertEqual(s, 200)
        self.assertEqual(len(out["all_outcomes"]), 3)                      # every choice explained after logging
        log = self.req("GET", "/api/leadership-log", cookie=ava)[1]["entries"]
        self.assertEqual((log[0]["decision"], log[0]["reasoning"], log[0]["learned"]),
                         (ex["decision"], "Fair and fast", "Listen first."))
        self.assertEqual(self.req("GET", "/api/leadership-log", cookie=bo)[1]["entries"], [])   # only your own
        self.assertTrue(vault.is_sealed((profiles.folder(self.a["id"]) / "scenarios.jsonl").read_bytes()))
        # instructors can't keep a log; Cadets can't reach instructor scenario routes
        for path, body in (("/api/instructor/scenario", {"text": "x"}), ("/api/instructor/live", {"action": "start", "scenario": sid})):
            self.assertEqual(self.req("POST", path, body, ava)[0], 403)
        self.assertEqual(self.req("GET", f"/api/instructor/leadership-log?id={self.a['id']}", cookie=ava)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, sgt)[0], 200)
        s, ilog = self.req("GET", f"/api/instructor/leadership-log?id={self.a['id']}", cookie=sgt)
        self.assertEqual((s, ilog["entries"][0]["reflection"]), (200, "I'd say the first sentence calmly."))
        # instructor writes a scenario (and editing a practice one makes a copy, never changes it)
        text = scenarios.to_text(scenarios.get(sid)).replace("Two Cadets arguing", "Our own version")
        s, mine = self.req("POST", "/api/instructor/scenario", {"id": sid, "text": text}, sgt)
        self.assertEqual(s, 200)
        self.assertTrue(mine["id"].startswith("i-"))
        self.assertEqual(scenarios.get(sid)["title"], "Two Cadets arguing")
        self.assertEqual(self.req("POST", "/api/instructor/scenario", {"action": "delete", "id": sid}, sgt)[0], 400)
        self.assertEqual(self.req("POST", "/api/instructor/scenario", {"action": "delete", "id": mine["id"]}, sgt)[0], 200)
        # classroom mode: a live, anonymous vote
        self.assertEqual(self.req("POST", "/api/live/vote", {"choice": 0}, ava)[0], 404)          # nothing live yet
        self.assertEqual(self.req("POST", "/api/instructor/live", {"action": "start", "scenario": sid}, sgt)[0], 200)
        self.assertEqual(self.req("GET", "/api/live", cookie=bo)[1]["scenario"]["id"], sid)
        self.assertEqual(self.req("POST", "/api/live/vote", {"choice": 0}, ava)[0], 200)
        self.assertEqual(self.req("POST", "/api/live/vote", {"choice": 2}, bo)[0], 200)
        self.assertEqual(self.req("POST", "/api/live/vote", {"choice": 1}, bo)[0], 200)           # changing a vote replaces it
        self.assertEqual(self.req("POST", "/api/live/vote", {"choice": 1}, sgt)[0], 403)          # instructors don't vote
        s, board = self.req("GET", "/api/instructor/live", cookie=sgt)
        self.assertEqual((board["counts"], board["votes"]), ([1, 1, 0], 2))
        self.assertNotIn(self.a["id"], json.dumps(board))                                        # who voted what: never shown
        self.assertNotIn("guidance", board)
        board = self.req("POST", "/api/instructor/live", {"action": "reveal"}, sgt)[1]
        self.assertEqual(len(board["guidance"]["outcomes"]), 3)
        self.assertEqual(self.req("GET", "/api/live", cookie=ava)[1]["my_vote"], 0)
        self.req("POST", "/api/instructor/live", {"action": "stop"}, sgt)
        self.assertEqual(self.req("GET", "/api/live", cookie=ava)[1], {})
        # the instructor's overview counts each Cadet's scenarios
        ov = self.req("GET", "/api/instructor/scenarios", cookie=sgt)[1]
        self.assertEqual(next(c for c in ov["cadets"] if c["id"] == self.a["id"])["count"], 1)


if __name__ == "__main__":
    unittest.main()
