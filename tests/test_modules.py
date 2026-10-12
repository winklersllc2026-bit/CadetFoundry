"""Phase 1 leftover: the instructor switches optional tools (faith, letters, voice) off for the device -- refused, not just hidden."""
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
class ModuleTests(unittest.TestCase):
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
        store.save_config({"modules_off": []})
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

    def test_switched_off_tools_are_refused(self):
        ana, ssg = self.login(self.a["id"], "482915"), self.login(self.t["id"], "736281")
        self.assertEqual(self.req("POST", "/api/instructor/modules", {"off": ["faith"]}, ana)[0], 403)
        self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, ssg)[0], 200)
        self.assertEqual(self.req("POST", "/api/instructor/modules", {"off": ["games"]}, ssg)[0], 400)
        s, r = self.req("POST", "/api/instructor/modules", {"off": ["faith", "letters", "voice"]}, ssg)
        self.assertEqual((s, r["modules_off"]), (200, ["faith", "letters", "voice"]))
        st = self.req("GET", "/api/status", cookie=ana)[1]
        self.assertEqual((st["modules_off"], st["voice"]), (["faith", "letters", "voice"], False))
        for path in ("/api/faith/catalog", "/api/faith/search?q=love", "/api/letters"):
            self.assertEqual(self.req("GET", path, cookie=ana)[0], 403, path)
        for path, body in (("/api/letters", {"to": "x", "text": "hi"}), ("/api/contacts", {"name": "x"}),
                           ("/api/voice", {"audio": ""}), ("/api/faith/plan/done", {"id": "x", "day": 1})):
            self.assertEqual(self.req("POST", path, body, ana)[0], 403, path)
        # back on: the routes answer again
        self.req("POST", "/api/instructor/modules", {"off": []}, ssg)
        self.assertEqual(self.req("GET", "/api/faith/catalog", cookie=ana)[0], 200)
        self.assertEqual(self.req("GET", "/api/letters", cookie=ana)[0], 200)
        self.assertEqual(self.req("GET", "/api/status", cookie=ana)[1]["modules_off"], [])


if __name__ == "__main__":
    unittest.main()
