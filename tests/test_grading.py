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


if __name__ == "__main__":
    unittest.main()
