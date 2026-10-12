"""Security review, Phase 5: program backup and restore -- a complete, staged, recoverable replacement.

Before: restore wrote the backup's files straight into the live program folder one by one, and files the backup
didn't have stayed behind (a restore of an older backup left newer records in place; join codes and cadet titles
weren't backed up at all).
"""
import base64
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CADETFOUNDRY_DATA", tempfile.mkdtemp())
os.environ["CADETFOUNDRY_NO_WARMUP"] = "1"

from cadetfoundry import program_backup, store, vault  # noqa: E402

PW = "long enough backup pass"


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class ProgramRestoreTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.patch = mock.patch.object(store, "DATA", self.root)
        self.patch.start()
        self.prog = self.root / "program"

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def put(self, files: dict, device: dict | None = None):
        shutil.rmtree(self.prog, ignore_errors=True)
        self.prog.mkdir(parents=True)
        for name, data in files.items():
            (self.prog / name).write_text(json.dumps(data), encoding="utf-8")
        for name, data in (device or {}).items():
            (self.root / name).write_text(json.dumps(data), encoding="utf-8")

    def state(self) -> dict:
        return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.prog.iterdir()) if p.is_file()}

    def backup_of(self, files: dict, device: dict | None = None) -> dict:
        self.put(files, device)
        return program_backup.export(PW)

    def seal_payload(self, payload: dict) -> dict:
        return {"cadetfoundry_program_backup_sealed": 1, **vault.seal_backup(json.dumps(payload).encode("utf-8"), PW)}

    # ── what a restore produces ────────────────────────────────────────────
    def test_restore_into_an_empty_installation(self):
        bk = self.backup_of({"lessons.json": [{"id": "L1"}], "join_codes.json": {"ABC234": {"unit": "u1", "name": "A"}}},
                            {"program.json": {"public": "aa"}, "admin.json": {"hash": "h"}})
        shutil.rmtree(self.prog)
        (self.root / "program.json").unlink()
        (self.root / "admin.json").unlink()
        out = program_backup.restore(bk, PW)
        self.assertEqual(out["mode"], "replace")
        self.assertEqual(self.state(), {"lessons.json": [{"id": "L1"}], "join_codes.json": {"ABC234": {"unit": "u1", "name": "A"}}})
        self.assertEqual(json.loads((self.root / "program.json").read_text()), {"public": "aa"})
        self.assertEqual(json.loads((self.root / "admin.json").read_text()), {"hash": "h"})

    def test_an_older_backup_over_a_fuller_program_leaves_nothing_stale(self):
        bk = self.backup_of({"lessons.json": [{"id": "old"}]}, {"program.json": {"public": "OLD"}})
        self.put({"lessons.json": [{"id": "old"}, {"id": "new"}], "assignments.json": [{"id": "A9"}],
                  "service_projects.json": [{"id": "S1"}]}, {"program.json": {"public": "NEW"}})
        program_backup.restore(bk, PW)
        self.assertEqual(self.state(), {"lessons.json": [{"id": "old"}]})          # exactly the backup: no stale files
        self.assertEqual(json.loads((self.root / "program.json").read_text()), {"public": "OLD"})
        # the replaced program is kept as a safety copy
        copies = list(self.root.glob("program.before-restore-*"))
        self.assertEqual(len(copies), 1)
        self.assertTrue((copies[0] / "assignments.json").exists())
        self.assertEqual(json.loads((copies[0] / "_device_program.json").read_text()), {"public": "NEW"})
        self.assertFalse((self.root / "program.restoring").exists())
        self.assertFalse((self.prog / "_RESTORE_READY").exists())
        self.assertFalse((self.prog / "_device").exists())

    def test_backups_now_carry_join_codes_titles_and_pending_joins(self):
        bk = self.backup_of({"join_codes.json": {"K7M2QX": {"unit": "u", "name": "LET 1"}},
                             "cadet_titles.json": {"p1": {"rank": "C/SGT"}}, "joins.json": {"sealed": []}})
        self.put({})
        program_backup.restore(bk, PW)
        self.assertEqual(set(self.state()), {"join_codes.json", "cadet_titles.json", "joins.json"})

    def test_only_three_safety_copies_are_kept(self):
        bk = self.backup_of({"lessons.json": []})
        for i in range(5):
            self.put({"lessons.json": [{"id": i}]})
            with mock.patch("time.strftime", return_value=f"2026101{i}-120000"):
                program_backup.restore(bk, PW)
        self.assertEqual(len(list(self.root.glob("program.before-restore-*"))), 3)

    # ── bad backups change nothing ─────────────────────────────────────────
    def assert_refused(self, box, password=PW):
        self.put({"lessons.json": [{"id": "live"}]}, {"program.json": {"public": "LIVE"}})
        before = (self.state(), (self.root / "program.json").read_text())
        with self.assertRaises(ValueError):
            program_backup.restore(box, password)
        self.assertEqual((self.state(), (self.root / "program.json").read_text()), before)
        self.assertFalse((self.root / "program.restoring").exists())
        self.assertEqual(list(self.root.glob("program.before-restore-*")), [])

    def test_wrong_password_missing_malformed_and_corrupted_backups_change_nothing(self):
        good = self.backup_of({"lessons.json": [{"id": "x"}]})
        self.assert_refused(good, "the wrong password!")                        # wrong password
        self.assert_refused({})                                                  # missing / not a backup
        self.assert_refused({"cadetfoundry_program_backup_sealed": 1})               # malformed
        bad = dict(good)
        bad["data"] = ("00" if good["data"][:2] != "00" else "11") + good["data"][2:]   # one byte changed: tag fails
        self.assert_refused(bad)
        self.assert_refused(self.seal_payload({"cadetfoundry_program_backup": 1, "files": {}}))          # empty
        self.assert_refused(self.seal_payload({"cadetfoundry_program_backup": 1,
                                               "files": {"program/lessons.json": "!!not base64!!"}}))
        self.assert_refused(self.seal_payload({"cadetfoundry_program_backup": 1,
                                               "files": {"program/lessons.json": base64.b64encode(b"{broken").decode()}}))
        self.assert_refused(self.seal_payload({"cadetfoundry_program_backup": 2, "files": {}}))          # future version

    def test_path_traversal_and_unexpected_names_are_refused(self):
        for name in ("program/../../evil.py", "../admin.json", "program/sub/x.json", "C:/Windows/x", "program/",
                     "program/roster.json/../../x", "profiles/abc/security.json", "config.json"):
            with self.subTest(name=name):
                self.assert_refused(self.seal_payload({"cadetfoundry_program_backup": 1,
                                                       "files": {name: base64.b64encode(b"{}").decode()}}))

    def test_an_older_version_1_backup_still_restores(self):
        """Backups made before this change (no join codes, titles or pending joins) restore as before."""
        old = self.seal_payload({"cadetfoundry_program_backup": 1, "created": "2026-09-01 10:00",
                                 "files": {"program/lessons.json": base64.b64encode(b'[{"id": "L"}]').decode()},
                                 "config": {"ai_mode": "library"}})
        self.put({"lessons.json": [], "join_codes.json": {"OLD": {}}})
        out = program_backup.restore(old, PW)
        self.assertEqual(out["from"], "2026-09-01 10:00")
        self.assertEqual(self.state(), {"lessons.json": [{"id": "L"}]})

    # ── interrupted restores ───────────────────────────────────────────────
    def test_interrupted_after_the_swap_started_is_finished_at_the_next_start(self):
        """Stopped after the live program became the safety copy, before the staged one moved in."""
        bk = self.backup_of({"lessons.json": [{"id": "restored"}]}, {"program.json": {"public": "B"}})
        self.put({"lessons.json": [{"id": "live"}]}, {"program.json": {"public": "LIVE"}})
        real_rename = Path.rename

        def crash_on_staging(self_path, target):
            if self_path.name == "program.restoring":
                raise SystemExit("power cut")                                    # the process dies here
            return real_rename(self_path, target)
        with mock.patch.object(Path, "rename", crash_on_staging), self.assertRaises(SystemExit):
            program_backup.restore(bk, PW)
        self.assertFalse(self.prog.exists())                                     # mid-swap: no program folder
        program_backup.finish_pending()                                           # what the next start does
        self.assertEqual(self.state(), {"lessons.json": [{"id": "restored"}]})
        self.assertEqual(json.loads((self.root / "program.json").read_text()), {"public": "B"})

    def test_interrupted_while_staging_rolls_back_to_the_program_as_it_was(self):
        self.put({"lessons.json": [{"id": "live"}]}, {"program.json": {"public": "LIVE"}})
        (self.root / "program.restoring").mkdir()                               # half-written, never marked ready
        (self.root / "program.restoring" / "lessons.json").write_text("[]", encoding="utf-8")
        program_backup.finish_pending()
        self.assertEqual(self.state(), {"lessons.json": [{"id": "live"}]})
        self.assertFalse((self.root / "program.restoring").exists())
        # and the case where the live folder was already moved aside, staging incomplete: the safety copy returns
        (self.root / "program").rename(self.root / "program.before-restore-20261011-120000")
        (self.root / "program.before-restore-20261011-120000" / "_device_program.json").write_text('{"public": "LIVE"}')
        (self.root / "program.json").write_text('{"public": "HALF"}')
        program_backup.finish_pending()
        self.assertEqual(self.state(), {"lessons.json": [{"id": "live"}]})
        self.assertEqual(json.loads((self.root / "program.json").read_text()), {"public": "LIVE"})


if __name__ == "__main__":
    unittest.main()
