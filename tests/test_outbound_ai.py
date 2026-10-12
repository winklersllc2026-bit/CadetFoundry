"""Nothing goes online (owner, 2026-10-12). Cadet Foundry once let an operator switch on an online AI provider (Groq or
Gemini) in config.json. Cadets are minors, so that option is gone: the only AI is the one on this computer (Ollama at
127.0.0.1), and a config.json that still holds an old key or "online": true changes nothing.
"""
import os
import sys
import tempfile
import unittest
import urllib.request
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
os.environ["CADETFOUNDRY_NO_WARMUP"] = "1"

from cadetfoundry import board, engine, profiles, store  # noqa: E402
from cadetfoundry.brain import Brain  # noqa: E402
from cadetfoundry.knowledge import Library  # noqa: E402

OLD_ONLINE = {"online": True, "groq_key": "test-key-not-real", "gemini_key": "test-key-not-real", "ai_mode": "ai"}


class NothingGoesOnlineTests(unittest.TestCase):
    lib = Library(cache_dir=Path(os.environ["CADETFOUNDRY_DATA"]))

    def setUp(self):
        self.urls = []                                    # every address Cadet Foundry tried to reach

        def watch(req, *a, **k):
            self.urls.append(req.full_url if hasattr(req, "full_url") else str(req))
            raise OSError("no network in this test")
        self.p = profiles.create(f"Cadet Offline-{uuid.uuid4().hex[:6]}")
        self.tok = store.use_profile(profiles.folder(self.p["id"]))
        self.patches = [mock.patch.object(urllib.request, "urlopen", watch),
                        mock.patch.object(store, "config", lambda: dict(OLD_ONLINE)),
                        mock.patch.object(Brain, "_learn", lambda *a: None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.reset_profile(self.tok)
        profiles.delete(self.p["id"])

    def test_only_this_computer_is_ever_contacted(self):
        with mock.patch.object(store, "ai_mode", lambda: "ai"):
            "".join(e.get("t", "") for e in Brain(self.lib).chat("What are the leader attributes in FM 6-22?"))
            "".join(e.get("t", "") for e in Brain(self.lib).chat("I don't want to live anymore"))
        board.grade("Who salutes first?", "The junior person", "whoever is lower in rank")
        engine.quick([{"role": "user", "content": "remember this"}])
        self.assertTrue(self.urls)                         # it did try the offline AI...
        for url in self.urls:                              # ...and nothing else
            self.assertTrue(url.startswith("http://127.0.0.1:11434/"), url)

    def test_no_online_settings_remain(self):
        self.assertNotIn("online_enabled", engine.status())
        self.assertFalse(hasattr(engine, "online_ready"))
        for name in ("_groq", "_gemini", "GROQ_URL", "GEMINI_URL"):
            self.assertFalse(hasattr(engine, name), name)

    def test_saving_settings_drops_old_keys(self):
        with mock.patch.object(store, "write_json") as w:
            store.save_config({"ai_mode": "library"})
        saved = w.call_args[0][1]
        for k in ("online", "groq_key", "gemini_key"):
            self.assertNotIn(k, saved)

    def test_the_engine_file_names_no_outside_address(self):
        text = (ROOT / "cadetfoundry" / "engine.py").read_text(encoding="utf-8")
        self.assertNotIn("https://", text)


if __name__ == "__main__":
    unittest.main()
