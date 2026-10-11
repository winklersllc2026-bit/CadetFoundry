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

    def test_people_never_see_the_name_before_the_rename(self):
        """Renamed from Vanguard to Cadet Foundry (owner, 2026-10-11). The app keeps a few internal names on purpose --
        the vanguard/ code folder, the Vanguard/ folder inside update zips (0.2.3-0.2.4 updaters require it), the
        .vanguard and VanguardData data folders -- but nothing a person reads may say Vanguard."""
        internal = re.compile(r"Vanguard(?=[/\\])|VanguardData|Vanguard-releases|winklersllc2026-bit/Vanguard|Vanguard-Setup-latest|"
                              r"StopVanguard|RemoveOldVanguard|Name = 'Vanguard'|exactly \"Vanguard\"|"
                              r"\"Start Vanguard|'Vanguard \(classroom\)|Vanguard\.lnk|Vanguard Classroom\.lnk|Install Vanguard\*|"
                              r"server_version = \"Vanguard\"|startswith\(\"Vanguard\"\)|/ \"Vanguard\"|Vanguard 0\.1\.0|"
                              r"before the rename|this app's name before")
        seen = [ROOT / "web" / "index.html", ROOT / "web" / "join.html", ROOT / "web" / "manifest.webmanifest",
                *(ROOT / "web" / "js").glob("*.js"), *(ROOT / "vanguard" / "legal").glob("*.md"),
                ROOT / "README.md", ROOT / "site" / "build.py", ROOT / "site" / "installer.iss",
                ROOT / "tools" / "make_usb.py", *(ROOT / "vanguard" / "scenarios").glob("*.md"),
                *(ROOT / "vanguard" / "cards").glob("*.md"), ROOT / "vanguard" / "brain.py", ROOT / "vanguard" / "safety.py"]
        hits = [f"{p.relative_to(ROOT)}:{i}" for p in seen for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                if re.search(r"\bVanguard\b|\bVANGUARD\b(?!_)", internal.sub("", line))]
        self.assertEqual(hits, [], "the old name is still visible")


if __name__ == "__main__":
    unittest.main()
