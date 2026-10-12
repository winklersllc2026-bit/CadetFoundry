"""Demo box / classroom network: public installer downloads (only listed files), the demo flag, and every profile
keeping a PIN on the classroom network -- including a brand-new device with no profiles yet."""
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
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
os.environ["CADETFOUNDRY_NO_WARMUP"] = "1"

from cadetfoundry import profiles, security, server, store, vault  # noqa: E402
from cadetfoundry.server import serve  # noqa: E402


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class DemoBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = serve("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        app = cls.httpd.RequestHandlerClass.app
        app.port, app.lan = cls.port, True                   # behave like a demo box on its own Wi-Fi
        # requests below say Host 10.42.0.1 (the demo box's address); a real phone connects to that address too
        cls.ip_patch = mock.patch.object(server.Handler, "_server_ip", lambda self: "10.42.0.1")
        cls.ip_patch.start()
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.dl = tempfile.TemporaryDirectory()
        Path(cls.dl.name, "CadetFoundry-Setup-9.9.9.exe").write_bytes(b"MZ" + b"x" * 1000)
        Path(cls.dl.name, "notes.py").write_text("secret = 1")
        cls.old_downloads, server.DOWNLOADS = server.DOWNLOADS, Path(cls.dl.name)
        cls.made = []

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.ip_patch.stop()
        server.DOWNLOADS = cls.old_downloads
        cls.dl.cleanup()
        store.save_config({"demo": False})
        for pid in cls.made:
            profiles.delete(pid)

    def req(self, method, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Host": f"10.42.0.1:{self.port}", "Cookie": cookie}
        if body is not None:
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        return r.status, r.read(), r

    def test_downloads_are_public_and_listed_files_only(self):
        s, page, _ = self.req("GET", "/download")                 # no sign-in needed
        self.assertEqual(s, 200)
        self.assertIn(b"CadetFoundry-Setup-9.9.9.exe", page)
        self.assertNotIn(b"notes.py", page)
        s, data, r = self.req("GET", "/downloads/CadetFoundry-Setup-9.9.9.exe")
        self.assertEqual((s, data[:2], r.getheader("Content-Disposition")),
                         (200, b"MZ", 'attachment; filename="CadetFoundry-Setup-9.9.9.exe"'))
        for path in ("/downloads/notes.py", "/downloads/..%2Frun.py", "/downloads/../run.py", "/downloads/"):
            self.assertEqual(self.req("GET", path)[0], 404, path)
        self.assertEqual(json.loads(self.req("GET", "/api/lock")[1])["downloads"], True)

    def test_demo_flag_and_lan_flag_on_the_sign_in_screen(self):
        store.save_config({"demo": True})
        lock = json.loads(self.req("GET", "/api/lock")[1])
        self.assertEqual((lock["demo"], lock["lan"]), (True, True))
        store.save_config({"demo": "yes"})                         # only a real true/false is kept; junk is dropped
        self.assertIs(json.loads(self.req("GET", "/api/lock")[1])["demo"], False)

    def test_every_profile_keeps_a_pin_on_the_classroom_network(self):
        name = f"Cadet-{uuid.uuid4().hex[:6]}"
        s, body, _ = self.req("POST", "/api/profiles/create", {"name": name, "pin": "", "kind": "cadet"})
        self.assertEqual(s, 400)
        self.assertIn(b"needs a PIN", body)
        self.assertIsNone(next((p for p in profiles.all_profiles() if p["name"] == name), None))
        s, body, r = self.req("POST", "/api/profiles/create", {"name": name, "pin": "482915", "kind": "cadet"})
        self.assertEqual(s, 200)
        self.made.append(json.loads(body)["profile"]["id"])
        cookie = r.getheader("Set-Cookie").split(";")[0]
        self.assertEqual(self.req("POST", "/api/pin/remove", {"current": "482915"}, cookie)[0], 403)

    def test_other_devices_see_shortened_names_before_sign_in(self):
        name = f"Dana Q{uuid.uuid4().hex[:4]} Whitfield"
        p = profiles.create(name)
        self.made.append(p["id"])
        with security.as_profile(p["id"]):
            security.set_pin("482915")
        with mock.patch.object(server.Handler, "_local", return_value=False):   # a Cadet's phone on the Wi-Fi
            names = [x["name"] for x in json.loads(self.req("GET", "/api/lock")[1])["profiles"]]
        self.assertIn("Dana W.", names)
        self.assertNotIn(name, names)
        names = [x["name"] for x in json.loads(self.req("GET", "/api/lock")[1])["profiles"]]   # the laptop itself
        self.assertIn(name, names)

    def test_a_busy_port_is_never_shared(self):
        """Two copies on one port would let the browser reach the wrong data (a USB drive vs the computer's own)."""
        with self.assertRaises(OSError):
            serve("127.0.0.1", self.port)

    def test_each_data_folder_has_its_own_id(self):
        lock = json.loads(self.req("GET", "/api/lock")[1])
        self.assertEqual(lock["instance"], store.data_id())
        self.assertEqual(store.data_id(), store.data_id())              # stable

    def test_a_brand_new_device_can_start_on_the_classroom_network(self):
        with mock.patch.object(profiles, "all_profiles", return_value=[]):
            self.assertTrue(security.all_have_pins())


if __name__ == "__main__":
    unittest.main()
