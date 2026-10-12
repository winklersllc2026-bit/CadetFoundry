"""Security review, Phase 6: third-party code is fixed in version and fingerprint, and a changed file is refused."""
import hashlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())

from cadetfoundry import addons  # noqa: E402

BUILD = (ROOT / "site" / "build.py").read_text(encoding="utf-8")
REQS = (ROOT / "site" / "bundle-requirements.txt").read_text(encoding="utf-8")


class PinnedDependencyTests(unittest.TestCase):
    def test_bundled_packages_are_exact_versions_with_hashes(self):
        entries = re.findall(r"^([A-Za-z0-9_.-]+)(\S*) \\\n\s+--hash=sha256:([0-9a-f]{64})$", REQS, re.M)
        self.assertEqual({e[0] for e in entries}, {"cryptography", "cffi", "pycparser"})
        for name, spec, _ in entries:
            self.assertRegex(spec, r"^==\d", name)
        self.assertIn('"--require-hashes", "-r", str(PYTHON_REQUIREMENTS)', BUILD)

    def test_bundled_python_and_deploy_tool_are_fixed_versions(self):
        self.assertRegex(BUILD, r'PYTHON_EMBED = \("https://www\.python\.org/ftp/python/(\d+\.\d+\.\d+)/python-\1-embed'
                                r'-amd64\.zip",\s+"[0-9a-f]{64}"\)')
        self.assertRegex(BUILD, r'WRANGLER = "\d+\.\d+\.\d+"')
        self.assertNotIn("npx --yes wrangler deploy", BUILD)

    def test_add_on_downloads_are_fixed_versions_with_hashes(self):
        for url, sha in (addons.PIP_PYZ, addons.VOICE_MODEL):
            self.assertTrue(url.startswith("https://"))
            self.assertRegex(url, r"\d+\.\d+")                   # a versioned file, not "latest"
            self.assertRegex(sha, r"^[0-9a-f]{64}$")
        self.assertRegex(addons.VOSK, r"^vosk==\d+\.\d+\.\d+$")

    def test_a_download_that_doesnt_match_its_fingerprint_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.bin"
            src.write_bytes(b"the real file")
            url = src.as_uri()
            good = hashlib.sha256(b"the real file").hexdigest()
            dest = Path(tmp) / "out.bin"
            addons._download(url, dest, "test", 0, 1, sha256=good)
            self.assertEqual(dest.read_bytes(), b"the real file")
            with self.assertRaises(RuntimeError):
                addons._download(url, dest, "test", 0, 1, sha256="0" * 64)
            self.assertFalse(dest.exists())                     # the mismatched file isn't left behind


if __name__ == "__main__":
    unittest.main()
