"""Starter lessons (2026-10-11): ready to assign on day one, built from cited study cards. These tests hold every
lesson to the content rule: the right answer comes from the card, the card has been checked, and the right choice
isn't always in the same place."""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())

from cadetfoundry import choices, knowledge, lessons  # noqa: E402

LIB = knowledge.Library()


def norm(s: str) -> str:
    s = re.sub(r"^(yes|no)\s*[—-]\s*", "", s.strip(), flags=re.I)      # "No — a squad leader…" quotes the card's line
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


class StarterLessonTests(unittest.TestCase):
    def test_there_are_twelve_and_each_is_a_valid_lesson(self):
        ss = lessons.starters()
        self.assertEqual(len(ss), 12)
        self.assertEqual(len({s["key"] for s in ss}), 12)
        for s in ss:
            with self.subTest(s["key"]):
                qs = lessons.parse_questions(s["questions"])
                self.assertEqual(len(qs), 4)
                self.assertIn(s["let_level"], (1, 2, 3, 4))
                self.assertTrue(s["objective"] and s["reflection"] and s["competency"])

    def test_every_right_answer_comes_from_its_checked_card(self):
        for s in lessons.starters():
            card = LIB.card(s["card"])
            with self.subTest(s["key"]):
                self.assertIsNotNone(card)
                self.assertTrue(card.verified)                           # never from an unchecked card
                # the card's answer, or its short form as a choice shows it ("Three" for "Three -- legislative, ...")
                known = {norm(a) for _q, a in card.quiz} | {norm(choices.head(a)) for _q, a in card.quiz}
                asked = {norm(q): {norm(a), norm(choices.head(a))} for q, a in card.quiz}
                body = norm(card.body)
                for q in lessons.parse_questions(s["questions"]):
                    right = norm(q["choices"][q["answer"]])
                    self.assertTrue(right in known or right in body, f"{s['key']}: {q['q']}")
                    if norm(q["q"]) in asked:                           # the card's own question: same right answer
                        self.assertIn(right, asked[norm(q["q"])], f"{s['key']}: {q['q']}")

    def test_the_right_choice_moves_around(self):
        positions = [q["answer"] for s in lessons.starters() for q in lessons.parse_questions(s["questions"])]
        for p in (0, 1, 2):
            self.assertGreater(positions.count(p), 8)

    def test_the_list_shows_what_is_left_to_add(self):
        listed = lessons.starter_list(LIB)
        self.assertEqual(len(listed), 12)
        self.assertTrue(all(x["title"] and not x["added"] for x in listed))


class CardCheckTests(unittest.TestCase):
    def test_the_ocs_card_is_checked_and_cites_official_pages(self):
        c = LIB.card("officer_candidate_school")
        self.assertTrue(c.verified)
        self.assertIn("goarmy.com", c.source)
        self.assertIn("checked 2026-10-11", c.source)

    def test_unchecked_cards_are_few_and_known(self):
        # land_navigation: its manual (TC 3-25.26) couldn't be checked from a public copy. It stays marked on screen
        # and out of exams and starter lessons until someone checks it against the current manual.
        self.assertEqual(sorted(c.id for c in LIB.all_cards if not c.verified), ["land_navigation"])


if __name__ == "__main__":
    unittest.main()
