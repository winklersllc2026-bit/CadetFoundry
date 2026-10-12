"""Tests never touch the real data folder (2026-10-12: a run that happened to load a file without this first filled the
owner's ~/.cadetfoundry with test profiles and a test Class PIN). The data folder is fixed when the app is first
imported, so every test file must point CADETFOUNDRY_DATA at a throwaway folder before it imports anything of the app."""
import os
import re
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())   # never the real data folder

HERE = Path(__file__).resolve().parent
APP = re.compile(r"^\s*(from|import)\s+(cadetfoundry|build|pilot_access|video_pack|make_usb|sign|run|cadet_drive)\b", re.M)


class IsolationTests(unittest.TestCase):
    def test_every_test_file_picks_a_throwaway_data_folder_first(self):
        for f in sorted(HERE.glob("test_*.py")):
            src = f.read_text(encoding="utf-8")
            with self.subTest(file=f.name):
                at = src.find('os.environ.setdefault("CADETFOUNDRY_DATA"')
                if at < 0:
                    at = src.find('os.environ["CADETFOUNDRY_DATA"] =')
                self.assertGreaterEqual(at, 0, "sets no throwaway CADETFOUNDRY_DATA")
                first = APP.search(src)
                if first:
                    self.assertLess(at, first.start(), "imports the app before choosing the data folder")


if __name__ == "__main__":
    unittest.main()
