"""The rename (0.2.6): a computer, USB drive or backup made before it keeps working. Data folders move to their new
names (nothing copied, nothing lost), and backups made before the rename still restore."""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())

from cadetfoundry import backup, program_backup, store, vault  # noqa: E402

OLD = backup.OLD


class DataFolderMoveTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, True)

    def folder(self):
        with mock.patch.dict(os.environ, {"CADETFOUNDRY_DATA": ""}), mock.patch.object(Path, "home", lambda: self.home):
            return store._data_folder()

    def test_the_old_folder_moves_to_the_new_name_with_everything_in_it(self):
        old = self.home / store.OLD_DATA_FOLDER
        (old / "profiles" / "abc").mkdir(parents=True)
        (old / "profiles.json").write_text('{"profiles": []}', encoding="utf-8")
        got = self.folder()
        self.assertEqual(got, self.home / ".cadetfoundry")
        self.assertTrue((got / "profiles.json").exists() and (got / "profiles" / "abc").is_dir())
        self.assertFalse(old.exists())                                 # moved, not copied

    def test_a_new_folder_wins_and_the_old_one_is_left_alone(self):
        (self.home / ".cadetfoundry").mkdir()
        (self.home / store.OLD_DATA_FOLDER).mkdir()
        self.assertEqual(self.folder(), self.home / ".cadetfoundry")
        self.assertTrue((self.home / store.OLD_DATA_FOLDER).exists())

    def test_if_it_cant_move_it_is_used_where_it_is(self):
        old = self.home / store.OLD_DATA_FOLDER
        old.mkdir()
        with mock.patch.object(Path, "rename", side_effect=OSError("in use")):
            self.assertEqual(self.folder(), old)

    def test_a_fresh_computer_gets_the_new_folder(self):
        self.assertEqual(self.folder(), self.home / ".cadetfoundry")


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class OldBackupTests(unittest.TestCase):
    def no_profile_files(self):
        return mock.patch.multiple(store, read_json=lambda name, default=None: default, read_lines=lambda name: [])

    def test_a_personal_backup_from_before_the_rename_still_opens(self):
        with self.no_profile_files():
            sealed = backup.export_sealed("cadet", "correct horse battery")
        self.assertIn("cadetfoundry_backup_sealed", sealed)                    # new backups carry the new name
        old = {(k.replace("cadetfoundry", OLD) if k.startswith("cadetfoundry") else k): v for k, v in sealed.items()}
        data = backup.open_any(old, "correct horse battery")
        self.assertEqual(data["cadetfoundry_backup"], backup.VERSION)

    def test_a_personal_backup_file_written_before_the_rename_restores(self):
        with self.no_profile_files():
            made = backup.export("cadet")
        self.assertEqual(made["cadetfoundry_backup"], backup.VERSION)
        old = {(OLD + "_backup" if k == "cadetfoundry_backup" else k): v for k, v in made.items()}
        with mock.patch.object(store, "write_json"), mock.patch.object(store, "write_lines"):
            self.assertIn("restored", backup.restore(old))
        with self.assertRaises(ValueError):
            backup.restore({"something_else": 1})

    def test_a_program_backup_from_before_the_rename_is_recognised(self):
        payload = json.dumps({OLD + "_program_backup": program_backup.VERSION, "files": {}}).encode("utf-8")
        for marker in (OLD, "cadetfoundry"):
            box = {marker + "_program_backup_sealed": program_backup.VERSION, **vault.seal_backup(payload, "correct horse battery")}
            with self.assertRaises(ValueError) as e:                       # stops at the password: it IS a backup
                program_backup.restore(box, "wrong password entirely")
            self.assertIn("password", str(e.exception))
        with self.assertRaises(ValueError) as e:
            program_backup.restore({"other": 1}, "x")
        self.assertIn("isn't", str(e.exception))


class UsbLayoutTests(unittest.TestCase):
    def test_a_drive_from_before_the_rename_is_recognised(self):
        src = (ROOT / "tools" / "make_usb.py").read_text(encoding="utf-8")
        self.assertIn('("VanguardData", "Cadet Foundry Data")', src)       # the data folder is renamed, not copied
        self.assertIn('OLD_APP_ITEMS = ["vanguard"', src)                  # old code left in the app folder is removed
        clone = importlib.import_module("tools.clone_drive") if (ROOT / "tools" / "__init__.py").exists() else None
        text = (ROOT / "tools" / "clone_drive.py").read_text(encoding="utf-8")
        self.assertIn('"VanguardData"', text)                              # a Cadet copy never takes an old data folder
        del clone


if __name__ == "__main__":
    unittest.main()
