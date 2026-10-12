"""Downloads with an access code (owner, 2026-10-12): site/worker.js run under Node against stand-ins for Cloudflare's
D1 and R2 -- a right code downloads and is counted, a wrong or switched-off code gets nothing, and the code is only ever
compared as a hash. Skipped when Node isn't installed."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import pilot_access  # noqa: E402

HARNESS = r"""
import { download, normCode, sha256hex } from './worker.mjs';
const [goodHash, offHash] = process.argv.slice(2);
const rows = { [goodHash]: { id: 'aaa111', active: 1 }, [offHash]: { id: 'bbb222', active: 0 } };
const log = [];
const DB = {
  prepare(sql) { return { bind(...a) { return { sql, a, async first() { return rows[a[0]] || null; } }; } }; },
  async batch(stmts) { for (const s of stmts) log.push([s.sql.split(' ')[0], ...s.a.filter(x => typeof x === 'string' && x.length < 40)]); },
};
const files = { 'latest.json': JSON.stringify({ setup: 'CadetFoundry-Setup-9.9.9.exe', zip: 'CadetFoundry-9.9.9.zip', sig: 'CadetFoundry-9.9.9.zip.sig' }),
  'CadetFoundry-Setup-9.9.9.exe': 'MZ-installer' };
const DOWNLOADS = { async get(k) { return k in files ? { body: files[k], async json() { return JSON.parse(files[k]); } } : null; } };
const env = { DB, DOWNLOADS };
const post = (code, file = 'setup') => {
  const f = new FormData(); f.set('code', code); f.set('file', file);
  return download(new Request('https://cadetfoundry.org/download', { method: 'POST', body: f }), env);
};
const out = {};
let r = await post(process.argv[4]);                          // the right code, typed loosely
out.good = [r.status, r.headers.get('Content-Disposition'), await r.text()];
r = await post('WRONG-CODE1'); out.wrong = [r.status, r.headers.get('Location')];
r = await post(process.argv[5]); out.off = [r.status, r.headers.get('Location')];
r = await post(process.argv[4], 'update'); out.notReady = [r.status, r.headers.get('Location')];
r = await post(process.argv[4], '../../etc'); out.badFile = [r.status, r.headers.get('Location')];
out.log = log;
out.norm = normCode(' abcde-fghjk ');
out.hash = await sha256hex('ABCDEFGHJK');
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node"), "Node isn't installed")
class DownloadCodeTests(unittest.TestCase):
    def test_codes_open_the_download_and_nothing_else(self):
        good, off = pilot_access.new_code(), pilot_access.new_code()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copy(ROOT / "site" / "worker.js", tmp / "worker.mjs")
            (tmp / "harness.mjs").write_text(HARNESS, encoding="utf-8")
            loose = good.lower().replace("-", " ")
            r = subprocess.run(["node", "harness.mjs", pilot_access.code_hash(good), pilot_access.code_hash(off), loose, off],
                               cwd=tmp, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(out["good"][0], 200)
        self.assertIn('filename="CadetFoundry-Setup-9.9.9.exe"', out["good"][1])
        self.assertEqual(out["good"][2], "MZ-installer")
        self.assertEqual(out["wrong"], [303, "https://cadetfoundry.org/download?bad=1"])
        self.assertEqual(out["off"], [303, "https://cadetfoundry.org/download?off=1"])
        self.assertEqual(out["notReady"], [303, "https://cadetfoundry.org/download?missing=1"])
        self.assertEqual(out["badFile"], [303, "https://cadetfoundry.org/download?bad=1"])
        # one download recorded, against the right code: which code and when -- nothing else
        self.assertEqual([x[0] for x in out["log"]], ["INSERT", "UPDATE"])
        self.assertIn("aaa111", out["log"][0])
        # the site and the owner's tool read a code the same way
        self.assertEqual(out["norm"], pilot_access.norm(" abcde-fghjk "))
        self.assertEqual(out["hash"], pilot_access.code_hash("ABCDE-FGHJK"))

    def test_codes_are_hard_to_guess_and_easy_to_read(self):
        codes = {pilot_access.new_code() for _ in range(200)}
        self.assertEqual(len(codes), 200)
        for c in codes:
            self.assertRegex(c, r"^[A-HJ-KM-NP-Z2-9]{5}-[A-HJ-KM-NP-Z2-9]{5}$")   # no I, L, O, 0 or 1


if __name__ == "__main__":
    unittest.main()
