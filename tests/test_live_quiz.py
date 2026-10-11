"""Phase 11: the live in-class pop quiz -- graded by Cadet Foundry, one answer each, no answer before the reveal, counts only."""
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


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class LiveQuizTests(unittest.TestCase):
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
        cls.a = profiles.create(f"Ana-{tag}")
        cls.b = profiles.create(f"Ben-{tag}")
        cls.t = profiles.create(f"Ssg-{tag}", "instructor")
        for p, pin in ((cls.a, "482915"), (cls.b, "573920"), (cls.t, "736281")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        (store.DATA / "program" / "live_quiz.json").unlink(missing_ok=True)
        for p in (cls.a, cls.b, cls.t):
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

    def test_live_quiz_rules(self):
        ana, ben, ssg = (self.login(self.a["id"], "482915"), self.login(self.b["id"], "573920"),
                         self.login(self.t["id"], "736281"))
        # only an instructor (with the program unlocked) runs it
        self.assertEqual(self.req("POST", "/api/instructor/live-quiz", {"action": "start", "q": "x", "a": "y"}, ana)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, ssg)[0], 200)
        self.assertEqual(self.req("POST", "/api/instructor/live-quiz", {"action": "start", "q": "Who?", "a": "", "mode": "typed"}, ssg)[0], 400)

        # a study-card question, multiple choice
        d = self.req("GET", "/api/instructor/quiz?card=citizenship_three_branches", cookie=ssg)[1]
        qid = next(q["id"] for q in d["questions"] if "how many branches" in q["q"].lower())
        s, lq = self.req("POST", "/api/instructor/live-quiz", {"action": "start", "id": qid, "mode": "mc"}, ssg)
        self.assertEqual((s, lq["answered"], len(lq["choices"])), (200, 0, 4))
        right = next(c for c in lq["choices"] if c.lower().startswith("three"))
        wrong = next(c for c in lq["choices"] if c != right)

        # the Cadet's screen never gets the answer before the reveal
        s, mine = self.req("GET", "/api/live/quiz", cookie=ana)
        self.assertEqual((s, mine["q"], mine["answered"]), (200, lq["q"], False))
        self.assertNotIn("answer", mine)
        self.assertNotIn("a", mine)

        # graded here, one answer each, no result until the reveal
        s, mine = self.req("POST", "/api/live/quiz/answer", {"choice": right}, ana)
        self.assertEqual((s, mine["answered"]), (200, True))
        self.assertNotIn("verdict", mine)
        self.assertEqual(self.req("POST", "/api/live/quiz/answer", {"choice": wrong}, ana)[0], 400)      # no changing it
        self.assertEqual(self.req("POST", "/api/live/quiz/answer", {"choice": "made up"}, ben)[0], 400)
        self.assertEqual(self.req("POST", "/api/live/quiz/answer", {"choice": wrong}, ben)[0], 200)
        self.assertEqual(self.req("POST", "/api/live/quiz/answer", {"choice": right}, ssg)[0], 403)      # Cadets only

        # the projector: counts only, never who
        s, view = self.req("GET", "/api/instructor/live-quiz", cookie=ssg)
        self.assertEqual((view["answered"], view["right"], sum(view["counts"])), (2, 1, 2))
        raw = json.dumps(view)
        self.assertNotIn(self.a["id"], raw)
        self.assertNotIn(self.b["id"], raw)

        # the reveal: each Cadet sees the answer and their own result; answering is closed
        self.req("POST", "/api/instructor/live-quiz", {"action": "reveal"}, ssg)
        self.assertEqual(self.req("GET", "/api/live/quiz", cookie=ana)[1]["verdict"], "right")
        mine = self.req("GET", "/api/live/quiz", cookie=ben)[1]
        self.assertEqual(mine["verdict"], "wrong")
        self.assertIn("legislative", mine["answer"].lower())

        # the instructor's own question, typed and graded by meaning-words
        s, lq = self.req("POST", "/api/instructor/live-quiz", {"action": "start", "q": "What color is the union of the flag?",
                                                               "a": "Blue", "mode": "typed"}, ssg)
        self.assertEqual((s, lq["mode"], lq["choices"]), (200, "typed", []))
        self.assertEqual(self.req("POST", "/api/live/quiz/answer", {"answer": "  "}, ana)[0], 400)
        self.req("POST", "/api/live/quiz/answer", {"answer": "blue"}, ana)
        self.req("POST", "/api/live/quiz/answer", {"answer": "red"}, ben)
        self.assertEqual(self.req("GET", "/api/instructor/live-quiz", cookie=ssg)[1]["right"], 1)

        # ending it clears every screen
        self.req("POST", "/api/instructor/live-quiz", {"action": "stop"}, ssg)
        self.assertEqual(self.req("GET", "/api/live/quiz", cookie=ana)[1], {})
        self.assertEqual(self.req("POST", "/api/live/quiz/answer", {"answer": "blue"}, ana)[0], 404)


if __name__ == "__main__":
    unittest.main()
