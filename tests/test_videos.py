"""0.2: official videos -- the catalog, offline playback with seeking, and no YouTube embedding."""
import http.client
import json
import os
import re
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
os.environ["CADETFOUNDRY_NO_WARMUP"] = "1"

from cadetfoundry import knowledge, profiles, security, store, vault, videos  # noqa: E402
from cadetfoundry.server import serve  # noqa: E402

OFFICIAL_CHANNELS = {"GoArmy", "America's Navy", "Marine Corps Recruiting", "Space Force Recruiting"}


class CatalogTests(unittest.TestCase):
    def test_every_video_is_official_and_complete(self):
        vids = videos.catalog()
        self.assertGreater(len(vids), 20)
        self.assertEqual(len({v["id"] for v in vids}), len(vids))
        for v in vids:
            with self.subTest(video=v["id"]):
                self.assertIn(v["service"], knowledge.SERVICES)
                self.assertTrue(v["title"] and v["topic"])
                if v["kind"] == "dvids":
                    self.assertEqual(v["id"], f"dvids-{v['dvids_id']}")
                    self.assertTrue(v["url"].startswith(f"https://www.dvidshub.net/video/{v['dvids_id']}/"))
                    self.assertRegex(v["length"], r"^\d{1,2}:\d{2}$")
                else:
                    self.assertEqual(v["kind"], "youtube")
                    self.assertIn(v["channel"], OFFICIAL_CHANNELS)
                    self.assertRegex(v["url"], r"^https://www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11}$")
        # Army, Navy, Air Force, Marine Corps and Space Force all have videos
        self.assertTrue({"army", "navy", "air_force", "marine_corps", "space_force"} <= {v["service"] for v in vids})

    def test_only_catalog_videos_can_be_requested(self):
        for bad in ("../run.py", "dvids-1.mp4/../x", "x.mp4", "dvids-999999999.mp4", "dvids-777200.mp4.exe"):
            self.assertIsNone(videos.path_for_request(bad), bad)

    def test_the_page_never_embeds_youtube(self):
        """An embedded YouTube player would connect every Cadet's device to Google; Cadet Foundry only links out."""
        js = (ROOT / "web" / "js" / "videos.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"<iframe|youtube\.com/embed|youtube-nocookie")
        csp = security.SECURITY_HEADERS["Content-Security-Policy"]
        self.assertNotIn("youtube", csp)


class DvidsCacheTests(unittest.TestCase):
    def test_saved_copies_follow_dvids(self):
        """DVIDS API terms (I.E, Caching): copies of removed videos are deleted, details are kept current, and files
        no longer in Cadet Foundry's list are cleaned up."""
        import io
        import urllib.error
        sys.path.insert(0, str(ROOT / "tools"))
        import fetch_videos
        tmp = Path(tempfile.mkdtemp())
        for name in ("dvids-777200.mp4", "dvids-968639.mp4", "dvids-1.mp4"):
            (tmp / name).write_bytes(b"x")

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        def fake(req, timeout=0):
            url = getattr(req, "full_url", req)
            if "video%3A968639" in url:
                raise urllib.error.HTTPError(url, 404, "gone", {}, None)
            if "video%3A777200" in url:
                return R(json.dumps({"results": {"title": "Renamed by DVIDS", "files": []}}).encode())
            if "api.dvidshub.net" in url:
                return R(json.dumps({"results": {"title": "t", "files": [{"src": "https://x/v.mp4", "width": 1280,
                                                                          "bitrate": 1500}]}}).encode())
            return R(b"VIDEO")

        with mock.patch.object(videos, "VIDEOS", tmp), mock.patch("urllib.request.urlopen", fake), \
                mock.patch("time.sleep"), mock.patch("builtins.print"):
            self.assertEqual(fetch_videos.main(["--key", "TEST"]), 0)
            listing = {v["id"]: v for v in videos.listing()["videos"]}
        self.assertFalse((tmp / "dvids-968639.mp4").exists())          # removed from DVIDS -> deleted here
        self.assertNotIn("dvids-968639", listing)                       # ...and not shown
        self.assertEqual(listing["dvids-777200"]["title"], "Renamed by DVIDS")
        self.assertFalse((tmp / "dvids-1.mp4").exists())                # not in the list -> cleaned up
        self.assertTrue((tmp / "dvids-850203.mp4").exists())             # a new one was saved


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class PlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.data = bytes(range(256)) * 400                      # a stand-in "video", 102,400 bytes
        (cls.dir / "dvids-777200.mp4").write_bytes(cls.data)
        cls.patch = mock.patch.object(videos, "VIDEOS", cls.dir)
        cls.patch.start()
        cls.httpd = serve("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        cls.httpd.RequestHandlerClass.app.port = cls.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.p = profiles.create(f"Vid-{uuid.uuid4().hex[:6]}")
        with security.as_profile(cls.p["id"]):
            assert security.set_pin("482915") is None

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.patch.stop()
        profiles.delete(cls.p["id"])

    def req(self, path, headers=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        c.request("GET", path, headers={"Host": f"127.0.0.1:{self.port}", "Cookie": cookie, **(headers or {})})
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, dict(r.getheaders()), body

    def login(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("POST", "/api/unlock", body=json.dumps({"profile": self.p["id"], "pin": "482915"}),
                  headers={"Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json"})
        r = c.getresponse()
        r.read()
        c.close()
        return r.getheader("Set-Cookie").split(";")[0]

    def test_saved_video_plays_and_seeks_only_when_signed_in(self):
        self.assertEqual(self.req("/videos/dvids-777200.mp4")[0], 401)          # locked: nothing
        ck = self.login()
        st, h, body = self.req("/videos/dvids-777200.mp4", cookie=ck)
        self.assertEqual((st, body), (200, self.data))
        self.assertEqual(h.get("Accept-Ranges"), "bytes")
        st, h, body = self.req("/videos/dvids-777200.mp4", {"Range": "bytes=1000-1999"}, ck)
        self.assertEqual((st, body, h["Content-Range"]), (206, self.data[1000:2000], f"bytes 1000-1999/{len(self.data)}"))
        st, h, body = self.req("/videos/dvids-777200.mp4", {"Range": "bytes=-100"}, ck)
        self.assertEqual((st, body), (206, self.data[-100:]))
        self.assertEqual(self.req("/videos/dvids-777200.mp4", {"Range": "bytes=999999-"}, ck)[0], 416)
        self.assertEqual(self.req("/videos/dvids-850203.mp4", cookie=ck)[0], 404)     # in the list, not saved
        listing = json.loads(self.req("/api/videos", cookie=ck)[2])
        saved = [v for v in listing["videos"] if v["local"]]
        self.assertEqual([v["id"] for v in saved], ["dvids-777200"])
        self.assertEqual(saved[0]["src"], "/videos/dvids-777200.mp4")


if __name__ == "__main__":
    unittest.main()
