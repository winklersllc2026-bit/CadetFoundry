"""Security review, Phase 7: the safety check on Ask messages -- best-effort pattern matching, not a crisis detector.

What it does: a first-person disclosure shows help resources first and switches Ask to a short, caring reply; a
message that only mentions the topic shows a neutral help line and gets a normal answer. It notifies NO ONE and
records nothing beyond the person's own private chat. It runs on Ask messages only.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())

from vanguard import safety  # noqa: E402

DISCLOSURES = [                       # -> care: resources first, then a caring reply
    "I want to kill myself", "im gonna kms", "i want to unalive myself", "I wish I was dead",
    "I don't want to be alive anymore", "everyone would be better off without me", "there's no point in living",
    "i want to end it", "I'm not suicidal but I think about dying a lot", "i keep thinking about suicde",
    "thinking about sucide again", "i feel so suicidal", "I've been cutting myself again", "I took a bunch of pills",
    "I want to disappear forever", "im not safe at home", "I'm scared to go home tonight",
    "my stepdad hits me", "my dad beats me when he drinks", "someone touched me and I didn't want it",
    "I was raped", "a senior cadet keeps hazing me", "I got sexually harassed at practice", "he forced me to",
    "I KILL MYSELF IN MY HEAD EVERY NIGHT",            # capitals
]
TOPIC_ONLY = [                        # -> a neutral help line, then a normal answer (not care mode)
    "what's the punishment for hazing in the army", "can you explain the suicide prevention brief",
    "what does SHARP say about sexual harassment", "what is the 988 number for",
]
NOTHING = [                           # ordinary language that must not trigger anything
    "this homework is killing me", "I killed it on the PT test", "the mile run almost killed me lol",
    "how do I cut my hair to regulation", "I'm dying to know my score", "we shot the targets at the range",
    "my dad drove me to practice", "my team beat us in the drill meet", "hit me with the next question",
]
KNOWN_MISSES = [                      # indirect wording a pattern can't catch -- documented, not hidden
    "I just want everything to stop", "what's the most painless way", "I gave away my things today",
    "this is my last week", "nobody notices me anyway",
]


class SafetyCheckTests(unittest.TestCase):
    def test_first_person_disclosures_show_help_first_and_switch_to_care(self):
        for text in DISCLOSURES:
            with self.subTest(text=text):
                c = safety.check(text)
                self.assertTrue(c["care"])
                self.assertTrue("988" in c["banner"] or "RAINN" in c["banner"] or "Childhelp" in c["banner"])
                self.assertIn("911", c["banner"])

    def test_the_topic_alone_gets_a_neutral_line_and_a_normal_answer(self):
        for text in TOPIC_ONLY:
            with self.subTest(text=text):
                c = safety.check(text)
                self.assertFalse(c["care"])
                self.assertEqual(c["banner"], safety.TOPIC_BANNER)

    def test_everyday_language_triggers_nothing(self):
        for text in NOTHING:
            with self.subTest(text=text):
                c = safety.check(text)
                self.assertFalse(c["care"])
                self.assertEqual(c["banner"], "")

    def test_known_misses_are_known(self):
        """Pattern matching can't read intent or indirect wording. If one of these starts being caught, move it up."""
        for text in KNOWN_MISSES:
            self.assertFalse(safety.check(text)["care"], text)

    def test_the_resources_work_without_internet(self):
        for banner in (safety.CRISIS_BANNER, safety.ASSAULT_BANNER, safety.CARE_FALLBACK, safety.TOPIC_BANNER):
            self.assertNotIn("http", banner)               # phone numbers and plain words, no links to load
        self.assertIn("988", safety.CRISIS_BANNER)
        self.assertIn("741741", safety.CRISIS_BANNER)


if __name__ == "__main__":
    unittest.main()
