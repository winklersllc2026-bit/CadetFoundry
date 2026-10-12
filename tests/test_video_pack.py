"""The official-video pack (owner, 2026-10-12): tools/video_pack.py splits and signs the videos; Me -> Add-ons downloads
them with the access code against a stand-in for cadetfoundry.org. A right code saves every video byte for byte; a
wrong code, an unsigned list or a tampered piece saves nothing; a stopped download carries on; Remove deletes them."""
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())   # never the real data folder
os.environ.setdefault("CADETFOUNDRY_NO_WARMUP", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from cadetfoundry import addons, videos  # noqa: E402
import video_pack  # noqa: E402

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:                                     # pragma: no cover
    Ed25519PrivateKey = None

CODE = "ABCDE-FGHJK"
CATALOG = [{"id": "dvids-11", "kind": "dvids", "title": "One"}, {"id": "dvids-22", "kind": "dvids", "title": "Two"},
           {"id": "yt-1", "kind": "youtube", "title": "Link"}]


class Site(http.server.BaseHTTPRequestHandler):
    """POST /video-pack, like site/worker.js: {code, file} -> the signed list, or one piece."""
    out: Path = Path(".")
    asked: list = []
    tamper: str = ""

    def log_message(self, *a):
        pass

    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).asked.append(b["file"])
        if b["code"] != CODE.replace("-", ""):
            return self._send(403, json.dumps({"error": "bad"}).encode())
        if b["file"] == "manifest":
            return self._send(200, json.dumps({"manifest": (self.out / "manifest.json").read_text(encoding="utf-8"),
                                               "sig": (self.out / "manifest.json.sig").read_text()}).encode())
        data = (self.out / b["file"]).read_bytes()
        if b["file"] == self.tamper:
            data = b"X" + data[1:]
        self._send(200, data)

    def _send(self, code, body):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@unittest.skipIf(Ed25519PrivateKey is None, "cryptography not installed")
class VideoPackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src, self.out, self.dest = self.tmp / "src", self.tmp / "out", self.tmp / "dest"
        self.src.mkdir()
        self.originals = {"dvids-11": os.urandom(2500), "dvids-22": os.urandom(900)}
        for vid, data in self.originals.items():
            (self.src / f"{vid}.mp4").write_bytes(data)
        self.key = Ed25519PrivateKey.generate()
        patches = [mock.patch.object(videos, "catalog", lambda: [dict(v) for v in CATALOG]),
                   mock.patch.object(video_pack, "PIECE", 1000),
                   mock.patch.object(videos, "VIDEOS", self.src)]
        for p in patches:
            p.start()
        self.manifest = video_pack.make(self.src, self.out, key=self.key)
        patches[-1].stop()
        self.addCleanup(lambda: [p.stop() for p in patches[:-1]])
        Site.out, Site.asked, Site.tamper = self.out, [], ""
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        for p in (mock.patch.object(addons, "SITE", f"http://127.0.0.1:{self.httpd.server_address[1]}"),
                  mock.patch.object(addons, "_KEY", self.key.public_key()),
                  mock.patch.object(videos, "VIDEOS", self.dest)):
            p.start()
            self.addCleanup(p.stop)

    def saved(self):
        return sorted(f.name for f in self.dest.glob("*.mp4"))

    def test_the_pack_is_split_listed_and_signed(self):
        self.assertEqual([v["id"] for v in self.manifest["videos"]], ["dvids-11", "dvids-22"])   # no YouTube links
        self.assertEqual([p["name"] for p in self.manifest["videos"][0]["pieces"]],
                         ["dvids-11.mp4.0", "dvids-11.mp4.1", "dvids-11.mp4.2"])
        self.assertTrue((self.out / "manifest.json.sig").exists())

    def test_a_right_code_saves_every_video_exactly(self):
        self.assertEqual(addons._install_videos("abcde fghjk"), 2)           # typed loosely
        for vid, data in self.originals.items():
            self.assertEqual((self.dest / f"{vid}.mp4").read_bytes(), data)
        self.assertFalse((self.dest / ".download").exists())
        self.assertEqual(videos.listing()["saved"], 2)
        Site.asked.clear()
        addons._install_videos(CODE)                                         # nothing new: only the list is asked for
        self.assertEqual(Site.asked, ["manifest"])

    def test_a_wrong_code_saves_nothing_and_says_so_plainly(self):
        with self.assertRaisesRegex(RuntimeError, "access code isn't right"):
            addons._install_videos("WRONG-CODE9")
        self.assertEqual(self.saved(), [])

    def test_a_list_not_signed_by_the_project_is_refused(self):
        with mock.patch.object(addons, "_KEY", Ed25519PrivateKey.generate().public_key()):
            with self.assertRaisesRegex(RuntimeError, "isn't signed"):
                addons._install_videos(CODE)
        self.assertEqual(Site.asked, ["manifest"])                           # not one piece was fetched
        self.assertEqual(self.saved(), [])

    def test_a_tampered_piece_is_refused_and_a_retry_carries_on(self):
        Site.tamper = "dvids-11.mp4.1"
        with self.assertRaisesRegex(RuntimeError, "fingerprint"):
            addons._install_videos(CODE)
        self.assertEqual(self.saved(), [])
        self.assertTrue((self.dest / ".download" / "dvids-11.mp4.0").exists())   # the good piece is kept
        Site.tamper, Site.asked = "", []
        addons._install_videos(CODE)
        self.assertNotIn("dvids-11.mp4.0", Site.asked)                       # not downloaded twice
        self.assertEqual(self.saved(), ["dvids-11.mp4", "dvids-22.mp4"])

    def test_a_video_dvids_removed_is_deleted_here_too(self):
        self.dest.mkdir()
        (self.dest / "dvids-22.mp4").write_bytes(b"old copy")
        m = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        m["status"] = {"dvids-22": {"removed": True, "checked": "2026-10-12"}}
        m["videos"] = [v for v in m["videos"] if v["id"] != "dvids-22"]
        data = json.dumps(m).encode()
        (self.out / "manifest.json").write_bytes(data)
        import base64
        (self.out / "manifest.json.sig").write_text(base64.b64encode(self.key.sign(data)).decode())
        addons._install_videos(CODE)
        self.assertEqual(self.saved(), ["dvids-11.mp4"])
        self.assertNotIn("dvids-22", [v["id"] for v in videos.listing()["videos"]])

    def test_install_needs_a_code_and_remove_deletes_them(self):
        with self.assertRaisesRegex(ValueError, "access code"):
            addons.install("videos", "")
        addons._install_videos(CODE)
        self.assertEqual(addons.status()["videos"]["saved"], 2)
        self.assertEqual(addons.remove_videos()["ok"], True)
        self.assertEqual(self.saved(), [])
        self.assertFalse(addons.status()["videos"]["installed"])


if __name__ == "__main__":
    unittest.main()
