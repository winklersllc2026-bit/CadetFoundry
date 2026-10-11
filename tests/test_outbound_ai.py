"""Security review, Phase 7: what can leave the device through online AI.

Online AI is off unless an operator turns it on in config.json with a provider key. Even then (2026-10-11):
  * only Ask's ordinary answers may go online, and without the Cadet's profile, remembered facts, logbook or earlier
    chat -- just the question, the public library passages and Vanguard's rules;
  * a message that shows signs of crisis or harm never goes online;
  * grading (which carries answer keys), memory learning and letters never go online.
Before this, every AI call tried the online provider first, with the full personal context.
"""
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import board, engine, profiles, store  # noqa: E402
from vanguard.brain import Brain  # noqa: E402
from vanguard.knowledge import Library  # noqa: E402

ONLINE = {"online": True, "groq_key": "test-key-not-real", "ai_mode": "ai"}


class OutboundAITests(unittest.TestCase):
    lib = Library(cache_dir=Path(os.environ["VANGUARD_DATA"]))

    def setUp(self):
        self.sent = []                                    # everything the "online provider" received
        self.p = profiles.create(f"Cadet Outbound-{uuid.uuid4().hex[:6]}")
        self.tok = store.use_profile(profiles.folder(self.p["id"]))
        store.save_profile({"name": "Jordan Ellis", "grade": "10", "goals": "Make the drill team"})
        store.remember("Jordan's little brother is in the hospital")
        store.add_history("user", "my secret earlier question about home")
        store.add_history("assistant", "an earlier answer")

        def groq(messages, key, max_tokens):
            self.sent.append(messages)
            return "Online answer."

        def ollama(messages, max_tokens):
            yield "Local answer."
        self.patches = [mock.patch.object(engine, "_groq", groq), mock.patch.object(engine, "_ollama", ollama),
                        mock.patch.object(Brain, "_learn", lambda *a: None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.reset_profile(self.tok)
        profiles.delete(self.p["id"])

    def config(self, cfg):
        return mock.patch.object(store, "config", lambda: {**store.DEFAULT_CONFIG, **cfg}
                                 if hasattr(store, "DEFAULT_CONFIG") else dict(cfg))

    def ask(self, text):
        with mock.patch.object(store, "ai_mode", lambda: "ai"):
            return "".join(e.get("t", "") for e in Brain(self.lib).chat(text))

    def test_nothing_goes_online_when_online_ai_is_off(self):
        with self.config({"online": False, "groq_key": "test-key-not-real"}):
            self.ask("What are the leader attributes in FM 6-22?")
            self.assertEqual(board.grade("Who salutes first?", "The junior person", "the senior one")["how"], "words")
        self.assertEqual(self.sent, [])

    def test_an_ordinary_question_goes_online_without_personal_context(self):
        with self.config(ONLINE):
            self.ask("What are the leader attributes in FM 6-22?")
        self.assertEqual(len(self.sent), 1)
        everything = " ".join(m["content"] for m in self.sent[0])
        for private in ("Jordan Ellis", "drill team", "little brother", "my secret earlier question", "an earlier answer",
                        "## The Cadet", "What you remember"):
            self.assertNotIn(private, everything)
        self.assertIn("What are the leader attributes", everything)

    def test_a_crisis_message_never_goes_online(self):
        with self.config(ONLINE):
            out = self.ask("I don't want to live anymore")
        self.assertEqual(self.sent, [])
        self.assertIn("988", out)                          # help is still shown first, offline

    def test_grading_and_background_jobs_never_go_online(self):
        with self.config(ONLINE):
            board.grade("Who salutes first?", "The junior person", "whoever is lower in rank")   # carries the answer key
            engine.quick([{"role": "user", "content": "remember this"}])
            "".join(engine.stream([{"role": "user", "content": "draft my letter"}]))            # letters, simplify: default
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
