"""Security review, Phase 2: program-level data at rest.

  * Live votes and live-question answers (tied to profile ids) never touch the disk.
  * Pending join requests are sealed to the program public key: a Cadet's session writes one, only an instructor's
    session opens it.
  * Older versions' plain files are migrated without losing anything: read as they were, sealed (or, for live state,
    taken into memory) and the plain copy removed -- no plain copy left beside the sealed one, no .tmp left behind.
"""
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
os.environ["CADETFOUNDRY_NO_WARMUP"] = "1"

from cadetfoundry import instructor, live_quiz, pilot, profiles, scenarios, security, store, vault  # noqa: E402

ADMIN = "905172"


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class ProgramDataAtRestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.made_admin = not security.admin_set()
        if cls.made_admin:
            assert security.set_admin_pin(ADMIN) is None
        cls.priv = vault.unwrap(security._program()["private"], ADMIN)
        cls.prog = store.DATA / "program"
        cls.prog.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        if cls.made_admin:
            (store.DATA / "admin.json").unlink(missing_ok=True)

    def setUp(self):
        self.saved = {p.name: p.read_bytes() for p in self.prog.glob("*") if p.is_file()}

    def tearDown(self):                                      # leave the shared test data as it was
        for p in self.prog.glob("*"):
            if p.is_file() and p.name not in self.saved:
                p.unlink()
        for name, raw in self.saved.items():
            (self.prog / name).write_bytes(raw)

    def no_tmp_left(self):
        self.assertEqual([p.name for p in self.prog.glob("*.tmp")], [])

    # ── live state ─────────────────────────────────────────────────────────
    def test_live_vote_and_live_answers_never_touch_the_disk(self):
        sid = scenarios.builtins()[0]["id"]
        pid = uuid.uuid4().hex[:12]
        scenarios.live_start(sid)
        scenarios.live_vote(pid, 1)
        self.assertEqual(scenarios.live()["votes"], {pid: 1})
        self.assertFalse((self.prog / "live.json").exists())
        scenarios.live_stop()
        self.assertEqual(scenarios.live(), {})

        live_quiz.start(None, q="2 + 2?", a="4", choices=["3", "5"], mode="mc")
        live_quiz.answer(pid, choice="4")                                       # a typed-in custom question: no study record
        self.assertFalse((self.prog / "live_quiz.json").exists())
        self.assertEqual(live_quiz.for_instructor()["answered"], 1)
        live_quiz.stop()
        self.assertEqual(live_quiz.for_instructor(), {})

    def test_an_older_versions_live_files_are_taken_over_then_removed(self):
        pid = uuid.uuid4().hex[:12]
        sid = scenarios.builtins()[0]["id"]
        (self.prog / "live.json").write_text(json.dumps({"scenario": sid, "started": 1, "revealed": False,
                                                          "votes": {pid: 2}}), encoding="utf-8")
        (self.prog / "live_quiz.json").write_text(json.dumps({"id": "live-x", "q": "Q?", "a": "A", "mode": "typed",
                                                               "choices": [], "started": 1, "revealed": False,
                                                               "answers": {pid: {"verdict": "right", "correct": True}}}),
                                                   encoding="utf-8")
        scenarios._LIVE.clear(); scenarios._live_checked = False
        live_quiz._STATE.clear(); live_quiz._legacy_checked = False
        self.assertEqual(scenarios.live()["votes"], {pid: 2})                 # nothing lost
        self.assertEqual(live_quiz.for_instructor()["answered"], 1)
        self.assertFalse((self.prog / "live.json").exists())                   # and no plain copy left
        self.assertFalse((self.prog / "live_quiz.json").exists())
        scenarios.live_stop()
        live_quiz.stop()

    # ── pending joins ──────────────────────────────────────────────────────
    def test_a_join_is_sealed_to_the_instructor_and_filed_once(self):
        pid = uuid.uuid4().hex[:12]
        instructor.request_join(pid, "unit123")
        raw = (self.prog / "joins.json").read_bytes()
        self.assertNotIn(pid.encode(), raw)
        self.assertNotIn(b"unit123", raw)
        cur = instructor._pending_joins()
        self.assertEqual(len(cur["sealed"]), 1)
        opened = json.loads(vault.open_from(self.priv, cur["sealed"][0], "join"))
        self.assertEqual(opened, {"pid": pid, "unit": "unit123"})
        with self.assertRaises(vault.VaultError):                              # any other key: no
            vault.open_from(vault.new_program_keys()[0], cur["sealed"][0], "join")
        self.no_tmp_left()

    def test_an_older_plain_joins_file_is_kept_and_sealed(self):
        old_pid, new_pid = uuid.uuid4().hex[:12], uuid.uuid4().hex[:12]
        (self.prog / "joins.json").write_text(json.dumps({old_pid: "unitA"}), encoding="utf-8")
        instructor.request_join(new_pid, "unitB")
        raw = (self.prog / "joins.json").read_bytes()
        self.assertNotIn(old_pid.encode(), raw)                                # the older plain entry is sealed now
        boxes = instructor._pending_joins()["sealed"]
        got = [json.loads(vault.open_from(self.priv, b, "join")) for b in boxes]
        self.assertIn({"pid": old_pid, "unit": "unitA"}, got)                   # nothing lost
        self.assertIn({"pid": new_pid, "unit": "unitB"}, got)

    # ── pilot files ────────────────────────────────────────────────────────
    def test_older_plain_pilot_files_migrate_without_losing_anything(self):
        (self.prog / "pilot.json").write_text(json.dumps({"school": "Oak Ridge HS", "survey_open": True,
                                                           "start": "2026-09-01"}), encoding="utf-8")
        (self.prog / "feedback_cadets.json").write_text(json.dumps([{"date": "2026-10-01", "learn": 5, "lead": 4,
                                                                     "progress": 4, "easy": 5, "again": 5,
                                                                     "comment": "Loved the votes"}]), encoding="utf-8")
        (self.prog / "feedback_instructor.json").write_text(json.dumps([{"id": "x", "satisfaction": 5,
                                                                         "comment": "Saves me time"}]), encoding="utf-8")
        (self.prog / "pilot_survey.json").unlink(missing_ok=True)
        self.assertTrue(pilot._survey_open())                                # a Cadet's screen still sees "open"
        self.assertEqual(pilot.config(None), {})                                # no key: nothing (and nothing changed)
        self.assertIn(b"Oak Ridge HS", (self.prog / "pilot.json").read_bytes())
        cfg = pilot.config(self.priv)                                           # the instructor opens it: migrated
        self.assertEqual((cfg["school"], cfg["survey_open"]), ("Oak Ridge HS", True))
        fb = pilot.feedback_summary(self.priv)
        self.assertIn("Loved the votes", fb["cadet_comments"])
        self.assertEqual(fb["latest_instructor"]["comment"], "Saves me time")
        disk = b"".join((self.prog / n).read_bytes() for n in ("pilot.json", "feedback_cadets.json",
                                                                 "feedback_instructor.json"))
        for secret in (b"Oak Ridge HS", b"Loved the votes", b"Saves me time"):
            self.assertNotIn(secret, disk)
        # opening again: still readable (the migration is idempotent), and the survey stays open
        self.assertEqual(pilot.config(self.priv)["school"], "Oak Ridge HS")
        self.assertIn("Loved the votes", pilot.feedback_summary(self.priv)["cadet_comments"])
        pilot.set_survey(self.priv, True)
        self.assertTrue(pilot._survey_open())
        self.no_tmp_left()

    def test_survey_answers_are_stored_in_random_order(self):
        (self.prog / "feedback_cadets.json").unlink(missing_ok=True)
        for i in range(12):
            pilot._add_survey_row({"date": "2026-10-11", "learn": 1 + i % 5, "lead": 3, "progress": 3, "easy": 3,
                                   "again": 3, "comment": f"c{i:02d}"})
        got = [r["comment"] for r in pilot._survey_rows(self.priv)]
        self.assertEqual(sorted(got), [f"c{i:02d}" for i in range(12)])         # every answer is there
        self.assertNotEqual(got, sorted(got))                                    # not in the order they came in


if __name__ == "__main__":
    unittest.main()
