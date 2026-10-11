"""A whole class day, end to end through the real server: an instructor sets up a platoon and a lesson, three Cadets
do real work (lesson, typed quiz, exam, scenarios, service, fitness), and the instructor's dashboard, lesson results,
CSV report and each Cadet's progress must show exactly what the Cadets did -- and nothing private."""
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

from vanguard import instructor, lessons, profiles, security, store, vault  # noqa: E402
from vanguard.server import serve  # noqa: E402

ADMIN = "905172"
LESSON = {"title": "Chain of command", "objective": "Know who leads whom.", "content": "Study the chain of command card.",
          "questions": "Q: Who is at the top of the chain of command?\n* The President\n- The first sergeant\n"
                       "Q: Which channel runs alongside the chain of command?\n* The NCO support channel\n- The mail room",
          "reflection": "Who is in your chain of command at school?"}


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class ClassDayTests(unittest.TestCase):
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
        cls.ana, cls.ben, cls.cal = (profiles.create(f"Ana-{tag}"), profiles.create(f"Ben-{tag}"),
                                     profiles.create(f"Cal-{tag}"))
        cls.sgt = profiles.create(f"Sgt-{tag}", "instructor")
        cls.pins = {cls.ana["id"]: "482915", cls.ben["id"]: "573920", cls.cal["id"]: "618274", cls.sgt["id"]: "736281"}
        for pid, pin in cls.pins.items():
            with security.as_profile(pid):
                assert security.set_pin(pin) is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        for a in [x for x in lessons.all_assignments() if x.get("title", "").startswith("Chain of command")]:
            lessons.delete_assignment(a["id"])
        for p in (cls.ana, cls.ben, cls.cal, cls.sgt):
            profiles.delete(p["id"])
        if cls.made_admin:
            (store.DATA / "admin.json").unlink(missing_ok=True)

    def req(self, method, path, body=None, cookie="", raw=False):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = {"Host": f"127.0.0.1:{self.port}", "Cookie": cookie}
        if body is not None:
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return (r.status, data) if raw else (r.status, json.loads(data or b"{}"))

    def ok(self, method, path, body=None, cookie=""):
        s, out = self.req(method, path, body, cookie)
        self.assertEqual(s, 200, f"{path}: {out}")
        return out

    def login(self, p):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/api/unlock", body=json.dumps({"profile": p["id"], "pin": self.pins[p["id"]]}),
                  headers={"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"})
        r = c.getresponse()
        r.read()
        c.close()
        return r.getheader("Set-Cookie").split(";")[0]

    def test_the_instructor_sees_exactly_what_the_cadets_did(self):
        A, B, C, S = (self.login(self.ana), self.login(self.ben), self.login(self.cal), self.login(self.sgt))
        ida, idb, idc = self.ana["id"], self.ben["id"], self.cal["id"]

        # ── the instructor sets up a platoon and a lesson for it (Cal isn't in the platoon) ──
        self.ok("POST", "/api/instructor/unlock", {"admin": ADMIN}, S)
        unit = self.ok("POST", "/api/instructor/unit", {"action": "add", "name": "1st Platoon", "kind": "platoon"}, S)
        uid = unit["id"] if "id" in unit else next(u["id"] for u in unit["units"] if u["name"] == "1st Platoon")
        for pid in (ida, idb):
            self.ok("POST", "/api/instructor/assign", {"cadet": pid, "unit": uid}, S)
        lesson = self.ok("POST", "/api/instructor/lesson", LESSON, S)
        tomorrow = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400))
        asg = self.ok("POST", "/api/instructor/assign-lesson", {"lesson": lesson["id"], "units": [uid], "due": tomorrow}, S)
        aid = asg["id"] if "id" in asg else asg["assignment"]["id"]

        # ── the Cadets do the lesson ──
        self.assertEqual([x["id"] for x in self.ok("GET", "/api/lessons", cookie=A)["assignments"]], [aid])
        self.assertEqual(self.ok("GET", "/api/lessons", cookie=C)["assignments"], [])          # not in the platoon
        # answers are choice numbers: the right one is wherever "The President" landed
        lz = self.ok("GET", f"/api/lesson?a={aid}", cookie=A)
        qs = lz["lesson"]["questions"] if "lesson" in lz else lz["questions"]
        right = {str(i): next(j for j, c in enumerate(q["choices"]) if c in ("The President", "The NCO support channel"))
                 for i, q in enumerate(qs)}
        wrong1 = dict(right, **{"1": str(1 - int(right["1"]))})
        self.assertEqual(self.req("POST", "/api/lesson/submit", {"a": aid, "answers": right}, A)[0], 400)   # reflection
        self.ok("POST", "/api/lesson/submit", {"a": aid, "answers": right, "reflection": "My squad leader, then the PSG."}, A)
        self.ok("POST", "/api/lesson/submit", {"a": aid, "answers": wrong1, "reflection": "My team leader."}, B)

        # ── typed quiz (graded by Cadet Foundry), an exam, scenarios, service, fitness ──
        q = next(x for x in self.ok("GET", "/api/quiz?n=50&topic=citizenship_three_branches", cookie=A)
                 if "how many branches" in x["q"].lower())
        self.assertTrue(self.ok("POST", "/api/quiz/answer", {"id": q["id"], "answer": "three, legislative executive judicial"}, A)["correct"])
        self.assertFalse(self.ok("POST", "/api/quiz/answer", {"id": q["id"], "answer": "two"}, B)["correct"])
        ex = self.ok("POST", "/api/exam/start", {"topic": "Citizenship", "n": 5}, A)
        ex_out = self.ok("POST", "/api/exam/submit", {"id": ex["id"], "answers": {str(i): 0 for i in range(len(ex["questions"]))}}, A)
        self.ok("POST", "/api/scenario/log", {"id": "01_two_cadets_arguing", "choice": 2, "reflection": "Listen to both."}, A)
        for sid in ("02_teammate_checked_out", "05_tough_feedback"):
            self.ok("POST", "/api/scenario/log", {"id": sid, "choice": 1, "reflection": "Ask first."}, B)
        mine = self.ok("POST", "/api/service/add", {"project": "Food drive", "hours": "4", "date": time.strftime("%Y-%m-%d"),
                                                     "reflection": "We sorted 300 cans."}, A)
        entry = mine["entries"][0]["id"]
        self.ok("POST", "/api/train/add", {"event": "pushups", "value": "20", "date": "2026-09-01"}, B)
        self.ok("POST", "/api/train/add", {"event": "pushups", "value": "30", "date": "2026-10-01"}, B)
        self.ok("POST", "/api/memory", {"text": "PRIVATE-NOTE my grandma is sick"}, A)            # private, never shown

        # ── the instructor runs a scenario on the projector; the class votes; the instructor sees the counts ──
        self.ok("POST", "/api/instructor/live", {"action": "start", "scenario": "04_answers_going_around"}, S)
        self.assertEqual(self.ok("GET", "/api/live", cookie=C)["scenario"]["id"], "04_answers_going_around")
        self.ok("POST", "/api/live/vote", {"choice": 1}, A)
        self.ok("POST", "/api/live/vote", {"choice": 1}, B)
        self.ok("POST", "/api/live/vote", {"choice": 2}, C)
        live = self.ok("GET", "/api/instructor/live", cookie=S)
        self.assertEqual((live["votes"], live["counts"][1], live["counts"][2]), (3, 2, 1))
        self.assertNotIn(ida, json.dumps(live))                              # counts only, never who
        self.ok("POST", "/api/instructor/live", {"action": "reveal"}, S)
        self.assertIn("guidance", self.ok("GET", "/api/instructor/live", cookie=S))
        self.ok("POST", "/api/instructor/live", {"action": "stop"}, S)

        # ── the instructor's view ──
        dash = self.ok("GET", "/api/instructor/dashboard", cookie=S)
        rows = {r["id"]: r for r in dash["rows"]}
        a, b, c = rows[ida], rows[idb], rows[idc]
        self.assertTrue(a["shared"] and b["shared"] and c["shared"])
        self.assertEqual((a["unit"], b["unit"], c["unit"]), ("1st Platoon", "1st Platoon", ""))
        self.assertEqual((a["lessons_assigned"], a["lessons_completed"], a["lesson_score_pct"]), (1, 1, 100))
        self.assertEqual((b["lessons_assigned"], b["lessons_completed"], b["lesson_score_pct"]), (1, 1, 50))
        self.assertEqual((c["lessons_assigned"], c["lessons_completed"]), (0, 0))
        self.assertEqual((a["scenarios"], b["scenarios"], c["scenarios"]), (1, 2, 0))
        self.assertEqual((a["service_hours"], a["service_pending"]), (0, 1))                   # not verified yet
        self.assertEqual(b["fitness_improvement_pct"], 50)                                     # 20 -> 30 push-ups
        self.assertEqual(a["cards_mastered"], 0)                     # mastered = 80% of a card's questions known
        self.assertTrue(a["active"] and b["active"])
        for k in ("lesson_completion_pct", "avg_lesson_score_pct"):
            self.assertIsNotNone(dash[k])

        # the lesson's results, Cadet by Cadet
        det = self.ok("GET", f"/api/instructor/assignment?id={aid}", cookie=S)
        res = {r["id"]: r for r in det["cadets"]}
        self.assertEqual((res[ida]["state"], res[ida]["score"], res[ida]["total"]), ("complete", 2, 2))
        self.assertEqual((res[idb]["state"], res[idb]["score"]), ("complete", 1))
        self.assertIn("squad leader", res[ida]["reflection"])
        self.assertNotIn(idc, res)

        # verify the service hours -> they count
        self.ok("POST", "/api/instructor/service/review", {"cadet": ida, "id": entry, "action": "verify"}, S)
        a = {r["id"]: r for r in self.ok("GET", "/api/instructor/dashboard", cookie=S)["rows"]}[ida]
        self.assertEqual((a["service_hours"], a["service_pending"]), (4, 0))

        # one Cadet's progress: the same numbers the Cadet sees, the exam included -- never private notes
        theirs = self.ok("GET", f"/api/instructor/progress?id={ida}", cookie=S)
        own = self.ok("GET", "/api/progress", cookie=A)
        self.assertEqual(theirs["academics"]["exams"], 1)
        self.assertEqual(theirs["academics"]["best_exam"], own["academics"]["best_exam"])
        self.assertEqual(theirs["academics"]["best_exam"], ex_out["score_pct"] if "score_pct" in ex_out else theirs["academics"]["best_exam"])
        self.assertEqual(theirs["service"]["verified_hours"], 4)
        self.assertEqual(theirs["leadership"], own["leadership"])
        cit = lambda pf: next(c for c in pf["academics"]["categories"] if c["id"] == "citizenship")["known"]  # noqa: E731
        self.assertGreaterEqual(cit(theirs), 1)                       # the typed quiz answer counts
        self.assertEqual(cit(theirs), cit(own))
        ben = self.ok("GET", f"/api/instructor/progress?id={idb}", cookie=S)
        push = next(e for e in ben["fitness"]["events"] if e["name"] == "Push-ups")
        self.assertEqual((push["first"], push["latest"]), ("20", "30"))
        self.assertNotIn("PRIVATE-NOTE", json.dumps(theirs))

        # the CSV report has every Cadet with the same numbers
        s, csv = self.req("GET", "/api/instructor/report.csv", cookie=S, raw=True)
        lines = csv.decode("utf-8-sig").splitlines()
        self.assertEqual(s, 200)
        ana_line = next(x for x in lines if x.startswith(self.ana["name"]))
        self.assertIn("1st Platoon", ana_line)
        self.assertIn("100", ana_line)
        self.assertTrue(any(x.startswith(self.cal["name"]) for x in lines))
        self.assertNotIn("PRIVATE-NOTE", csv.decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
