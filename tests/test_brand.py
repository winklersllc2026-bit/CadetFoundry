"""Vanguard carries no trace of the product it was copied from (owner's rule, 2026-10-08)."""
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
ALLOWED = {"docs/history/HANDOFF.md", "docs/history/REUSE_PLAN.md", "docs/history/MIGRATION_PLAN.md", "tests/test_brand.py"}


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


if __name__ == "__main__":
    unittest.main()
