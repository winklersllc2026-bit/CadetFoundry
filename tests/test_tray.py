"""The taskbar icon (owner, 2026-10-12): it appears while Cadet Foundry runs, a click opens it, Quit closes it, and it's
gone afterwards. Uses the real Windows notification area; skipped elsewhere."""
import sys
import threading
import time
import unittest
from pathlib import Path
import os
import tempfile
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())   # never the real data folder
os.environ.setdefault("CADETFOUNDRY_NO_WARMUP", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cadetfoundry import tray  # noqa: E402


@unittest.skipUnless(sys.platform == "win32", "Windows only")
class TrayTests(unittest.TestCase):
    def test_click_opens_quit_quits_and_the_icon_goes_away(self):
        opened, quit_ = threading.Event(), threading.Event()
        icon = tray.Tray(opened.set, quit_.set, "Cadet Foundry is running (test)")
        self.assertTrue(icon.start(), "the icon couldn't be added to the notification area")
        thread = next(t for t in threading.enumerate() if t.name == "tray")
        # a click on the icon, as Windows sends it
        tray.user32.PostMessageW(icon.hwnd, tray.WM_TRAY, 0, tray.WM_LBUTTONUP)
        self.assertTrue(opened.wait(5))
        icon._command(tray.ID_QUIT)                       # "Quit Cadet Foundry" from the right-click menu
        self.assertTrue(quit_.is_set())
        icon.set_tip("Cadet Foundry is running (test, renamed)")
        icon.stop()
        thread.join(5)
        self.assertFalse(thread.is_alive())               # its window closed and the icon was removed

    def test_never_on_other_systems_or_quiet_starts(self):
        src = (ROOT / "run.py").read_text(encoding="utf-8")
        self.assertIn('if sys.platform != "win32" or quiet or sample.ACTIVE or os.environ.get("CADETFOUNDRY_NO_TRAY")', src)


if __name__ == "__main__":
    unittest.main()
