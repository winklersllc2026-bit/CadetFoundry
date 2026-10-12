"""Data written by an older version must always open (found 2026-10-11: the rename changed the encryption labels in
vault.py, and a real 0.2.5 USB drive refused the right PIN). tests/fixtures/written_by_0_2_5/ was written by the real
0.2.5 code -- profiles with PINs, a private note, a class record, the program key, a class, a personal backup and a
program backup. Every version from now on has to open all of it. All PINs and passwords in it are test values."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "written_by_0_2_5"

CHECK = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from cadetfoundry import backup, instructor, program_backup, security, store, vault
f = json.load(open(sys.argv[2], encoding="utf-8"))
out = {}
token, msg = security.unlock(f["cadet"], f["cadet_pin"])
out["cadet_unlocks"] = bool(token)
with security.as_profile(f["cadet"], security.session_key(token), security.session_class_key(token)):
    out["private_note"] = any(r.get("text") == "FIXTURE-PRIVATE-NOTE" for r in store.read_lines("memory.jsonl"))
    out["class_record"] = store.read_json("study.json", {}).get("q1", {}).get("right") is True
itoken, _ = security.unlock(f["instructor"], f["instructor_pin"])
out["instructor_unlocks"] = bool(itoken)
out["class_pin_opens_records"] = security.unlock_program(itoken, f["class_pin"]) is None
priv = security.session_program_key(itoken)
out["program_data_key"] = vault.program_data_key(priv).hex() == f["program_data_key"]
out["class_still_there"] = any(u["name"] == f["unit"] for u in instructor.roster(priv)["units"])
out["cadet_records_readable"] = instructor.records(priv, f["cadet"]).get("questions_practiced") == 1
out["sealed_to_program"] = vault.open_from(priv, f["sealed_to_program"], "fixture") == b"FIXTURE-SEALED"
personal = backup.open_any(json.load(open(sys.argv[3], encoding="utf-8")), f["backup_password"])
out["personal_backup"] = any(r.get("text") == "FIXTURE-PRIVATE-NOTE" for r in personal["lines"]["memory.jsonl"])
program_backup.restore(json.load(open(sys.argv[4], encoding="utf-8")), f["backup_password"])
out["program_backup_restores"] = True
print(json.dumps(out))
"""


class OldDataTests(unittest.TestCase):
    def test_everything_written_by_0_2_5_still_opens(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            shutil.copytree(FIXTURE / "data", data)                     # never change the fixture itself
            env = {**os.environ, "CADETFOUNDRY_DATA": str(data), "CADETFOUNDRY_NO_WARMUP": "1"}
            r = subprocess.run([sys.executable, "-X", "utf8", "-c", CHECK, str(ROOT), str(FIXTURE / "facts.json"),
                                str(FIXTURE / "backups" / "personal.json"), str(FIXTURE / "backups" / "program.json")],
                               capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            result = json.loads(r.stdout.strip().splitlines()[-1])
            for what, ok in result.items():
                with self.subTest(what):
                    self.assertTrue(ok)
            self.assertEqual(len(result), 11)


if __name__ == "__main__":
    unittest.main()
