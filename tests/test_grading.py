"""Typed quiz answers: numbers, ordinals and Roman numerals count the same, and the key part must be right."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import board, knowledge  # noqa: E402

CASES = [
    ("Which amendment gave women the right to vote?", "The 19th Amendment", "19th", "right"),
    ("Which amendment gave women the right to vote?", "The 19th Amendment", "nineteenth", "right"),
    ("Which amendment gave women the right to vote?", "The 19th Amendment", "Amendment XIX", "right"),
    ("Which amendment gave women the right to vote?", "The 19th Amendment", "the 26th amendment", "wrong"),
    ("How many Articles does the Constitution have?", "Seven", "7", "right"),
    ("How many Articles does the Constitution have?", "Seven", "6", "wrong"),
    ("How many amendments does the Constitution have?", "27", "twenty-seven", "right"),
    ("Which Article of the Constitution creates Congress?", "Article I", "article 1", "right"),
    ("Which Article of the Constitution creates Congress?", "Article I", "Article I", "right"),
    ("Which Article of the Constitution creates Congress?", "Article I", "article 2", "wrong"),
    ("Which Article creates the executive branch?", "Article II", "article iv", "wrong"),
    ("How many branches of government are there?", "Three — legislative, executive, judicial", "3", "right"),
    ("How many branches of government are there?", "Three — legislative, executive, judicial",
     "legislative, executive and judicial", "right"),
]


class GradingTests(unittest.TestCase):
    def test_numbers_and_key_parts(self):
        for q, ref, ans, want in CASES:
            with self.subTest(answer=ans, reference=ref):
                self.assertEqual(board.quiz_grade(q, ref, ans, use_ai=False)["verdict"], want)

    def test_every_card_answer_grades_right(self):
        """Typing a card's own answer must always count -- an answer the grader can't match is a broken question."""
        for card in knowledge.Library().all_cards:
            for item in card.quiz:
                q, a = (item["q"], item["a"]) if isinstance(item, dict) else item[:2]
                with self.subTest(card=card.id, question=q):
                    self.assertEqual(board.quiz_grade(q, a, a, use_ai=False)["verdict"], "right")


    def test_cards_use_only_markdown_the_screen_shows(self):
        """web/js/core.js md() renders bold, italic, lists, headings and > quotes -- not tables."""
        for card in knowledge.Library().all_cards:
            with self.subTest(card=card.id):
                self.assertFalse([l for l in card.body.splitlines() if l.lstrip().startswith("|")], "tables don't render")


    def test_every_card_names_a_known_service(self):
        """Learn is organized by service (Army, Navy, Air Force, Marine Corps, ...) plus shared material."""
        cards = knowledge.Library().all_cards
        for card in cards:
            with self.subTest(card=card.id):
                self.assertIn(card.service, knowledge.SERVICES)
        self.assertTrue(all(c.service == "army" for c in cards if c.category == "basic"))   # Army's study guide so far
        self.assertTrue(any(c.service == "joint" for c in cards))

    def test_learn_section_filter(self):
        """Learn's quiz buttons: "category@service" picks one branch's cards in one subject, nothing else."""
        cards = knowledge.Library().all_cards
        army_mil = [c for c in cards if knowledge.matches(c, "military@army")]
        self.assertTrue(army_mil)
        self.assertTrue(all(c.category == "military" and c.service == "army" for c in army_mil))
        shared = [c for c in cards if knowledge.matches(c, "leadership@joint")]
        self.assertTrue(shared and all(c.service == "joint" for c in shared))
        self.assertEqual(len([c for c in cards if knowledge.matches(c, "army")]), sum(c.service == "army" for c in cards))
        self.assertEqual(len([c for c in cards if knowledge.matches(c, "")]), len(cards))

if __name__ == "__main__":
    unittest.main()
