"""Cadet flash drives (owner, 2026-10-12): made from the instructor's Me screen, used at home, brought back to class.
The instructor's computer and the Cadet's drive each run in their own process with their own data folder -- exactly
as they would for real. All PINs here are test values."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cadetfoundry import cadet_drive, vault  # noqa: E402

PRELUDE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from cadetfoundry import cadet_drive, instructor, lessons, profiles, security, store, vault
cadet_drive.APP_ITEMS = ["run.py", "README.md"]       # a small app copy: the test is about the data
ADMIN, CADET_PIN, INST_PIN, NEW_PIN = "905172", "482915", "736281", "573920"
def priv():
    return vault.unwrap(security._program()["private"], ADMIN)
def as_cadet(pid, pin):
    token, msg = security.unlock(pid, pin)
    assert token, msg
    return security.as_profile(pid, security.session_key(token), security.session_class_key(token))
args = json.loads(sys.argv[2])
out = {}
"""

LAPTOP_SETUP = PRELUDE + r"""
assert security.set_admin_pin(ADMIN) is None
k = priv()
unit = instructor.add_unit(k, "LET 1", "class")
ana = profiles.create("Ana Rivera")
with security.as_profile(ana["id"]):
    assert security.set_pin(CADET_PIN) is None
instructor.assign(k, ana["id"], unit["id"])
with as_cadet(ana["id"], CADET_PIN):                 # signs in once in class: shares class records with the program
    store.record_answer("salute#0", True)
    store.append_line("memory.jsonl", {"text": "PRIVATE-IN-CLASS"})
lesson = lessons.save_lesson(k, {"title": "Chain of command", "content": "Who leads whom.",
                                 "questions": "Q: Who is at the top?\n* The President\n- The first sergeant"})
a = lessons.assign(k, lesson["id"], units=[unit["id"]])
d1, d2 = args["drive1"], args["drive2"]
cadet_drive.make(k, d1, ana["id"], unit["id"], unit["name"], videos=False)
cadet_drive.make(k, d2, "", unit["id"], unit["name"], videos=False)          # "any Cadet" in LET 1
out.update(ana=ana["id"], unit=unit["id"], assignment=a["id"])
print(json.dumps(out))
"""

DRIVE_ANA = PRELUDE + r"""
pid = args["ana"]
assert cadet_drive.here()["for"] == pid
with as_cadet(pid, CADET_PIN):                       # at home, on the drive
    store.record_answer("salute#0", True)
    store.record_answer("salute#0", False)
    store.append_line("memory.jsonl", {"text": "PRIVATE-AT-HOME"})
    mine = lessons.my_assignments(pid)
    out["lessons_on_drive"] = [x["title"] for x in mine]
    work = store.read_json("assignments.json", {})
    work[args["assignment"]] = {"state": "complete", "completed": "2026-10-12", "score": 1, "total": 1}
    store.write_json("assignments.json", work)
print(json.dumps(out))
"""

DRIVE_NEW = PRELUDE + r"""
m = cadet_drive.here()
assert m and not m["for"]
p = profiles.create("Ben Ortiz")                     # what /api/profiles/create does on a Cadet drive
with security.as_profile(p["id"]):
    assert security.set_pin(NEW_PIN) is None
cadet_drive.claim(p["id"])
lessons.sync_unit(p["id"], m["unit"])
with as_cadet(p["id"], NEW_PIN):
    store.record_answer("ranks#1", True)
    out["lessons_on_drive"] = [x["title"] for x in lessons.my_assignments(p["id"])]
out["ben"] = p["id"]
print(json.dumps(out))
"""

LAPTOP_SYNC = PRELUDE + r"""
k = priv()
r1 = cadet_drive.sync(k, args["drive1"])
r2 = cadet_drive.sync(k, args["drive2"])
out["again"] = cadet_drive.sync(k, args["drive1"])   # nothing changed since: no second notice
out["notices"] = r1["notices"] + r2["notices"]
study = instructor.read_class_file(k, args["ana"], "study.json", {})
out["ana_salute"] = study.get("salute#0")
out["ana_lesson"] = (instructor.read_class_file(k, args["ana"], "assignments.json", {}) or {}).get(args["assignment"], {})
with as_cadet(args["ana"], CADET_PIN):
    out["laptop_private"] = [r["text"] for r in store.read_lines("memory.jsonl")]
ben = next((p for p in profiles.all_profiles() if p["name"] == "Ben Ortiz"), None)
out["ben_here"] = bool(ben)
out["ben_unit"] = (instructor.roster(k)["cadets"].get(ben["id"]) or {}).get("unit") if ben else None
out["ben_ranks"] = instructor.read_class_file(k, ben["id"], "study.json", {}).get("ranks#1") if ben else None
print(json.dumps(out))
"""

DRIVE_AFTER = PRELUDE + r"""
with as_cadet(args["ana"], CADET_PIN):
    out["drive_salute"] = store.read_json("study.json", {}).get("salute#0")
    out["drive_private"] = [r["text"] for r in store.read_lines("memory.jsonl")]
print(json.dumps(out))
"""


@unittest.skipUnless(vault.AVAILABLE, "cryptography not installed")
class CadetDriveTests(unittest.TestCase):
    def run_as(self, script: str, data: Path, args: dict, drives=()) -> dict:
        env = {**os.environ, "CADETFOUNDRY_DATA": str(data), "CADETFOUNDRY_NO_WARMUP": "1",
               "CADETFOUNDRY_TEST_DRIVES": os.pathsep.join(str(d) for d in drives)}
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", script, str(ROOT), json.dumps(args)],
                           capture_output=True, text=True, env=env, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_a_drive_goes_home_and_comes_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            laptop, d1, d2 = tmp / "laptop", tmp / "E", tmp / "F"
            d1.mkdir(), d2.mkdir()
            ids = self.run_as(LAPTOP_SETUP, laptop, {"drive1": str(d1), "drive2": str(d2)}, (d1, d2))
            ids.update(drive1=str(d1), drive2=str(d2))

            # what's on the drive: the app, the Cadet, the program's PUBLIC key -- never the Class PIN or private key
            data1 = d1 / "Cadet Foundry Data"
            self.assertTrue((d1 / "Cadet Foundry" / "run.py").exists())
            self.assertTrue((d1 / "Start Cadet Foundry.bat").exists())
            self.assertFalse((data1 / "admin.json").exists())
            self.assertEqual(set(json.loads((data1 / "program.json").read_text())), {"public"})
            self.assertEqual([p["name"] for p in json.loads((data1 / "profiles.json").read_text())["profiles"]], ["Ana Rivera"])
            self.assertFalse((d2 / "Cadet Foundry Data" / "profiles").exists())          # "any Cadet": nobody yet

            home = self.run_as(DRIVE_ANA, data1, ids)
            self.assertEqual(home["lessons_on_drive"], ["Chain of command"])
            ben = self.run_as(DRIVE_NEW, d2 / "Cadet Foundry Data", ids)
            self.assertEqual(ben["lessons_on_drive"], ["Chain of command"])          # their class's lesson, offline

            back = self.run_as(LAPTOP_SYNC, laptop, ids, (d1, d2))
            self.assertEqual(back["ana_salute"]["right"], 2)                          # 1 in class + 1 at home
            self.assertEqual(back["ana_salute"]["wrong"], 1)
            self.assertEqual(back["ana_lesson"].get("state"), "complete")
            self.assertEqual(back["laptop_private"], ["PRIVATE-IN-CLASS"])            # home notes never leave the drive
            self.assertTrue(back["ben_here"])
            self.assertEqual(back["ben_unit"], ids["unit"])
            self.assertEqual(back["ben_ranks"]["right"], 1)
            self.assertIsNone(back["again"])
            self.assertTrue(any("Ana Rivera's drive" in n and "brought in" in n for n in back["notices"]), back["notices"])
            self.assertTrue(any("Ben Ortiz joined" in n for n in back["notices"]), back["notices"])

            after = self.run_as(DRIVE_AFTER, data1, ids)
            self.assertEqual(after["drive_salute"]["right"], 2)                       # both copies agree now
            self.assertEqual(after["drive_private"], ["PRIVATE-IN-CLASS", "PRIVATE-AT-HOME"])

    def test_merge_adds_up_and_respects_deletions(self):
        self.assertEqual(cadet_drive.merge("study.json", {"q": {"right": 2, "wrong": 1}},
                                           {"q": {"right": 3, "wrong": 1}}, {"q": {"right": 4, "wrong": 2}})["q"],
                         {"right": 5, "wrong": 2})
        self.assertEqual(cadet_drive.merge("service.jsonl", [{"id": "a"}, {"id": "b"}], [{"id": "a"}],
                                           [{"id": "a"}, {"id": "b"}, {"id": "c"}]), [{"id": "a"}, {"id": "c"}])
        self.assertEqual(cadet_drive.merge("assignments.json", {"x": {"state": "in_progress"}}, {"x": {"state": "in_progress"}},
                                           {"x": {"state": "complete"}})["x"]["state"], "complete")

    def test_never_touches_an_instructors_drive_or_someone_elses(self):
        with tempfile.TemporaryDirectory() as tmp:
            inst = Path(tmp) / "G"
            (inst / "Cadet Foundry Data").mkdir(parents=True)
            (inst / "Cadet Foundry Data" / "admin.json").write_text("{}")
            self.assertEqual(cadet_drive.describe(inst)["state"], "instructor")
            other = Path(tmp) / "H"
            (other / "Cadet Foundry Data" / "profiles" / "abc").mkdir(parents=True)
            self.assertEqual(cadet_drive.describe(other)["state"], "people")


if __name__ == "__main__":
    unittest.main()
