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
import os
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())   # never the real data folder
os.environ.setdefault("CADETFOUNDRY_NO_WARMUP", "1")

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

VIDEO_HARNESS = r"""
import { videoPack } from './worker.mjs';
const [goodHash, offHash, good, off] = process.argv.slice(2);
const rows = { [goodHash]: { id: 'aaa111', active: 1 }, [offHash]: { id: 'bbb222', active: 0 } };
const log = [];
const DB = {
  prepare(sql) { return { bind(...a) { return { sql, a, async first() { return rows[a[0]] || null; } }; } }; },
  async batch(stmts) { for (const s of stmts) log.push([s.sql.split(' ')[0], ...s.a.filter(x => typeof x === 'string' && x.length < 40)]); },
};
const files = { 'videos/manifest.json': '{"videos":[]}', 'videos/manifest.json.sig': 'SIG', 'videos/dvids-5.mp4.0': 'PIECE-BYTES',
  'latest.json': '{}' };
const DOWNLOADS = { async get(k) { return k in files ? { body: files[k], async text() { return files[k]; } } : null; } };
const env = { DB, DOWNLOADS };
const post = async (code, file) => {
  const r = await videoPack(new Request('https://cadetfoundry.org/video-pack', { method: 'POST', body: JSON.stringify({ code, file }) }), env);
  return [r.status, await r.text()];
};
const out = {};
out.manifest = await post(good, 'manifest');
out.piece = await post(good, 'dvids-5.mp4.0');
out.wrong = await post('WRONG-CODE1', 'manifest');
out.off = await post(off, 'manifest');
out.escape = await post(good, '../latest.json');
out.other = await post(good, 'CadetFoundry-Setup-9.9.9.exe');
out.latest = await post(good, 'latest.json');
out.gone = await post(good, 'dvids-6.mp4.0');
out.log = log;
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

    def test_the_video_pack_needs_a_code_and_serves_only_its_own_files(self):
        good, off = pilot_access.new_code(), pilot_access.new_code()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copy(ROOT / "site" / "worker.js", tmp / "worker.mjs")
            (tmp / "harness.mjs").write_text(VIDEO_HARNESS, encoding="utf-8")
            r = subprocess.run(["node", "harness.mjs", pilot_access.code_hash(good), pilot_access.code_hash(off), good, off],
                               cwd=tmp, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(out["manifest"][0], 200)
        self.assertEqual(json.loads(out["manifest"][1]), {"manifest": '{"videos":[]}', "sig": "SIG"})
        self.assertEqual(out["piece"], [200, "PIECE-BYTES"])
        self.assertEqual(out["wrong"], [403, '{"error":"bad"}'])
        self.assertEqual(out["off"], [403, '{"error":"off"}'])
        for k in ("escape", "other", "latest"):                       # only video pieces, never other bucket files
            self.assertEqual(out[k][0], 400, k)
        self.assertEqual(out["gone"], [404, '{"error":"missing"}'])
        self.assertEqual([x[0] for x in out["log"]], ["INSERT", "UPDATE"])   # the list counts once; pieces don't
        self.assertIn("videos", out["log"][0])

    def test_setup_says_plainly_when_r2_is_off_and_changes_nothing(self):
        # what the owner saw on 2026-10-12: wrangler's emoji output, and R2 not switched on for the account
        from unittest import mock
        out = subprocess.CompletedProcess("x", 1, " ⛅️ wrangler\n", "✘ [ERROR] Please enable R2 through the Cloudflare Dashboard. [code: 10042]")
        toml = (ROOT / "site" / "wrangler.toml").read_text(encoding="utf-8")
        with mock.patch.object(pilot_access.subprocess, "run", return_value=out) as run, \
                mock.patch("builtins.print") as said:
            self.assertEqual(pilot_access.setup(), 1)
        self.assertEqual(run.call_count, 1)                                  # stopped at the bucket: no database made
        self.assertTrue(any("R2 isn't switched on" in str(c) for c in said.call_args_list))
        self.assertEqual((ROOT / "site" / "wrangler.toml").read_text(encoding="utf-8"), toml)

    def test_codes_are_hard_to_guess_and_easy_to_read(self):
        codes = {pilot_access.new_code() for _ in range(200)}
        self.assertEqual(len(codes), 200)
        for c in codes:
            self.assertRegex(c, r"^[A-HJ-KM-NP-Z2-9]{5}-[A-HJ-KM-NP-Z2-9]{5}$")   # no I, L, O, 0 or 1


if __name__ == "__main__":
    unittest.main()
