"""0.2.2: "Make more flash drives" -- a Cadet drive gets the app but never anyone's profiles or class records."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import clone_drive  # noqa: E402


class CloneDriveTests(unittest.TestCase):
    def make_source(self) -> Path:
        src = Path(tempfile.mkdtemp())
        (src / "Vanguard" / "tools").mkdir(parents=True)
        (src / "Vanguard" / "run.py").write_text("print('vanguard')")
        (src / "Vanguard" / "videos").mkdir()
        (src / "Vanguard" / "videos" / "dvids-1.mp4").write_bytes(b"x" * 1000)
        (src / "Start Vanguard.bat").write_text("@echo off")
        (src / "Make more flash drives").mkdir()
        (src / "Make more flash drives" / "HOW TO MAKE MORE DRIVES.txt").write_text("how")
        (src / "VanguardData" / "profiles" / "abc123").mkdir(parents=True)      # the instructor's class: never copied
        (src / "VanguardData" / "profiles" / "abc123" / "security.json").write_text("{}")
        return src

    def test_copies_the_app_but_never_vanguarddata(self):
        src, dest = self.make_source(), Path(tempfile.mkdtemp())
        with mock.patch("builtins.print"):
            self.assertEqual(clone_drive.main([str(src), str(dest)]), 0)
        self.assertTrue((dest / "Vanguard" / "run.py").exists())
        self.assertTrue((dest / "Vanguard" / "videos" / "dvids-1.mp4").exists())
        self.assertTrue((dest / "Start Vanguard.bat").exists())
        self.assertTrue((dest / "Make more flash drives" / "HOW TO MAKE MORE DRIVES.txt").exists())
        self.assertTrue((dest / "VanguardData").is_dir())                       # there, and empty
        self.assertEqual(list((dest / "VanguardData").iterdir()), [])

    def test_never_overwrites_a_drive_with_profiles(self):
        src, dest = self.make_source(), Path(tempfile.mkdtemp())
        (dest / "VanguardData" / "profiles" / "someone").mkdir(parents=True)
        with mock.patch("builtins.print"):
            self.assertEqual(clone_drive.main([str(src), str(dest)]), 1)
        self.assertFalse((dest / "Vanguard").exists())

    def test_refuses_a_folder_that_isnt_a_vanguard_copy(self):
        with mock.patch("builtins.print"):
            self.assertEqual(clone_drive.main([tempfile.mkdtemp(), tempfile.mkdtemp()]), 1)


if __name__ == "__main__":
    unittest.main()
