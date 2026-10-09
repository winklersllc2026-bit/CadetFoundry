"""Phase 9: dashboard, reports, CSV export, program backup, quiz edits and pop quizzes."""
import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import lessons, profiles, quiz_edits, reports, security, store, vault  # noqa: E402
from vanguard.server import serve  # noqa: E402

ADMIN = "905172"


class CsvTests(unittest.TestCase):
    def test_csv_never_carries_a_spreadsheet_formula(self):
        out = reports.to_csv([{"name": "=HYPERLINK(\"http://x\")", "unit": "+cmd", "let": 2, "shared": True,
                               "lessons_completed": 1, "lessons_assigned": 2}])
        self.assertIn("'=HYPERLINK", out)
        self.assertIn("'+cmd", out)


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class InstructorReportTests(unittest.TestCase):
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
        cls.a, cls.b = profiles.create(f"Ty-{tag}"), profiles.create(f"Zo-{tag}")
        cls.t = profiles.create(f"Cpt-{tag}", "instructor")
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

    def req(self, method, path, body=None, cookie="", raw=False):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Host": f"127.0.0.1:{self.port}", "Cookie": cookie}
        if body is not None:
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        headers = dict(r.getheaders())
        c.close()
        return (r.status, data, headers) if raw else (r.status, json.loads(data or b"{}"))

    def login(self, pid, pin):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/api/unlock", body=json.dumps({"profile": pid, "pin": pin}),
                  headers={"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"})
        r = c.getresponse()
        r.read()
        c.close()
        return r.getheader("Set-Cookie").split(";")[0]

    def test_dashboard_reports_quiz_edits_pop_quiz_and_backup(self):
        ty, zo, cpt = self.login(self.a["id"], "482915"), self.login(self.b["id"], "573920"), self.login(self.t["id"], "736281")
        for path in ("/api/instructor/dashboard", "/api/instructor/report.csv", "/api/instructor/quiz"):
            self.assertEqual(self.req("GET", path, cookie=ty)[0], 403)
        for path in ("/api/instructor/pop-quiz", "/api/instructor/quiz", "/api/instructor/program-backup", "/api/instructor/program-restore"):
            self.assertEqual(self.req("POST", path, {}, ty)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, cpt)[0], 200)
        # activity -> dashboard
        self.req("POST", "/api/scenario/log", {"id": "03_behind_schedule", "choice": 1, "reflection": "List tasks first."}, ty)
        self.req("POST", "/api/service/add", {"project": "Car wash", "hours": "2", "reflection": "Teamwork."}, ty)
        s, dash = self.req("GET", "/api/instructor/dashboard", cookie=cpt)
        self.assertEqual(s, 200)
        mine = {r["id"]: r for r in dash["rows"]}
        self.assertTrue(mine[self.a["id"]]["active"])
        self.assertGreaterEqual(dash["scenarios"], 1)
        self.assertGreaterEqual(dash["service_pending"], 1)
        # CSV export: an attachment, only names and numbers
        s, data, h = self.req("GET", "/api/instructor/report.csv", cookie=cpt, raw=True)
        self.assertEqual(s, 200)
        self.assertIn("attachment", h.get("Content-Disposition", ""))
        self.assertIn(self.a["name"], data.decode("utf-8-sig"))
        self.assertIn("Leadership scenarios", data.decode("utf-8-sig").splitlines()[0])
        # quiz edit: the program's answer is the one graded; a hidden question disappears
        qid = next(x["id"] for x in self.req("GET", "/api/quiz?n=50&topic=citizenship_three_branches", cookie=ty)[1] if "breaks ties" in x["q"].lower())
        self.addCleanup(quiz_edits.reset, qid)
        self.assertEqual(self.req("POST", "/api/instructor/quiz", {"id": qid, "a": "The Vice President of the United States"}, cpt)[0], 200)
        g = self.req("POST", "/api/quiz/answer", {"id": qid, "answer": "vice president of the united states"}, ty)[1]
        self.assertIn("Vice President of the United States", g["answer"])
        self.req("POST", "/api/instructor/quiz", {"id": qid, "hidden": True}, cpt)
        self.assertNotIn(qid, [x["id"] for x in self.req("GET", "/api/quiz?n=50&topic=citizenship_three_branches", cookie=ty)[1]])
        self.assertEqual(self.req("POST", "/api/quiz/answer", {"id": qid, "answer": "x"}, ty)[0], 404)
        # pop quiz: due today, only for the Cadet chosen
        s, pop = self.req("POST", "/api/instructor/pop-quiz", {"title": "Branches", "cadets": [self.a["id"]],
                                                               "questions": "Q: How many branches?\n* Three\n- Two"}, cpt)
        self.assertEqual(s, 200, pop)
        self.addCleanup(lambda: (lessons.delete_assignment(pop["assignment"]["id"])))
        got = self.req("GET", "/api/lessons", cookie=ty)[1]["assignments"]
        self.assertIn((pop["assignment"]["id"], time.strftime("%Y-%m-%d")), [(x["id"], x["due"]) for x in got])
        self.assertNotIn(pop["assignment"]["id"], [x["id"] for x in self.req("GET", "/api/lessons", cookie=zo)[1]["assignments"]])
        self.assertEqual(self.req("POST", "/api/instructor/pop-quiz", {"title": "Nobody", "questions": "Q: x?\n* a\n- b"}, cpt)[0], 400)
        # program backup: weak password refused; restore brings a deleted service project back
        self.assertEqual(self.req("POST", "/api/instructor/program-backup", {"password": "short"}, cpt)[0], 400)
        s, proj = self.req("POST", "/api/instructor/service/project", {"title": "Backup check project"}, cpt)
        s, bk = self.req("POST", "/api/instructor/program-backup", {"password": "long enough backup pass"}, cpt)
        self.assertEqual(s, 200)
        self.assertNotIn(b"Backup check project", json.dumps(bk).encode())          # sealed
        self.req("POST", "/api/instructor/service/project", {"action": "remove", "id": proj["id"]}, cpt)
        self.assertEqual(self.req("POST", "/api/instructor/program-restore", {"file": bk["file"], "password": "wrong password!!"}, cpt)[0], 400)
        s, out = self.req("POST", "/api/instructor/program-restore", {"file": bk["file"], "password": "long enough backup pass"}, cpt)
        self.assertEqual((s, out["relock"]), (200, True))
        self.assertEqual(self.req("GET", "/api/instructor/dashboard", cookie=cpt)[0], 403)      # Instructor PIN again
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, cpt)[0], 200)
        titles = [p["title"] for p in self.req("GET", "/api/instructor/service", cookie=cpt)[1]["projects"]]
        self.assertIn("Backup check project", titles)
        self.req("POST", "/api/instructor/service/project", {"action": "remove", "id": proj["id"]}, cpt)


if __name__ == "__main__":
    unittest.main()
