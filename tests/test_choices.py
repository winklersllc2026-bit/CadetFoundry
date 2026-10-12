"""Multiple-choice answers (choices.py). Owner's report, 2026-10-11: exam answers "seem illogical and don't really line
up with the question" -- "Name three things drill builds" offered "120" and "The Blue Book". Every question in the
library is checked here, so a new card can't bring that back."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cadetfoundry import choices, exam, knowledge  # noqa: E402

LIB = knowledge.Library()


def find(question: str):
    for c in LIB.all_cards:
        for q, a in c.quiz:
            if q == question:
                return c, q, a
    raise AssertionError(f"no such question: {question}")


class ChoicesTests(unittest.TestCase):
    def test_every_set_in_the_library_is_fair(self):
        rng = random.Random(7)
        built = 0
        for c in LIB.all_cards:
            for q, a in c.quiz:
                picks = choices.build(LIB, c, q, a, rng=rng)
                if picks is None:
                    continue
                built += 1
                right = choices.right_choice(q, a)
                with self.subTest(card=c.id, q=q):
                    self.assertIn(right, picks)
                    self.assertTrue(2 <= len(picks) <= 4)
                    self.assertEqual(len({choices.norm(p) for p in picks}), len(picks))       # no repeats
                    self.assertEqual(sum(choices.is_right(q, a, p) for p in picks), 1)       # exactly one right
                    f = choices.features(q, a)
                    for p in picks:
                        if p == right or choices._binary(q, a) or p in c.wrong.get(q, []):
                            continue
                        g = choices.features("", p)
                        self.assertFalse(choices.YESNO.match(p), p)                          # never a stray "Yes"
                        if f["kind"] == "number":                                       # a number for a number
                            self.assertTrue(g["nums"] or choices.ORDINAL.search(p) or choices.ROMAN.search(p), p)
                        else:
                            self.assertFalse(g["nums"] and not f["nums"] and g["cls"] != "command" and len(p.split()) <= 3, p)
                        if f["cls"] and f["kind"] != "list":                            # a person for a person
                            self.assertEqual(g["cls"], f["cls"], p)
        self.assertGreater(built, 600)                 # raise as cards get hand-written WRONG: lines

    def test_the_reported_questions(self):
        for question, never in (("Name three things drill builds", {"120", "180", "The Blue Book"}),
                                ("What are the three Marine Corps values?", {"1883", "Honor"})):
            c, q, a = find(question)
            for seed in range(20):
                picks = choices.build(LIB, c, q, a, rng=random.Random(seed)) or []
                self.assertFalse(never & set(picks), (question, picks))

    def test_numbers_get_nearby_numbers_in_the_same_words(self):
        self.assertIn("Three times", choices._number_variants("Twice"))
        self.assertIn("The ninth general order", choices._number_variants("The eighth general order"))
        self.assertIn("Article IV", choices._number_variants("Article III"))
        for v in choices._number_variants("The 19th Amendment"):
            n = int("".join(ch for ch in v if ch.isdigit()))
            self.assertLessEqual(n, 27)                                       # there are 27 amendments
            self.assertRegex(v, r"\d(st|nd|rd|th) Amendment")
            self.assertNotRegex(v, r"(?<!1)(1|2|3)th|11st|12nd|13rd")
        self.assertEqual(choices._number_variants("AR 670-1"), [])            # never a made-up regulation number
        self.assertEqual(choices._number_variants("Second Lieutenant"), [])   # never "Fifth Lieutenant"
        self.assertEqual(choices._number_variants("Zero six hundred"), [])

    def test_yes_no_and_this_or_that(self):
        self.assertEqual(choices.right_choice("Are salutes exchanged indoors?", "No — except when reporting"), "No")
        self.assertEqual(sorted(choices.wrong_answers(LIB, None, "Is it easier or harder to do X?", "Harder — it takes more effort")),
                         ["Easier"])
        q = "Which is older, the Army or the Declaration of Independence?"
        a = "The Army — 1775, the Declaration was 1776"
        self.assertEqual(choices.right_choice(q, a), "The Army")
        self.assertEqual(choices.wrong_answers(LIB, None, q, a), ["The Declaration of Independence"])
        self.assertTrue(choices.is_right(q, a, "The Army"))
        self.assertTrue(choices.is_right(q, a, a))
        self.assertFalse(choices.is_right(q, a, "The Declaration of Independence"))

    def test_a_choice_shows_the_short_part_and_grades_right(self):
        q, a = "What field exercise comes in White Phase?", "The Anvil — two days and two nights"
        self.assertEqual(choices.right_choice(q, a), "The Anvil")
        self.assertTrue(choices.is_right(q, a, "The Anvil"))
        self.assertFalse(choices.is_right(q, a, "The Forge"))

    def test_authors_wrong_answers_come_first(self):
        card = knowledge.Card(id="t", title="t", topic="t", source="t", body="",
                              quiz=[("Which way?", "Left")], wrong={"Which way?": ["Right", "Up", "Down"]})
        self.assertEqual(sorted(choices.wrong_answers(LIB, card, "Which way?", "Left")), ["Down", "Right", "Up"])

    def test_wrong_lines_parse(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.md"
            p.write_text("---\ntitle: X\n---\nbody\n## Quiz\nQ: One? | A: Yes | WRONG: a; b; c\n"
                         "Q: Two? | A: B | ALSO: Second?; 2? | WRONG: c\nQ: Three? | A: C | WRONG: d | ALSO: 3?\n",
                         encoding="utf-8")
            c = knowledge.parse_card(p)
        self.assertEqual(c.quiz, [("One?", "Yes"), ("Two?", "B"), ("Three?", "C")])
        self.assertEqual(c.wrong, {"One?": ["a", "b", "c"], "Two?": ["c"], "Three?": ["d"]})
        self.assertEqual(c.also, {"Two?": ["Second?", "2?"], "Three?": ["3?"]})

    def test_an_exam_has_four_fair_choices_per_question(self):
        from unittest import mock
        with mock.patch.object(exam.store, "write_json"):                 # (no profile needed to look at it)
            ex = exam.start(LIB, "", 25)
        self.assertEqual(len(ex["questions"]), 25)
        for q in ex["questions"]:
            self.assertEqual(len({choices.norm(c) for c in q["choices"]}), 4, q)


if __name__ == "__main__":
    unittest.main()
