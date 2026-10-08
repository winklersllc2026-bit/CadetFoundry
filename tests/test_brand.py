"""Vanguard carries no trace of the product it was copied from (owner's rule, 2026-10-08)."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD = re.compile(r"cursiv|recruit(?!er|ing|ment)", re.I)       # "recruiter"/"recruiting" are ordinary words
# Phase 0 planning docs still describe the inherited layout; they are rewritten at the end of Phase 1.
ALLOWED = {"HANDOFF.md", "ARCHITECTURE.md", "REUSE_PLAN.md", "MIGRATION_PLAN.md", "tests/test_brand.py"}


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
