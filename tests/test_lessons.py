"""Phase 4: lessons and assignments, end to end over HTTP, with the permission rules (spec §19, §47)."""
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

from vanguard import lessons, profiles, security, store, vault  # noqa: E402
from vanguard.server import serve  # noqa: E402

ADMIN = "905172"
QUESTIONS = """Q: Who salutes first?
* The junior person
- The senior person
- Whoever sees the other first

Q: What does LET stand for?
- Leader Endurance Test
* Leadership Education and Training"""


class ParseTests(unittest.TestCase):
    def test_question_format(self):
        qs = lessons.parse_questions(QUESTIONS)
        self.assertEqual([q["answer"] for q in qs], [0, 1])
        self.assertEqual(lessons.parse_questions(lessons.questions_text(qs)), qs)        # round trip for editing
        for bad, msg in (("Q: x\n- a\n- b", "correct choice"), ("Q: x\n* a\n* b", "more than one"),
                         ("Q: x\n* a", "2 to 6"), ("just text", "start a question")):
            with self.assertRaises(ValueError) as e:
                lessons.parse_questions(bad)
            self.assertIn(msg, str(e.exception))

    def test_vocab_format(self):
        self.assertEqual(lessons.parse_vocab("Chain of command: who reports to whom\n\n- Squad: a small team"),
                         [{"term": "Chain of command", "definition": "who reports to whom"},
                          {"term": "Squad", "definition": "a small team"}])
        with self.assertRaises(ValueError):
            lessons.parse_vocab("no colon here")


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class LessonFlowTests(unittest.TestCase):
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
        cls.a = profiles.create(f"Ann-{tag}")
        cls.b = profiles.create(f"Ben-{tag}")
        cls.t = profiles.create(f"Teach-{tag}", "instructor")
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
        self.assertEqual(r.status, 200)
        return r.getheader("Set-Cookie").split(";")[0]

    def test_lesson_assign_complete_and_track(self):
        ann, ben = self.login(self.a["id"], "482915"), self.login(self.b["id"], "573920")
        teach = self.login(self.t["id"], "736281")
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, teach)[0], 200)
        # the instructor writes a lesson with private notes
        s, lesson = self.req("POST", "/api/instructor/lesson", {
            "title": "Customs and courtesies", "let_level": "1", "competency": "Leadership",
            "content": "Respect is shown through customs.", "questions": QUESTIONS,
            "vocabulary": "Salute: a sign of respect", "reflection": "When did you show respect today?",
            "notes": "SECRET-NOTE: stress the junior salutes first"}, teach)
        self.assertEqual(s, 200, lesson)
        # Cadets can't write lessons or see the instructor's list
        self.assertEqual(self.req("POST", "/api/instructor/lesson", {"title": "x", "content": "y"}, ann)[0], 403)
        self.assertEqual(self.req("GET", "/api/instructor/lessons", cookie=ann)[0], 403)
        # assign it to a platoon that holds Ann, not Ben
        _, unit = self.req("POST", "/api/instructor/unit", {"action": "add", "name": "Alpha", "kind": "platoon"}, teach)
        self.assertEqual(self.req("POST", "/api/instructor/assign", {"cadet": self.a["id"], "unit": unit["id"]}, teach)[0], 200)
        s, a = self.req("POST", "/api/instructor/assign-lesson", {"lesson": lesson["id"], "units": [unit["id"]],
                                                                  "due": "2026-10-20"}, teach)
        self.assertEqual(s, 200, a)
        self.addCleanup(lessons.delete_assignment, a["id"])
        self.assertEqual(a["cadets"], [self.a["id"]])
        # Ben doesn't see it and can't open it
        self.assertEqual(self.req("GET", "/api/lessons", cookie=ben)[1]["assignments"], [])
        self.assertEqual(self.req("GET", f"/api/lesson?a={a['id']}", cookie=ben)[0], 404)
        self.assertEqual(self.req("POST", "/api/lesson/submit", {"a": a["id"], "answers": {}}, ben)[0], 404)
        # Ann sees it -- without the answer key or the notes
        mine = self.req("GET", "/api/lessons", cookie=ann)[1]["assignments"]
        self.assertEqual([(x["id"], x["state"]) for x in mine], [(a["id"], "not_started")])
        s, opened = self.req("GET", f"/api/lesson?a={a['id']}", cookie=ann)
        self.assertEqual(s, 200)
        raw = json.dumps(opened)
        self.assertNotIn("SECRET-NOTE", raw)
        self.assertNotIn("answer", raw.replace('"answers"', ""))
        self.assertEqual(opened["work"]["state"], "in_progress")
        # instructor sees "in progress"
        prog = next(x for x in self.req("GET", "/api/instructor/lessons", cookie=teach)[1]["assignments"] if x["id"] == a["id"])
        self.assertEqual((prog["assigned"], prog["in_progress"], prog["complete"]), (1, 1, 0))
        # submit: reflection required, every question answered, graded on the server
        self.assertEqual(self.req("POST", "/api/lesson/submit", {"a": a["id"], "answers": {"0": 0, "1": 1}}, ann)[0], 400)
        self.assertEqual(self.req("POST", "/api/lesson/submit", {"a": a["id"], "answers": {"0": 0}, "reflection": "x"}, ann)[0], 400)
        s, res = self.req("POST", "/api/lesson/submit", {"a": a["id"], "answers": {"0": 0, "1": 0},
                                                         "reflection": "I saluted my instructor."}, ann)
        self.assertEqual((s, res["score"], res["total"]), (200, 1, 2))
        self.assertEqual(self.req("POST", "/api/lesson/submit", {"a": a["id"], "answers": {"0": 0, "1": 1},
                                                                 "reflection": "again"}, ann)[0], 400)   # once only
        self.assertEqual(self.req("GET", f"/api/lesson?a={a['id']}", cookie=ann)[1]["answers"], [0, 1])  # now shown
        # Ann's work is a class record: sealed on disk, readable by the instructor
        self.assertTrue(vault.is_sealed((profiles.folder(self.a["id"]) / "assignments.json").read_bytes()))
        s, det = self.req("GET", f"/api/instructor/assignment?id={a['id']}", cookie=teach)
        row = det["cadets"][0]
        self.assertEqual((row["state"], row["score"], row["reflection"]), ("complete", 1, "I saluted my instructor."))
        self.assertEqual(self.req("GET", f"/api/instructor/assignment?id={a['id']}", cookie=ann)[0], 403)
        # notes come back to the instructor only
        mine_t = next(x for x in self.req("GET", "/api/instructor/lessons", cookie=teach)[1]["lessons"] if x["id"] == lesson["id"])
        self.assertIn("SECRET-NOTE", mine_t["notes"])
        self.assertNotIn(b"SECRET-NOTE", (store.DATA / "program" / "lesson_notes.json").read_bytes())
        # an assigned lesson can't be deleted out from under the Cadets
        self.assertEqual(self.req("POST", "/api/instructor/lesson", {"action": "delete", "id": lesson["id"]}, teach)[0], 400)


if __name__ == "__main__":
    unittest.main()
