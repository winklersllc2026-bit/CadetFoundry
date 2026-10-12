"""Issued drives and one home for the class (owner, 2026-10-12): a copied instructor drive shows the copyright notice;
an installed copy notices a class drive; a USB class is backed up only to the instructor's own computer."""
import json
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
from cadetfoundry import integrity, issued, store, usb_home, vault  # noqa: E402


def drive_layout(tmp: Path) -> Path:
    app = tmp / "E" / "Cadet Foundry"
    app.mkdir(parents=True)
    (tmp / "E" / "Cadet Foundry Data").mkdir()
    return app


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class IssuedTests(unittest.TestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        self.key = Ed25519PrivateKey.generate()                 # a test key: never the owner's release key
        self.pub = mock.patch.object(integrity, "public_key", lambda: self.key.public_key())
        self.pub.start()

    def tearDown(self):
        self.pub.stop()

    def test_an_issued_drive_is_quiet_and_a_copy_shows_the_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = drive_layout(Path(tmp))
            issued.write(app, "1A2B3C4D", "SFC Test, Test High", "2026-10-12", self.key)
            st = issued.status(app, serial_of=lambda d: "1A2B3C4D")
            self.assertEqual((st["drive"], st["copied"], st["to"]), (True, False, "SFC Test, Test High"))
            # the same files on another flash drive: another serial number
            self.assertTrue(issued.status(app, serial_of=lambda d: "99999999")["copied"])
            # someone edits the record to match their drive: the signature no longer verifies
            rec = json.loads((app / "issued.json").read_text())
            rec["serial"] = "99999999"
            (app / "issued.json").write_text(json.dumps(rec, sort_keys=True))
            self.assertTrue(issued.status(app, serial_of=lambda d: "99999999")["copied"])

    def test_no_record_is_a_copy_but_a_cadet_drive_never_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = drive_layout(Path(tmp))
            self.assertTrue(issued.status(app, serial_of=lambda d: "1A2B3C4D")["copied"])
            (app.parent / "Cadet Foundry Data" / "cadet_drive.json").write_text('{"id": "x"}')
            self.assertFalse(issued.status(app, serial_of=lambda d: "1A2B3C4D")["copied"])

    def test_an_installed_copy_is_never_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Programs" / "Cadet Foundry"
            app.mkdir(parents=True)
            self.assertEqual(issued.status(app)["drive"], False)
            self.assertFalse(issued.status(app)["copied"])

    def test_the_notice_claims_only_what_is_ours(self):
        text = issued.notice()
        self.assertIn("All rights reserved", text)
        self.assertIn("support@cadetfoundry.org", text)
        self.assertIn("U.S. government", text)                  # manuals and videos aren't claimed
        self.assertIn("Create a Cadet flash drive", text)       # Cadet drives are allowed


class HomeAndBackupTests(unittest.TestCase):
    def test_backups_only_on_a_trusted_computer_newest_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, home = Path(tmp) / "data", Path(tmp) / "home"
            (data / "profiles" / "abc").mkdir(parents=True)
            (data / "profiles.json").write_text("{}")
            (data / "profiles" / "abc" / "study.json").write_bytes(b"sealed")
            (data / "cadetfoundry.log").write_text("not backed up")
            with mock.patch.object(store, "DATA", data), mock.patch.object(Path, "home", lambda: home), \
                    mock.patch.object(usb_home, "home", lambda: {"where": "usb", "drive": "E:"}):
                self.assertIsNone(usb_home.backup_now())                # not asked yet: nothing
                usb_home.set_trusted(False)
                self.assertIsNone(usb_home.backup_now())                # a school computer: nothing
                usb_home.set_trusted(True)
                first = usb_home.backup_now()
                self.assertTrue(first and Path(first["file"]).exists())
                names = zipfile.ZipFile(first["file"]).namelist()
                self.assertIn("profiles/abc/study.json", names)
                self.assertNotIn("cadetfoundry.log", names)
                self.assertNotIn(usb_home.TRUST, names)
                self.assertIsNone(usb_home.backup_now())                # nothing changed
                for i in range(7):
                    (data / "profiles.json").write_text(json.dumps({"n": i}))
                    time.sleep(1.05)                                   # one file per second in the name
                    usb_home.backup_now(force=True)
                self.assertEqual(len(usb_home.backups()), usb_home.KEEP)

    def test_restore_never_overwrites_a_class_or_writes_outside_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            good = tmp / "good.zip"
            with zipfile.ZipFile(good, "w") as z:
                z.writestr("profiles.json", "{}")
                z.writestr("profiles/abc/study.json", "x")
            self.assertEqual(usb_home.restore(good, tmp / "new"), 2)
            with self.assertRaises(ValueError):
                usb_home.restore(good, tmp / "new")                    # already has a class
            bad = tmp / "bad.zip"
            with zipfile.ZipFile(bad, "w") as z:
                z.writestr("../escape.txt", "x")
            with self.assertRaises(ValueError):
                usb_home.restore(bad, tmp / "other")
            self.assertFalse((tmp / "escape.txt").exists())

    def test_a_drive_never_carries_the_installer_or_a_copier(self):
        src = (ROOT / "tools" / "make_usb.py").read_text(encoding="utf-8")
        self.assertNotIn("shutil.copy2, setup", src)
        self.assertNotIn("MAKE_BAT", src)
        self.assertIn('shutil.rmtree(drive / "Make more flash drives"', src)
        self.assertFalse((ROOT / "tools" / "clone_drive.py").exists())


if __name__ == "__main__":
    unittest.main()
