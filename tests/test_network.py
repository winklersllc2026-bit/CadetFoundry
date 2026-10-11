"""Security review, Phase 3: the classroom network -- Host and Origin checks, DNS rebinding, cookies.

Before: classroom mode accepted ANY Host header, and the Origin check only compared Origin with that Host, so a
website a Cadet visited could point its own name at the instructor's computer (DNS rebinding) and pass both checks.
Now classroom mode accepts only this computer's own IP address (the one the device connected to).
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import security  # noqa: E402
from vanguard.server import Handler, serve  # noqa: E402


class HostRuleTests(unittest.TestCase):
    def test_this_computer_only(self):
        ok = lambda h: security.host_ok(h, 8780, lan=False, local_ip="127.0.0.1")
        for good in ("127.0.0.1:8780", "localhost:8780", "LOCALHOST:8780", "[::1]:8780"):
            self.assertTrue(ok(good), good)
        for bad in ("evil.example:8780", "127.0.0.1:9999", "127.0.0.1", "192.168.1.20:8780", "", None,
                    "127.0.0.1:8780.evil.example", "127.0.0.1:8780@evil.example", "[::1]"):
            self.assertFalse(ok(bad), bad)

    def test_classroom_mode_accepts_only_this_computers_own_address(self):
        ok = lambda h, ip="192.168.1.20": security.host_ok(h, 8780, lan=True, local_ip=ip)
        self.assertTrue(ok("192.168.1.20:8780"))
        self.assertTrue(ok("127.0.0.1:8780", "127.0.0.1"))
        self.assertTrue(ok("192.168.1.20:8780", "::ffff:192.168.1.20"))        # IPv4 client on a dual-stack socket
        for bad in ("evil.example:8780",            # DNS rebinding: a website's own name pointed at this computer
                    "laptop.local:8780",            # any name at all
                    "192.168.1.99:8780",            # another address than the one connected to
                    "192.168.1.20:9999",            # wrong port
                    "192.168.1.20",                 # no port (Vanguard isn't on 80)
                    "192.168.1.20:8780:1", ""):
            self.assertFalse(ok(bad), bad)
        self.assertFalse(security.host_ok("192.168.1.20:8780", 8780, lan=True, local_ip=None))

    def test_port_80(self):
        self.assertTrue(security.host_ok("192.168.1.20", 80, lan=True, local_ip="192.168.1.20"))
        self.assertTrue(security.host_ok("localhost", 80, lan=False))


class OriginRuleTests(unittest.TestCase):
    def test_origin_must_be_vanguard_itself(self):
        self.assertTrue(security.origin_ok(None, "192.168.1.20:8780"))         # same-origin GET: browsers send none
        self.assertTrue(security.origin_ok("http://192.168.1.20:8780", "192.168.1.20:8780"))
        for bad in ("http://evil.example", "null", "https://192.168.1.20:8780", "http://192.168.1.20:8781",
                    "http://192.168.1.20:8780.evil.example"):
            self.assertFalse(security.origin_ok(bad, "192.168.1.20:8780"), bad)


class ClassroomServerTests(unittest.TestCase):
    """The real server in classroom mode, reached on 127.0.0.1 (its own address for this connection)."""
    @classmethod
    def setUpClass(cls):
        cls.saved_app = getattr(Handler, "app", None)
        cls.httpd = serve("127.0.0.1", 0, lan=True)
        cls.port = cls.httpd.server_address[1]
        Handler.app.port = cls.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        if cls.saved_app is not None:
            Handler.app = cls.saved_app

    def req(self, method, path, host, headers=None, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Host": host, **(headers or {})}
        if body is not None:
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r.status, r.getheader("Set-Cookie") or "", data

    def test_rebinding_and_foreign_hosts_are_refused_before_anything_runs(self):
        good = f"127.0.0.1:{self.port}"
        self.assertEqual(self.req("GET", "/api/lock", good)[0], 200)
        for bad in (f"evil.example:{self.port}", f"attacker.test:{self.port}", f"127.0.0.1:{self.port + 1}"):
            self.assertEqual(self.req("GET", "/api/lock", bad)[0], 421, bad)                       # no names leak
            self.assertEqual(self.req("POST", "/api/profiles/create", bad, body={"name": "x", "pin": "482915"})[0], 421)
            self.assertEqual(self.req("POST", "/api/unlock", bad, body={"profile": "x", "pin": "1"})[0], 421)

    def test_cross_site_requests_are_refused(self):
        good = f"127.0.0.1:{self.port}"
        for origin in ("http://evil.example", "null", f"http://evil.example:{self.port}"):
            st = self.req("POST", "/api/unlock", good, {"Origin": origin}, {"profile": "x", "pin": "1"})[0]
            self.assertEqual(st, 403, origin)
        # a form post (not JSON) is refused too: browsers can send those cross-site without asking first
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        c.request("POST", "/api/unlock", body="profile=x&pin=1",
                  headers={"Host": good, "Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(c.getresponse().status, 415)
        c.close()

    def test_the_session_cookie_is_http_only_and_same_site_strict(self):
        header = security.cookie_header("t0ken")
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Strict", header)
        self.assertIn("Path=/", header)
        self.assertNotIn("Domain=", header)          # never shared with other hosts


if __name__ == "__main__":
    unittest.main()
