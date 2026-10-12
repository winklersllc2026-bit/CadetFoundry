"""What goes into the public download (owner's question, 2026-10-12: "no data from my computer would leak over,
right?"). The zip -- and the installer built from it -- carries the app, the manuals and the documentation: never a
data folder, a profile, a PIN or key file, a log, or the tests and their made-up fixture data."""
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))
import build  # noqa: E402

PERSONAL = re.compile(r"(^|/)(profiles\.json|profiles/|admin\.json|program\.json|security\.json|config\.json|"
                      r"cadet_drive\.json|drives\.json|instance\.id|[^/]*\.log|[^/]*\.pid|[^/]*\.pem|\.cadetfoundry|"
                      r"\.vanguard|Cadet Foundry Data|chats\.json|memory\.jsonl|program/sync/)", re.I)


class DownloadTests(unittest.TestCase):
    def test_the_download_holds_no_ones_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "download.zip"
            build.make_zip(z)
            names = zipfile.ZipFile(z).namelist()
        self.assertTrue(any(n.endswith("cadetfoundry/server.py") for n in names))            # the app is there
        self.assertEqual([n for n in names if "/tests/" in n], [])                           # no tests, no fixtures
        self.assertEqual([n for n in names if PERSONAL.search(n.split("/", 1)[1])], [])


if __name__ == "__main__":
    unittest.main()
