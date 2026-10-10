"""Classroom security: what an instructor may read of a Cadet's data, and what nobody else may.

Owner's decision (2026-10-08): the instructor sees CLASS RECORDS only (store.CLASS_FILES). Private files -- check-ins,
chats, memories, letters, logbook, profile -- stay readable with the Cadet's own PIN and nothing else.
"""
import json
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

from vanguard import profiles, security, store, vault  # noqa: E402

INSTRUCTOR_PIN = "905172"


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class ClassKeyTests(unittest.TestCase):
    def setUp(self):
        # A device of its own: no Instructor PIN, no program key, no other profiles.
        tmp = Path(tempfile.mkdtemp())
        self.patches = [mock.patch.object(store, "DATA", tmp), mock.patch.object(profiles, "ROOT", tmp / "profiles")]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(security._sessions.clear)

    def cadet(self, pin="482915", kind="cadet"):
        p = profiles.create(f"C-{uuid.uuid4().hex[:6]}", kind)
        with security.as_profile(p["id"]):
            self.assertIsNone(security.set_pin(pin))
        token, msg = security.unlock(p["id"], pin)
        self.assertEqual(msg, "ok")
        return p, token

    def write_records(self, pid, token):
        with security.as_profile(pid, security.session_key(token), security.session_class_key(token)):
            store.write_json("study.json", {"q1": {"right": 1}})          # class record
            store.append_line("memory.jsonl", {"text": "private"})         # private

    def raw(self, pid, name):
        return (profiles.folder(pid) / name).read_bytes()

    def test_class_records_and_private_files_use_different_keys(self):
        p, tok = self.cadet()
        self.write_records(p["id"], tok)
        key, ck = security.session_key(tok), security.session_class_key(tok)
        self.assertTrue(key and ck and key != ck)
        self.assertTrue(vault.is_sealed(self.raw(p["id"], "study.json")))
        self.assertTrue(vault.is_sealed(self.raw(p["id"], "memory.jsonl")))
        vault.open_sealed(ck, self.raw(p["id"], "study.json"), "study.json")
        with self.assertRaises(vault.VaultError):                          # the class key can't open private files
            vault.open_sealed(ck, self.raw(p["id"], "memory.jsonl"), "memory.jsonl")

    def test_instructor_reads_class_records_never_private_files(self):
        self.assertIsNone(security.set_admin_pin(INSTRUCTOR_PIN))
        self.assertIsNotNone(security.program_public())
        p, tok = self.cadet()
        self.write_records(p["id"], tok)
        with security.as_profile(p["id"]):
            box = security._state()["class_for"]
        priv = vault.unwrap(security._program()["private"], INSTRUCTOR_PIN)
        ck = vault.open_from(priv, box, "class key")
        with security.as_profile(p["id"], None, ck):                       # what an instructor's session has
            self.assertEqual(store.read_json("study.json", {}), {"q1": {"right": 1}})
            with self.assertRaises(vault.VaultError):
                store._read_text("memory.jsonl")

    def test_cadets_set_up_before_the_instructor_are_shared_at_next_unlock(self):
        p, tok = self.cadet()
        self.write_records(p["id"], tok)
        with security.as_profile(p["id"]):
            self.assertNotIn("class_for", security._state())               # no program key yet
        self.assertIsNone(security.set_admin_pin(INSTRUCTOR_PIN))
        security.unlock(p["id"], "482915")
        with security.as_profile(p["id"]):
            self.assertIn("class_for", security._state())

    def test_changing_the_instructor_pin_keeps_the_program_key(self):
        self.assertIsNone(security.set_admin_pin(INSTRUCTOR_PIN))
        pub = security.program_public()
        self.assertIsNone(security.set_admin_pin("604183", INSTRUCTOR_PIN))
        self.assertEqual(security.program_public(), pub)
        self.assertEqual(len(vault.unwrap(security._program()["private"], "604183")), 32)
        with self.assertRaises(vault.VaultError):
            vault.unwrap(security._program()["private"], INSTRUCTOR_PIN)

    def test_only_an_instructor_profile_with_the_instructor_pin_unlocks_class_records(self):
        self.assertIsNone(security.set_admin_pin(INSTRUCTOR_PIN))
        _c, ctok = self.cadet()
        self.assertIn("Only an instructor", security.unlock_program(ctok, INSTRUCTOR_PIN))
        self.assertIsNone(security.session_program_key(ctok))
        _i, itok = self.cadet("736281", kind="instructor")
        self.assertIn("isn't right", security.unlock_program(itok, "000000"))
        self.assertIsNone(security.session_program_key(itok))
        self.assertIsNone(security.unlock_program(itok, INSTRUCTOR_PIN))
        self.assertEqual(len(security.session_program_key(itok)), 32)

    def test_removing_the_pin_decrypts_everything(self):
        p, tok = self.cadet()
        self.write_records(p["id"], tok)
        with security.as_profile(p["id"], security.session_key(tok), security.session_class_key(tok)):
            self.assertIsNone(security.remove_pin("482915"))
        self.assertFalse(vault.is_sealed(self.raw(p["id"], "study.json")))
        self.assertFalse(vault.is_sealed(self.raw(p["id"], "memory.jsonl")))
        with security.as_profile(p["id"]):
            self.assertNotIn("class_vault", security._state())

    def test_recovery_code_still_opens_class_records(self):
        p, tok = self.cadet()
        self.write_records(p["id"], tok)
        with security.as_profile(p["id"]):
            code = security.make_recovery_code("482915")
        token, msg, _new = security.recover(p["id"], code, "736281")
        self.assertEqual(msg, "ok")
        with security.as_profile(p["id"], security.session_key(token), security.session_class_key(token)):
            self.assertEqual(store.read_json("study.json", {}), {"q1": {"right": 1}})


if __name__ == "__main__":
    unittest.main()
