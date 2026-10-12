"""Cadet Foundry carries no trace of the product it was copied from (owner's rule, 2026-10-08)."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The old product name was "Cursiv" / "Cursiv Recruit". Lower-case "recruit" (and recruits, recruiter, recruit
# training) is an ordinary military word every service uses; capital-R "Recruit" on its own is flagged, except in
# "Seaman Recruit", the Navy's E-1 rank (defense.gov), and "Recruit Training".
OLD = re.compile(r"(?i:cursiv)|(?<!Seaman )Recruit(?![ _-]?[Tt]raining)")
# Historical planning notes from the fork (docs/history/) describe the earlier product by name, on purpose.
ALLOWED = {"docs/history/HANDOFF.md", "docs/history/REUSE_PLAN.md", "docs/history/MIGRATION_PLAN.md", "tests/test_brand.py",
           "tests/test_rename.py",                     # checks that old computers, drives and backups still move over
           "tests/test_download.py"}                   # makes sure an old data folder never ships in a download


class BrandTests(unittest.TestCase):
    def test_no_old_product_name_in_tracked_files(self):
        try:
            tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        hits = []
        for name in tracked:
            if name in ALLOWED or OLD.search(name):
                hits += [name] if name not in ALLOWED else []
                continue
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            hits += [f"{name}:{i}" for i, line in enumerate(text.splitlines(), 1) if OLD.search(line)]
        self.assertEqual(hits, [], "old product name found")

    def test_the_name_before_the_rename_is_gone(self):
        """Renamed from Vanguard to Cadet Foundry (owner, 2026-10-11), inside and out (0.2.6). The old name may appear
        only where a computer, drive or backup from before the rename is recognised and moved over, plus three things
        outside the app: the owner's release-key folder, the website Worker's internal name, and the old web address
        (which forwards)."""
        moving_over = re.compile(
            r"\.vanguard-release|vanguard-site|vanguard\.winklers-llc\.com|Vanguard-releases|winklersllc2026-bit/Vanguard\b|"
            r"OLD_LATEST = \"Vanguard-Setup-latest\.exe\"|OLD_LATEST|Vanguard\*\\n|OLD_DATA_FOLDER = \"\.vanguard\"|OLD_DATA_FOLDER|OLD_APP_ITEMS = .*|OLD = \"vanguard\"|data\.vanguard_backup_sealed|"
            r"\"VanguardData\"|\(\"Vanguard\", \"Cadet Foundry\"\)|Install Vanguard\*|\"Start Vanguard|start-vanguard-usb\.sh|"
            r"\\\.vanguard\\vanguard\.pid|\{app\}\\vanguard|\{app\}\\(start|install)-vanguard|Vanguard( Classroom)?\.lnk|"
            r"b\"vanguard (data key|backup|box\||program data)\"|FILE-FORMAT LABELS.*|vanguard program data\" below.*|" 
            r"Name = 'Vanguard'|exactly \"Vanguard\"|Vanguard 0\.1\.0|before the rename|formerly Vanguard|renamed from Vanguard",
            re.I)
        try:
            tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        hits = []
        for name in tracked:
            if name in ALLOWED or name.startswith(("library/", "books/", "docs/history/", "tests/fixtures/")) \
                    or name == "docs/SECURITY_REVIEW_2026-10.md":           # a dated record, left as written
                continue
            if "vanguard" in name.lower():
                hits.append(name)
                continue
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            hits += [f"{name}:{i}" for i, line in enumerate(text.splitlines(), 1)
                     if re.search(r"vanguard", moving_over.sub("", line), re.I)]
        self.assertEqual(hits, [], "the old name is still here")


if __name__ == "__main__":
    unittest.main()
