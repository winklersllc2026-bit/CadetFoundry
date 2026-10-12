"""Phase 8: My Progress -- growth from class records only, recognition by the instructor, printable portfolio."""
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
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
os.environ["CADETFOUNDRY_NO_WARMUP"] = "1"

from cadetfoundry import profiles, security, store, vault  # noqa: E402
from cadetfoundry.server import serve  # noqa: E402

ADMIN = "905172"


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class ProgressTests(unittest.TestCase):
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
        cls.a = profiles.create(f"Ria-{tag}")
        cls.t = profiles.create(f"Lt-{tag}", "instructor")
        for p, pin in ((cls.a, "482915"), (cls.t, "736281")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        for p in (cls.a, cls.t):
            profiles.delete(p["id"])
        if cls.made_admin:
            (store.DATA / "admin.json").unlink(missing_ok=True)

    def req(self, method, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
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

    def test_portfolio_from_real_activity(self):
        ria, lt = self.login(self.a["id"], "482915"), self.login(self.t["id"], "736281")
        # some real activity by the Cadet
        self.req("POST", "/api/scenario/log", {"id": "01_two_cadets_arguing", "choice": 1, "reflection": "Listen first.",
                                                "learned": "Fair can be fast."}, ria)
        self.req("POST", "/api/service/add", {"project": "Food drive", "hours": "3", "date": "2026-10-01",
                                               "reflection": "Sorting by date saved time."}, ria)
        self.req("POST", "/api/train/add", {"event": "pushups", "value": "20", "date": "2026-09-01"}, ria)
        self.req("POST", "/api/train/add", {"event": "pushups", "value": "27", "date": "2026-10-01"}, ria)
        q = next(x for x in self.req("GET", "/api/quiz?n=50&topic=citizenship_three_branches", cookie=ria)[1] if "how many branches" in x["q"].lower())
        self.req("POST", "/api/quiz/answer", {"id": q["id"], "answer": "three: legislative, executive and judicial"}, ria)
        self.req("POST", "/api/memory", {"text": "PRIVATE-MEMORY my parents are divorcing"}, ria)   # a private file
        s, me = self.req("GET", "/api/progress", cookie=ria)
        self.assertEqual(s, 200)
        self.assertEqual(me["leadership"]["scenarios_completed"], 1)
        self.assertEqual(me["service"]["pending_hours"], 3)
        push = next(e for e in me["fitness"]["events"] if e["name"] == "Push-ups")
        self.assertEqual((push["first"], push["latest"], push["improvement_shown"]), ("20", "27", "+7"))
        cit = next(c for c in me["academics"]["categories"] if c["id"] == "citizenship")
        self.assertGreaterEqual(cit["known"], 1)
        titles = {a["title"] for a in me["achievements"]}
        self.assertTrue({"First leadership scenario", "Personal fitness best"} <= titles)
        self.assertNotIn("First service project verified", titles)                  # not verified yet
        self.assertTrue(any(m["scenarios"] == 1 for m in me["timeline"]))
        # no invented percentage for leadership
        self.assertNotIn("pct", json.dumps(me["leadership"]))
        # Cadets can't use the instructor's tools
        self.assertEqual(self.req("GET", f"/api/instructor/progress?id={self.a['id']}", cookie=ria)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/recognition", {"cadet": self.a["id"], "kind": "award", "title": "Me"}, ria)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/portfolio-sections", {"sections": ["academics"]}, ria)[0], 403)
        # the instructor sees the same portfolio -- never the private files -- and adds recognition
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, lt)[0], 200)
        s, theirs = self.req("GET", f"/api/instructor/progress?id={self.a['id']}", cookie=lt)
        self.assertEqual((s, theirs["leadership"]["scenarios_completed"]), (200, 1))
        self.assertNotIn("PRIVATE-MEMORY", json.dumps(theirs))
        s, rec = self.req("POST", "/api/instructor/recognition", {"cadet": self.a["id"], "kind": "award",
                                                                 "title": "Cadet of the Month", "note": "Led the food drive."}, lt)
        self.assertEqual(s, 200)
        self.assertEqual(self.req("POST", "/api/instructor/recognition", {"cadet": self.a["id"], "kind": "medal", "title": "x"}, lt)[0], 400)
        mine = self.req("GET", "/api/progress", cookie=ria)[1]
        self.assertEqual(mine["recognition"][0]["title"], "Cadet of the Month")
        self.assertTrue(vault.is_sealed((profiles.folder(self.a["id"]) / "recognition.jsonl").read_bytes()))
        # the instructor decides what a printed portfolio includes
        self.addCleanup(store.save_config, {"portfolio_sections": ["academics", "leadership", "fitness", "service", "recognition"]})
        s, out = self.req("POST", "/api/instructor/portfolio-sections", {"sections": ["leadership", "service"]}, lt)
        self.assertEqual(out["sections"], ["leadership", "service"])
        self.assertEqual(self.req("GET", "/api/progress", cookie=ria)[1]["sections"], ["leadership", "service"])
        self.req("POST", "/api/instructor/recognition", {"cadet": self.a["id"], "action": "remove", "id": rec["id"]}, lt)
        self.assertEqual(self.req("GET", "/api/progress", cookie=ria)[1]["recognition"], [])


if __name__ == "__main__":
    unittest.main()
