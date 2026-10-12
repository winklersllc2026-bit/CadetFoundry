"""Batch 2 (2026-10-11): each scenario's instructor debrief -- what to notice, discussion questions, a follow-up.
It's for the instructor's own screens: never in anything a Cadet's device or the projector receives."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())

from cadetfoundry import scenarios  # noqa: E402

SERVER = (ROOT / "cadetfoundry" / "server.py").read_text(encoding="utf-8")


class DebriefTests(unittest.TestCase):
    def test_every_practice_scenario_has_a_debrief(self):
        for sc in scenarios.builtins():
            with self.subTest(sc["id"]):
                d = scenarios.debrief(sc)
                self.assertTrue(d["notice"])
                self.assertEqual(len(d["discussion"]), 3)
                self.assertTrue(all(q.endswith("?") for q in d["discussion"]))
                self.assertTrue(d["follow_up"])
                self.assertTrue(d["principles"])
                self.assertNotIn("Notice:", sc["reflection"])          # the new fields don't leak into the reflection

    def test_the_debrief_never_reaches_a_cadet_or_the_projector(self):
        for sc in scenarios.builtins():
            secret = [sc["notice"], sc["follow_up"], *sc["discussion"]]
            seen = json.dumps([scenarios.for_cadet(sc), scenarios.summary(sc),
                               *[scenarios.explain(sc, i) for i in range(len(sc["choices"]))], scenarios.all_outcomes(sc)])
            for text in secret:
                self.assertNotIn(text, seen, sc["id"])
        scenarios.live_start(scenarios.builtins()[0]["id"])
        try:
            scenarios.live_reveal(True)
            projected = json.dumps([scenarios.live_for_instructor(), scenarios.live_for_cadet("someone")])
            sc = scenarios.builtins()[0]
            for text in [sc["notice"], sc["follow_up"], *sc["discussion"]]:
                self.assertNotIn(text, projected)
        finally:
            scenarios.live_stop()
        # only the instructor's scenario list carries it
        self.assertIn('"debrief": scenarios.debrief(s)', SERVER)
        self.assertEqual(SERVER.count("scenarios.debrief("), 1)

    def test_an_instructors_own_scenario_keeps_its_debrief(self):
        text = scenarios.to_text(scenarios.builtins()[3])
        sc = scenarios.parse(text)
        self.assertEqual(scenarios.parse(scenarios.to_text(sc)), sc)
        bare = scenarios.parse("Title: T\nSituation: S\nChoice: A\nOutcome: x\nChoice: B\nOutcome: y")
        self.assertEqual((bare["notice"], bare["discussion"], bare["follow_up"]), ("", [], ""))   # optional


if __name__ == "__main__":
    unittest.main()
