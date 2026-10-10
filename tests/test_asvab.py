"""0.2: ASVAB practice and the all-services jobs explorer.

The practice test must be scored exactly -- every generated math question's key is checked here by working the
problem a second, independent way -- and must never show a made-up AFQT.
"""
import os
import random
import re
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("VANGUARD_DATA", tempfile.mkdtemp())
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import asvab, careers, profiles, store  # noqa: E402


def _nums(s):
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*(?:\.\d+)?", s)]


def check_ar(q):
    """Work the word problem independently from the question text; return the expected answer text or None."""
    t, n = q["q"], _nums(q["q"])
    if t.startswith("A bus travels"):
        return f"{n[0] * n[1]:g} miles"
    if t.startswith("Pens cost"):
        return f"${n[0] * n[1]:,.2f}"
    if t.startswith("A jacket"):
        return f"${n[0] * (100 - n[1]) / 100:,.2f}"
    if "on four quizzes" in t:
        return str(int(sum(n[:4]) / 4))
    if "the ratio of juniors to seniors" in t:
        total, a, b = n[0], n[1], n[2]
        return str(int(total * b / (a + b)))
    if t.startswith("You buy items"):
        return f"${n[2] - n[0] - n[1]:,.2f}"
    if "simple interest" in t:
        return f"${n[0] * n[1] / 100 * n[2]:,.2f}"
    if t.startswith("A shift starts"):
        start = int(t.split("starts at ")[1][:4])
        mins = (start // 100) * 60 + start % 100 + int(n[1]) * 60 + int(n[2])
        return f"{mins // 60 % 24:02d}{mins % 60:02d}"
    if t.startswith("A truck goes"):
        return f"{n[1] / n[0]:g} gallons"
    if "joined the drill team" in t:
        return str(int(n[0] * n[1] / 100))
    if t.startswith("A room is"):
        return f"${n[0] * n[1] * n[2]:,.2f}"
    return None


def check_mk(q):
    t = q["q"].replace("−", "-")
    m = re.match(r"Solve for x: (\d+)x ([+-]) (\d+) = (-?\d+)", t)
    if m:
        a, sign, b, c = int(m[1]), m[2], int(m[3]), int(m[4])
        return f"x = {(c - (b if sign == '+' else -b)) // a}"
    m = re.match(r"If x = (-?\d+) and y = (-?\d+)", t)
    if m:
        x, y = int(m[1]), int(m[2])
        return str(2 * x * x - 3 * y)
    m = re.match(r"Simplify: x\^(\d+) · x\^(\d+)", t)
    if m:
        return f"x^{int(m[1]) + int(m[2])}"
    m = re.match(r"What is (\d+)/(\d+) \+ (\d+)/(\d+)\?", t)
    if m:
        f = Fraction(int(m[1]), int(m[2])) + Fraction(int(m[3]), int(m[4]))
        return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"
    m = re.search(r"radius of (\d+)", t)
    if m:
        return f"{int(m[1]) ** 2}π"
    m = re.search(r"legs of (\d+) and (\d+)", t)
    if m:
        return str(int((int(m[1]) ** 2 + int(m[2]) ** 2) ** 0.5))
    m = re.match(r"Simplify: √(\d+)", t)
    if m:
        n = int(m[1])
        k = max(i for i in range(1, 12) if n % (i * i) == 0)
        return f"{k}√{n // (k * k)}"
    m = re.search(r"measure (\d+)° and (\d+)°", t)
    if m:
        return f"{180 - int(m[1]) - int(m[2])}°"
    m = re.match(r"Factor: x² \+ (\d+)x \+ (\d+)", t)
    if m:
        s, p = int(m[1]), int(m[2])
        roots = [(a, s - a) for a in range(1, s) if a * (s - a) == p]
        return {f"(x + {a})(x + {b})" for a, b in roots}
    m = re.match(r"Solve: (\d+)x - (\d+) > (-?\d+)", t)
    if m:
        return f"x > {(int(m[3]) + int(m[2])) // int(m[1])}"
    m = re.search(r"through \((-?\d+), (-?\d+)\) and \((-?\d+), (-?\d+)\)", t)
    if m:
        x1, y1, x2, y2 = map(int, m.groups())
        return str((y2 - y1) // (x2 - x1))
    return None


class PracticeTests(unittest.TestCase):
    def test_every_generated_math_answer_is_right(self):
        """Each answer key is recomputed independently from the question's own numbers."""
        checked = 0
        for seed in range(400):
            rng = random.Random(seed)
            for section, check in (("AR", check_ar), ("MK", check_mk)):
                for q in asvab.questions(section, rng):
                    want = check(q)
                    self.assertIsNotNone(want, f"unchecked question: {q['q']}")
                    got = q["choices"][q["answer"]]
                    if isinstance(want, set):
                        self.assertIn(got, want, q["q"])
                    else:
                        self.assertEqual(got, want, q["q"])
                    checked += 1
        self.assertGreater(checked, 10000)

    def test_every_question_has_four_different_choices(self):
        for seed in range(300):
            rng = random.Random(seed)
            for s in asvab.ORDER:
                qs = asvab.questions(s, rng)
                self.assertEqual(len(qs), min(asvab.SECTIONS[s]["questions"], len(asvab.PC) if s == "PC" else 99))
                for q in qs:
                    self.assertEqual(len(set(q["choices"])), 4, q)
                    self.assertTrue(0 <= q["answer"] < 4)

    def test_official_counts_and_times(self):
        """Proctored CAT-ASVAB, officialasvab.com (2026-10-10): scored questions and minutes without tryouts."""
        want = {"AR": (15, 55), "WK": (15, 9), "PC": (10, 27), "MK": (15, 31)}
        self.assertEqual({s: (v["questions"], v["minutes"]) for s, v in asvab.SECTIONS.items()}, want)

    def test_scoring_is_exact_and_never_claims_an_afqt(self):
        tmp = Path(tempfile.mkdtemp())
        with mock.patch.object(store, "DATA", tmp), mock.patch.object(profiles, "ROOT", tmp / "profiles"):
            p = profiles.create("Cadet Test")
            ctx = store.use_profile(profiles.folder(p["id"]))
            try:
                t = asvab.start(["AR", "WK"])
                self.assertNotIn("key", t)                         # the answer key stays on the device's server
                key = store.read_json(asvab.CURRENT, {})["key"]
                answers = {str(i): k["answer"] for i, k in enumerate(key)}
                answers["0"] = (key[0]["answer"] + 1) % 4          # one wrong
                del answers["1"]                                   # one blank
                r = asvab.submit(t["id"], answers)
                self.assertEqual((r["right"], r["total"]), (28, 30))
                self.assertEqual(r["sections"]["AR"], {"right": 13, "total": 15})
                self.assertEqual(r["sections"]["WK"], {"right": 15, "total": 15})
                self.assertFalse(any(k in r for k in ("afqt", "percentile", "standard_score")))
                self.assertEqual(asvab.history()[0]["right"], 28)
                with self.assertRaises(ValueError):                # one submission per test
                    asvab.submit(t["id"], answers)
            finally:
                store.reset_profile(ctx)


class JobScoreTests(unittest.TestCase):
    def test_line_score_matching(self):
        job = {"asvab": [{"area": "Electronics", "min": 70}]}
        self.assertTrue(careers.meets(job, {"Electronics": 70}))
        self.assertFalse(careers.meets(job, {"Electronics": 69}))
        self.assertIsNone(careers.meets(job, {"General": 99}))          # the needed score wasn't entered
        self.assertIsNone(careers.meets({"asvab": []}, {"General": 99}))  # no published requirement: never a match
        both = {"asvab": [{"area": "Administrative", "min": 55}, {"area": "General", "min": 57}]}
        self.assertTrue(careers.meets(both, {"Administrative": 60, "General": 60}))
        self.assertFalse(careers.meets(both, {"Administrative": 60, "General": 50}))
        either = {"asvab_any": True, "asvab": [{"area": "Mechanical", "min": 60}, {"area": "Electronics", "min": 50}]}
        self.assertTrue(careers.meets(either, {"Electronics": 55}))

    def test_search_spans_services_when_downloaded(self):
        lib = ROOT / "library"
        r = careers.search(lib)
        if len(r["services"]) < 2:
            self.skipTest("job lists not downloaded (tools/fetch_library.py)")
        self.assertIn("air_force", r["services"])
        af = careers.search(lib, service="air_force")
        self.assertTrue(af["jobs"] and all(j["service"] == "air_force" for j in af["jobs"]))
        mine = careers.search(lib, service="air_force", scores={"General": 99, "Electronics": 99, "Mechanical": 99,
                                                                 "Administrative": 99}, only_meets=True, limit=500)
        self.assertTrue(mine["jobs"] and all(j["meets"] is True for j in mine["jobs"]))


if __name__ == "__main__":
    unittest.main()
