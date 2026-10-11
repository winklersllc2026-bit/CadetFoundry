"""0.2.2: "Open class to phones" from the instructor's Home -- the desktop icon starts Vanguard for this computer only;
the instructor opens class without quitting. Only an instructor with the class open, only on their own computer.
The server listens again in classroom mode on the same port, and sign-ins survive the switch."""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import profiles, security, store, vault  # noqa: E402
from vanguard.server import Handler, reopen, serve  # noqa: E402

ADMIN = "905172"


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class ClassroomSwitchTests(unittest.TestCase):
    def setUp(self):
        self.saved_app = getattr(Handler, "app", None)
        self.httpd = serve("127.0.0.1", 0)
        self.port = self.httpd.server_address[1]
        Handler.app.port = self.port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.made_admin = not security.admin_set()
        if self.made_admin:
            assert security.set_admin_pin(ADMIN) is None
        tag = uuid.uuid4().hex[:6]
        self.inst = profiles.create(f"Rivera-{tag}", "instructor")
        self.cadet = profiles.create(f"Cadet-{tag}", "cadet")
        for p, pin in ((self.inst, "736281"), (self.cadet, "482915")):
            with security.as_profile(p["id"]):
                assert security.set_pin(pin) is None

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        for p in (self.inst, self.cadet):
            profiles.delete(p["id"])
        if self.made_admin:
            (store.DATA / "admin.json").unlink(missing_ok=True)
        if self.saved_app is not None:
            Handler.app = self.saved_app

    def req(self, method, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Host": f"127.0.0.1:{self.port}", "Cookie": cookie, "Content-Type": "application/json"}
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        ck = (r.getheader("Set-Cookie") or "").split(";")[0]
        c.close()
        return r.status, json.loads(data or b"{}"), ck

    def sign_in(self, p, pin, class_pin=False):
        ck = self.req("POST", "/api/unlock", {"profile": p["id"], "pin": pin})[2]
        if class_pin:
            self.assertEqual(self.req("POST", "/api/instructor/unlock", {"admin": ADMIN}, ck)[0], 200)
        return ck

    def test_only_the_instructor_on_their_own_computer_can_open_class(self):
        cadet = self.sign_in(self.cadet, "482915")
        self.assertEqual(self.req("POST", "/api/instructor/classroom", {"open": True}, cadet)[0], 403)
        no_class_pin = self.sign_in(self.inst, "736281")
        self.assertEqual(self.req("POST", "/api/instructor/classroom", {"open": True}, no_class_pin)[0], 403)
        inst = self.sign_in(self.inst, "736281", class_pin=True)
        with mock.patch.object(Handler, "_local", lambda self: False):          # a device on the network
            self.assertEqual(self.req("POST", "/api/instructor/classroom", {"open": True}, inst)[0], 403)
        self.assertFalse(Handler.app.lan)

    def test_open_class_reopens_on_the_same_port_and_keeps_sign_ins(self):
        inst = self.sign_in(self.inst, "736281", class_pin=True)
        st, r, _ = self.req("POST", "/api/instructor/classroom", {"open": True}, inst)
        self.assertEqual((st, r.get("restarting")), (200, True))
        self.thread.join(10)                                    # the server stopped listening in its old mode
        self.assertFalse(self.thread.is_alive())
        self.assertIs(self.httpd.switch_lan, True)
        self.httpd.server_close()
        self.httpd = reopen(self.port, True)                    # what run.py does
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.assertEqual(self.httpd.server_address[0], "0.0.0.0")
        self.assertTrue(self.req("GET", "/api/lock")[1]["lan"])
        st, status, _ = self.req("GET", "/api/status", cookie=inst)
        self.assertEqual((st, status["lan"]), (200, True))     # still signed in after the switch
        # and closing it again
        st, r, _ = self.req("POST", "/api/instructor/classroom", {"open": False}, inst)
        self.assertEqual(st, 200)
        self.thread.join(10)
        self.assertIs(self.httpd.switch_lan, False)
        self.httpd.server_close()
        self.httpd = reopen(self.port, False)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")
        self.assertFalse(self.req("GET", "/api/lock")[1]["lan"])


if __name__ == "__main__":
    unittest.main()
