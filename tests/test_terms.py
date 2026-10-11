"""Terms of use and Privacy notice (2026-10-11): shipped where every updater accepts them, readable before setup,
accepted by ticking a box on first run (or by an instructor), and never by a Cadet's phone."""
import http.client
import json
import os
import re
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

from vanguard import integrity, profiles, security, store, terms  # noqa: E402
from vanguard.server import Handler, serve  # noqa: E402


class TermsDocumentTests(unittest.TestCase):
    def test_both_documents_ship_inside_the_app_folder(self):
        for doc in terms.DOCS:
            text = terms.text(doc)
            self.assertTrue(text and f"Version {terms.VERSION}" in text, doc)
            self.assertIn("support@cadetfoundry.org", text)
            self.assertIn("the Cadet Foundry project", text)
        # inside vanguard/: an older updater (0.2.3) accepts them, so the update path keeps working
        self.assertTrue(integrity.__dict__["_ALLOWED_DIRS"][0] == "vanguard/")
        self.assertIsNone(terms.text("../README"))

    def test_no_claim_of_a_company_that_doesnt_exist(self):
        for path in [*ROOT.glob("*.md"), *(ROOT / "docs").glob("*.md"), *(ROOT / "vanguard" / "legal").glob("*.md"),
                     ROOT / "site" / "build.py", ROOT / "site" / "installer.iss", ROOT / "tools" / "make_usb.py"]:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\bLLC\b", path.name)               # the domain winklers-llc.com is fine

    def test_the_privacy_notice_matches_the_website_worker(self):
        worker = (ROOT / "site" / "worker.js").read_text(encoding="utf-8")
        self.assertNotRegex(worker, r"(?i)set-cookie|analytics|beacon")   # the notice says: no cookies, no analytics
        self.assertIn("/.well-known/security.txt", worker)


class TermsAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_app = getattr(Handler, "app", None)
        cls.httpd = serve("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        Handler.app.port = cls.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        if cls.saved_app is not None:
            Handler.app = cls.saved_app

    def req(self, method, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        h = {"Host": f"127.0.0.1:{self.port}", "Cookie": cookie, "Content-Type": "application/json"}
        c.request(method, path, body=json.dumps(body or {}) if method == "POST" else None, headers=h)
        r = c.getresponse()
        data = json.loads(r.read() or b"{}")
        ck = (r.getheader("Set-Cookie") or "").split(";")[0]
        c.close()
        return r.status, data, ck

    def test_documents_are_readable_before_anyone_signs_in(self):
        st, d, _ = self.req("GET", "/api/legal?doc=privacy")
        self.assertEqual(st, 200)
        self.assertIn("Privacy notice", d["text"])
        self.assertEqual(self.req("GET", "/api/legal?doc=../../config")[0], 404)

    def test_first_run_accepts_on_this_computer_and_records_only_version_and_date(self):
        with mock.patch.object(security, "admin_set", lambda: False), \
                mock.patch.object(store, "save_config") as save:
            st, d, _ = self.req("POST", "/api/terms/accept")
            self.assertEqual(st, 200, d)
            saved = save.call_args[0][0]["terms"]
            self.assertEqual(set(saved), {"version", "date"})
            self.assertEqual(saved["version"], terms.VERSION)
            with mock.patch.object(Handler, "_local", lambda self: False):     # a phone on the classroom Wi-Fi
                self.assertEqual(self.req("POST", "/api/terms/accept")[0], 403)

    def test_after_setup_only_an_instructor_accepts(self):
        cadet = profiles.create(f"Terms-{uuid.uuid4().hex[:6]}", "cadet")
        try:
            with security.as_profile(cadet["id"]):
                assert security.set_pin("482915") is None
            ck = self.req("POST", "/api/unlock", {"profile": cadet["id"], "pin": "482915"})[2]
            with mock.patch.object(security, "admin_set", lambda: True), mock.patch.object(store, "save_config"):
                self.assertEqual(self.req("POST", "/api/terms/accept", cookie=ck)[0], 403)
                self.assertEqual(self.req("POST", "/api/terms/accept")[0], 403)      # nobody signed in
        finally:
            profiles.delete(cadet["id"])

    def test_the_sign_in_screen_says_whether_terms_are_accepted(self):
        with mock.patch.object(terms, "accepted", lambda: False):
            d = self.req("GET", "/api/lock")[1]
            self.assertFalse(d["terms_ok"])
            self.assertEqual(d["terms_version"], terms.VERSION)
        with mock.patch.object(terms, "accepted", lambda: True):
            self.assertTrue(self.req("GET", "/api/lock")[1]["terms_ok"])

    def test_a_stored_acceptance_must_match_the_current_version(self):
        with mock.patch.object(store, "config", lambda: {"terms": {"version": "2000-01-01", "date": "2000-01-01"}}):
            self.assertFalse(terms.accepted())
        with mock.patch.object(store, "config", lambda: {"terms": {"version": terms.VERSION, "date": "2026-10-11"}}):
            self.assertTrue(terms.accepted())
        with mock.patch.object(store, "config", lambda: {}), mock.patch.object(store, "write_json") as w:
            store.save_config({"terms": {"version": terms.VERSION, "name": "someone"}})   # nothing about who
            self.assertNotIn("terms", w.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
