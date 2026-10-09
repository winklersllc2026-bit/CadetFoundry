"""Phase 7: service learning -- projects, hours, roles, reflections, instructor verification."""
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

from vanguard import profiles, security, service, store, vault  # noqa: E402
from vanguard.server import serve  # noqa: E402

ADMIN = "905172"


class ServiceRuleTests(unittest.TestCase):
    def test_hours_and_dates(self):
        self.assertEqual(service._hours("2.6"), 2.5)                        # quarter hours
        for bad in ("0", "30", "lots"):
            with self.assertRaises(ValueError):
                service._hours(bad)
        with self.assertRaises(ValueError):
            service._date("2999-01-01")                                    # log service after you've done it


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class ServiceFlowTests(unittest.TestCase):
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
        cls.a, cls.b = profiles.create(f"Kai-{tag}"), profiles.create(f"Lu-{tag}")
        cls.t = profiles.create(f"Maj-{tag}", "instructor")
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

    def test_log_review_and_lock(self):
        kai, lu, maj = self.login(self.a["id"], "482915"), self.login(self.b["id"], "573920"), self.login(self.t["id"], "736281")
        # Cadets can't touch the instructor's service tools
        self.assertEqual(self.req("GET", "/api/instructor/service", cookie=kai)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/service/project", {"title": "x"}, kai)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/service/review", {"cadet": self.b["id"], "id": "x", "action": "verify"}, kai)[0], 403)
        # the instructor posts a project (spec §14 example)
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, maj)[0], 200)
        s, pr = self.req("POST", "/api/instructor/service/project", {"title": "Community Cleanup", "organization": "City Parks",
                                                                     "date": "2026-10-03", "hours": "4"}, maj)
        self.assertEqual(s, 200)
        self.addCleanup(service.remove_project, pr["id"])
        # a Cadet logs it: reflection required
        entry = {"project_id": pr["id"], "hours": "4", "role": "Team Lead"}
        self.assertEqual(self.req("POST", "/api/service/add", entry, kai)[0], 400)
        s, mine = self.req("POST", "/api/service/add", {**entry, "reflection": "Splitting the park into zones kept us moving."}, kai)
        self.assertEqual(s, 200)
        e = mine["entries"][0]
        self.assertEqual((e["project"], e["organization"], e["date"], e["hours"], e["role"], e["status"]),
                         ("Community Cleanup", "City Parks", "2026-10-03", 4.0, "Team Lead", "pending"))
        self.assertEqual((mine["totals"]["pending_hours"], mine["totals"]["verified_hours"]), (4.0, 0))
        self.assertTrue(vault.is_sealed((profiles.folder(self.a["id"]) / "service.jsonl").read_bytes()))
        self.assertEqual(self.req("GET", "/api/service", cookie=lu)[1]["entries"], [])          # only your own
        # the instructor sees it pending; returning needs a note
        ov = self.req("GET", "/api/instructor/service", cookie=maj)[1]
        self.assertGreaterEqual(ov["pending"], 1)
        self.assertEqual(self.req("POST", "/api/instructor/service/review", {"cadet": self.a["id"], "id": e["id"], "action": "return"}, maj)[0], 400)
        s, back = self.req("POST", "/api/instructor/service/review", {"cadet": self.a["id"], "id": e["id"], "action": "return",
                                                                      "note": "Add what you learned about leading."}, maj)
        self.assertEqual((s, back["status"]), (200, "returned"))
        # the Cadet fixes it -> pending again; the instructor verifies -> locked
        s, mine = self.req("POST", "/api/service/edit", {"id": e["id"], **entry, "reflection": "Leading meant checking on every zone."}, kai)
        self.assertEqual((s, mine["entries"][0]["status"]), (200, "pending"))
        self.assertEqual(self.req("POST", "/api/instructor/service/review", {"cadet": self.a["id"], "id": e["id"], "action": "verify"}, maj)[0], 200)
        mine = self.req("GET", "/api/service", cookie=kai)[1]
        self.assertEqual((mine["entries"][0]["status"], mine["totals"]["verified_hours"]), ("verified", 4.0))
        self.assertEqual(self.req("POST", "/api/service/edit", {"id": e["id"], **entry, "hours": "40", "reflection": "x"}, kai)[0], 400)
        self.assertEqual(self.req("POST", "/api/service/delete", {"id": e["id"]}, kai)[0], 400)
        # a free-text project works too
        s, mine = self.req("POST", "/api/service/add", {"project": "Food drive", "organization": "Church pantry", "hours": "2.5",
                                                        "date": "2026-10-05", "reflection": "Sorting by date saved time."}, kai)
        self.assertEqual((s, mine["totals"]["pending_hours"]), (200, 2.5))


if __name__ == "__main__":
    unittest.main()
