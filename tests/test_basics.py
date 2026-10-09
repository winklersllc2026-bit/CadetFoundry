"""Quick checks: python -m unittest discover tests"""
import os
import sys
import tempfile
import io
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["VANGUARD_DATA"] = tempfile.mkdtemp()
os.environ["VANGUARD_NO_WARMUP"] = "1"

from vanguard import board, daily, exam, fitness, pay, profiles, safety, store, voice  # noqa: E402
from vanguard.brain import Brain  # noqa: E402
from vanguard.faith import Faith, parse_ref  # noqa: E402
from vanguard.knowledge import Library  # noqa: E402


class LibraryTests(unittest.TestCase):
    lib = Library(cache_dir=Path(os.environ["VANGUARD_DATA"]))

    def test_cards_load_with_sources_and_quizzes(self):
        self.assertGreaterEqual(len(self.lib.cards), 15)
        for c in self.lib.cards:
            self.assertTrue(c.source, c.id)
            self.assertTrue(c.quiz, c.id)

    def test_search_finds_the_right_card(self):
        for query, expect in (("what is an article 15", "Uniform Code of Military Justice"), ("how do I read a grid", "TC 3-25.26"),
                              ("do I salute a sergeant", "AR 600-25"), ("army values ldrship", "army.mil/values"),
                              ("what is line 4 of a 9 line medevac", "ATP 4-02.2"), ("what is a SALUTE report", "TC 3-21.76"),
                              ("what is the nco support channel", "AR 600-20"), ("how do I file an EO complaint", "AR 600-20"),
                              ("restricted vs unrestricted report", "AR 600-52"), ("what are the four stages of counseling", "ATP 6-22.1"),
                              ("how long is a rush", "TC 3-21.75"), ("what are the leader attributes", "FM 6-22"),
                              ("what exercises are in the preparation drill", "ATP 7-22.02")):
            hits = self.lib.search(query, k=3)
            self.assertTrue(any(expect in p.source for _s, p in hits), query)

    def test_first_aid_from_current_source_and_unverified_cards_never_checked(self):
        r = self.lib.checked_answer("where do you put a tourniquet")
        self.assertTrue(r and "TC 3-21.76" in r["source"] and "over the uniform" in r["answer"])
        self.assertFalse(self.lib.card("land_navigation").verified)
        self.assertIsNone(self.lib.checked_answer("Name the five major terrain features."))

    def test_search_results_carry_the_edition(self):
        import tempfile as tf
        d = Path(tf.mkdtemp())
        (d / "TC_9-99_Test.md").write_text("# TC 9-99, Test Manual (08/13/2013)\n\n## page 1\n\nApply a tourniquet high and tight.\n", encoding="utf-8")
        lib = Library(library_dir=d, cache_dir=Path(tf.mkdtemp()))
        hit = lib.search("tourniquet", k=5)
        doc = next(p for _s, p in hit if "TC_9-99_Test.md" in p.source)
        self.assertEqual(lib.edition(doc.source), "2013-08-13")
        self.assertEqual(lib.edition("Vanguard study card"), "")

    def test_checked_answers_only_for_near_identical_questions(self):
        r = self.lib.checked_answer("Do I salute a sergeant first class?")
        self.assertTrue(r and r["answer"].startswith("No") and "AR 600-25" in r["source"].split("; "))
        tsp = self.lib.checked_answer("how much should I put in my TSP")     # a card with several sources names them all
        self.assertTrue(tsp and "Thrift Savings Plan" in tsp["source"])
        self.assertEqual(self.lib.checked_answer("Can I wear the APFU for commercial travel?")["answer"], "No")
        for q in ("what is my favorite color", "how do I salute", "what time is 1500", "hi"):
            self.assertIsNone(self.lib.checked_answer(q), q)               # a near miss is no answer at all

    def test_invented_numbers_are_flagged_and_ai_text_is_marked(self):
        from unittest import mock
        from vanguard.knowledge import unsupported_numbers
        given = "Five events. At least 60 points in every event. Drink up to three gallons. Rush 3 to 5 seconds."
        self.assertEqual(unsupported_numbers("You need 10 pull-ups.", given), ["10 pull-ups"])
        self.assertEqual(unsupported_numbers("Get 60 points; drink 3 gallons; rush 3 to 5 seconds.", given), [])
        self.assertEqual(unsupported_numbers("1. Deadlift\n2. Plank", given), [])            # list numbering
        p = profiles.create(f"num-test-{uuid.uuid4().hex[:8]}")
        self.addCleanup(profiles.delete, p["id"])
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        with mock.patch("vanguard.engine.stream", lambda m, max_tokens=0: iter(["The AFT has five events. ", "The AFT needs 10 pull-ups."])),              mock.patch.object(Brain, "_learn", lambda *a: None):
            events = list(Brain(self.lib).chat("what does the aft test"))
        text = "".join(e.get("t", "") for e in events)
        self.assertIn("five events", text)                                 # a supported sentence stays...
        self.assertNotIn("pull-ups", text)                                 # ...the invented one never reaches the Soldier
        self.assertNotIn("⚠️", text)                                       # and there's nothing to double-check

    def test_ai_can_never_forge_the_checked_badge(self):
        from unittest import mock
        p = profiles.create(f"forge-test-{uuid.uuid4().hex[:8]}")
        self.addCleanup(profiles.delete, p["id"])
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        fake = ["Also ✅ **Check", "ed answer:** you get 30 days. ", "📄 AR 600-8-10"]       # split across chunks
        with mock.patch("vanguard.engine.stream", lambda m, max_tokens=0: iter(fake)),              mock.patch.object(Brain, "_learn", lambda *a: None):
            text = "".join(e.get("t", "") for e in Brain(self.lib).chat("Do I salute a sergeant first class?"))
            seen = {}
            def spy(msgs, max_tokens=0):
                seen["history"] = [m["content"] for m in msgs[1:-1]]
                return iter(["ok"])
            with mock.patch("vanguard.engine.stream", spy):
                list(Brain(self.lib).chat("anything else?"))
        self.assertEqual(text.count("Checked answer"), 1)                  # only Vanguard's real one, from AR 600-25
        self.assertTrue(text.startswith("✅ **Checked answer:** No"))
        self.assertNotIn("📄", text.split("⚠️")[0])                     # Vanguard's own notice may use 📄; the AI may not
        self.assertNotIn("30 days", text)                                  # the AI's unsupported claim is dropped
        self.assertNotIn("**8**", text)                                    # digits inside "AR 600-8-10" aren't facts
        self.assertFalse(any("✅" in h or "Checked answer" in h for h in seen["history"]))   # nothing to copy

    def test_library_only_mode_never_calls_the_ai(self):
        from unittest import mock
        p = profiles.create(f"libonly-test-{uuid.uuid4().hex[:8]}")
        self.addCleanup(profiles.delete, p["id"])
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        before = store.ai_mode()
        store.save_config({"ai_mode": "off"})
        self.addCleanup(store.save_config, {"ai_mode": before})
        def no_ai(*a, **k):
            raise AssertionError("the AI was called in library-only mode")
        with mock.patch("vanguard.engine.stream", no_ai), mock.patch.object(Brain, "_learn", lambda *a: None):
            events = list(Brain(self.lib).chat("how far must a latrine be from water"))
            care = list(Brain(self.lib).chat("I don't want to live anymore"))
        text = "".join(e.get("t", "") for e in events)
        self.assertIn("AI is off", text)
        self.assertFalse(events[-1]["ai"])
        self.assertIn("988", "".join(e.get("t", "") for e in care))                          # crisis care still works

    def test_facts_come_from_vanguards_data_not_the_ai(self):
        """From a real test run: the AI invented BAS 'varies by location', an AFT run-time formula, an E-12, and
        'AR 999-99' haircut rules. Those now come from the tables -- or Vanguard says it doesn't know."""
        from unittest import mock
        from vanguard import facts
        lib_dir = self.lib.library_dir
        self.assertIn("13:22", facts.direct_answer("What's the AFT run time for a 20-year-old male to get 100 points?")["answer"])
        self.assertIn("$476.95", facts.direct_answer("How much is BAS for enlisted?")["answer"])
        self.assertTrue(facts.direct_answer("How much does an E-12 make?")["final"])
        self.assertIn("Block 6, ETS", facts.direct_answer("What is the ETS box on my LES?")["answer"])
        self.assertIn("Social Security part", facts.direct_answer('What does "FICA-SOC SEC" mean on my LES?')["answer"])
        if (lib_dir / "_jobs.json").exists():
            self.assertIn("92G", facts.direct_answer("What jobs are like being a cook?", lib_dir)["answer"])
            self.assertIn("11B Infantryman", facts.direct_answer("What does 11B do?", lib_dir)["answer"])
        self.assertIsNone(facts.direct_answer("how do I improve my deadlift", lib_dir))
        self.assertTrue(self.lib.checked_answer("Who do I salute?")["answer"].startswith("Commissioned and warrant"))
        p = profiles.create(f"facts-test-{uuid.uuid4().hex[:8]}")
        self.addCleanup(profiles.delete, p["id"])
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        def no_ai(*a, **k):
            raise AssertionError("the AI was called")
        with mock.patch("vanguard.engine.stream", no_ai), mock.patch.object(Brain, "_learn", lambda *a: None):
            e12 = "".join(e.get("t", "") for e in Brain(self.lib).chat("How much does an E-12 make?"))
            fake = "".join(e.get("t", "") for e in Brain(self.lib).chat("What does AR 999-99 say about haircuts?"))
        self.assertIn("no E-12", e12)
        self.assertIn("doesn't have **AR 999-99**", fake)
        self.assertIn("AR 670-1", fake)                                    # ...and shows what it has on haircuts

    def test_coach_text_never_repeats_or_adds_numbers(self):
        from unittest import mock
        p = profiles.create(f"coach-test-{uuid.uuid4().hex[:8]}")
        self.addCleanup(profiles.delete, p["id"])
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        fake = ["The five events of the AFT are:\n", "- Push-ups: 45 reps\n", "Squats are also tested. ",
                "Train all five events every week. ", "If you have any other questions, feel free to ask!"]
        with mock.patch("vanguard.engine.stream", lambda m, max_tokens=0: iter(fake)), \
                mock.patch.object(Brain, "_learn", lambda *a: None):
            text = "".join(e.get("t", "") for e in Brain(self.lib).chat("What are the events on the Army Fitness Test?"))
        self.assertTrue(text.startswith("✅ **Checked answer:** 3-rep max deadlift"))
        self.assertIn("Train all five events every week.", text)
        for gone in ("45 reps", "events of the AFT are:", "feel free to ask"):
            self.assertNotIn(gone, text)

    def test_made_up_manuals_are_flagged(self):
        from unittest import mock
        p = profiles.create(f"cite-test-{uuid.uuid4().hex[:8]}")
        self.addCleanup(profiles.delete, p["id"])
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        self.assertEqual(self.lib.unknown_pubs("See AR 670-1, DA PAM 670-1, TC 3-22.9 and DA Form 4856."), [])
        with mock.patch("vanguard.engine.stream", lambda m, max_tokens=0: iter(["Keep latrines away from water. ", "Dig it far away (TC 7-25.4)."])),              mock.patch.object(Brain, "_learn", lambda *a: None):
            text = "".join(e.get("t", "") for e in Brain(self.lib).chat("how far is a latrine from water"))
        self.assertIn("away from water", text)
        self.assertNotIn("TC 7-25.4", text)                                # a sentence citing a manual Vanguard lacks is dropped

    def test_checked_answer_comes_first_and_the_model_is_told_to_agree(self):
        from unittest import mock
        p = profiles.create(f"check-test-{uuid.uuid4().hex[:8]}")
        self.addCleanup(profiles.delete, p["id"])
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        seen = {}
        def fake(msgs, max_tokens=0):
            seen["system"] = msgs[0]["content"]
            yield "Model text."
        with mock.patch("vanguard.engine.stream", fake), mock.patch.object(Brain, "_learn", lambda *a: None):
            events = list(Brain(self.lib).chat("Do I salute a sergeant first class?"))
        self.assertTrue(events[0]["t"].startswith("✅ **Checked answer:** No"))
        self.assertIn("ANSWER (already shown to the Cadet)", seen["system"])
        self.assertIn("Do NOT repeat it", seen["system"])                  # the AI only adds help around the answer

    def test_army_terms_always_in_prompt_and_sources_only_when_named(self):
        """'AIT' was once expanded as 'Airborne Infantry Training'. The exact terms ride along with every question,
        and an answer only lists the sources it actually names."""
        from unittest import mock
        p = profiles.create(f"terms-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        self.addCleanup(profiles.delete, p["id"])
        store.save_profile({"stage": "AIT"})
        seen = {}
        def fake(msgs, max_tokens=0):
            seen["system"] = msgs[0]["content"]
            yield "Focus on your MOS skills (FM 7-22)."
        with mock.patch("vanguard.engine.stream", fake), mock.patch.object(Brain, "_learn", lambda *a: None):
            events = list(Brain(self.lib).chat("im just getting there, what do i need to know?"))
        self.assertIn("AIT = advanced individual training", seen["system"])
        self.assertIn("never call it the PFT", seen["system"])
        cites = events[-1]["cites"]
        self.assertTrue(all("FM 7-22" in c["source"] for c in cites), [c["source"] for c in cites])

    def test_questions_about_vanguard_itself_get_the_same_help_every_time(self):
        from unittest import mock
        from vanguard.brain import APP_HELP, app_help_question
        self.assertTrue(app_help_question("How does this work? what am i supposed to do with it"))
        self.assertFalse(app_help_question("how does a tourniquet work"))
        p = profiles.create(f"help-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        self.addCleanup(profiles.delete, p["id"])
        with mock.patch("vanguard.engine.stream", side_effect=AssertionError("no AI needed")):
            events = list(Brain(self.lib).chat("how does this work?"))
        self.assertEqual(events[0]["t"], APP_HELP)
        self.assertEqual(events[-1]["cites"], [])

    def test_cadet_profile_keeps_minors_data_minimal(self):
        """A Cadet's profile holds only name, grade, interests and goals. Body size, sex, rank, MOS or duty station
        are never stored, even if sent (owner's audit, 2026-10-08)."""
        p = profiles.create(f"prof-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        self.addCleanup(profiles.delete, p["id"])
        out = store.save_profile({"name": "Jo Rivera", "grade": "10th grade", "interests": "Public speaking",
                                  "goals": "Lead my squad", "age": "15", "sex": "female", "height": "5 6",
                                  "weight": "120", "rank": "PV1", "mos": "11B", "station": "Fort Jackson"})
        self.assertEqual({k: out.get(k) for k in ("name", "grade", "interests", "goals")},
                         {"name": "Jo Rivera", "grade": "10th grade", "interests": "Public speaking", "goals": "Lead my squad"})
        for gone in ("age", "sex", "height", "weight", "rank", "mos", "station"):
            self.assertNotIn(gone, out)
        text = store.profile_text()
        self.assertIn("Grade: 10th grade", text)
        self.assertNotRegex(text, r"(?i)height|weight|rank|MOS|stationed")

    def test_conversations_are_separate_and_the_old_chat_becomes_the_first(self):
        p = profiles.create(f"chats-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        self.addCleanup(profiles.delete, p["id"])
        store.write_json("chat.json", [{"role": "user", "content": "What is an Article 15?", "t": 1},
                                       {"role": "assistant", "content": "Nonjudicial punishment.", "t": 2}])
        first = store.chat_list()
        self.assertEqual([c["title"] for c in first["chats"]], ["What is an Article 15?"])
        self.assertEqual(len(store.history()), 2)
        new = store.new_chat()
        self.assertEqual(store.history(), [])                       # the AI only sees the current chat
        self.assertEqual(store.new_chat()["id"], new["id"])         # an empty chat is reused, not piled up
        store.add_history("user", "How do I wear the AGSU?")
        self.assertEqual(store.chat_list()["chats"][0]["title"], "How do I wear the AGSU?")
        self.assertEqual(len(store.open_chat(first["current"])), 2)
        self.assertTrue(store.delete_chat(first["current"]))
        self.assertEqual(store.history()[0]["content"], "How do I wear the AGSU?")
        self.assertIn("chats.json", __import__("vanguard.backup", fromlist=["x"]).JSON_FILES)

    def test_addons_report_status_and_unpack_safely(self):
        import tempfile
        import zipfile as zf
        from pathlib import Path
        from vanguard import addons
        st = addons.status()
        self.assertIn("installed", st["ai"]) and self.assertIn("installed", st["voice"])
        with self.assertRaises(ValueError):
            addons.install("bitcoin-miner")
        buf = io.BytesIO()
        with zf.ZipFile(buf, "w") as z:
            z.writestr("model/am/final.mdl", "ok")
            z.writestr("model/../../evil.txt", "no")
        dest = Path(tempfile.mkdtemp()) / "voice-model"
        addons._unpack(buf.getvalue(), dest)
        self.assertTrue((dest / "am" / "final.mdl").exists())
        self.assertFalse((dest.parent.parent / "evil.txt").exists())

    def test_answers_cite_each_page_once_with_its_text(self):
        _text, cites = self.lib.context("what is an article 15")
        self.assertTrue(cites and all(c["text"] and c["where"] for c in cites))
        self.assertEqual(len({(c["source"], c["where"]) for c in cites}), len(cites))

    def test_drill_best_time_counts_only_perfect_runs(self):
        p = profiles.create(f"drill-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        self.assertIsNone(daily.drill_time("9-line", 50, perfect=False)["best"])
        self.assertTrue(daily.drill_time("9-line", 90, perfect=True)["new_best"])
        self.assertFalse(daily.drill_time("9-line", 120, perfect=True)["new_best"])
        self.assertEqual(daily.drill_time("9-line", 80, perfect=True)["best"], 80)

    def test_sleep_summary_and_support_contacts(self):
        import datetime as dt
        p = profiles.create(f"sleep-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        today = dt.date.today()
        store.write_lines("checkins.jsonl", [{"date": (today - dt.timedelta(days=d)).isoformat(), "mood": 3, "stress": 3,
                                              "sleep": h, "note": ""} for d, h in [(0, 5), (1, 8), (2, 6.5), (9, 4)]])
        sl = daily.sleep_summary()
        self.assertEqual((sl["nights"], sl["short7"], sl["debt7"], sl["avg7"]), (3, 2, 2.5, 6.5))   # day 9 is outside the week
        rows = daily.save_support([{"role": "Chaplain", "name": "CH Smith", "phone": "555-0100"}, {"role": "Hacker", "name": "x"},
                                   {"role": "Family", "name": "", "phone": ""}, "junk"])
        self.assertEqual([r["role"] for r in rows], ["Chaplain", "Other"])
        self.assertEqual(daily.support(), rows)

    def test_crisis_without_ai_gets_care_never_library_text(self):
        from unittest import mock
        p = profiles.create(f"care-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        daily.save_support([{"role": "Chaplain", "name": "CH Reyes", "phone": "555-0100"}])
        with mock.patch("vanguard.engine.stream", side_effect=RuntimeError("no model")), \
             mock.patch.object(Brain, "_learn", lambda *a: None):
            events = list(Brain(self.lib).chat("I don't want to live anymore"))
        text = "".join(e.get("t", "") for e in events)
        self.assertIn("988", text)
        self.assertLess(text.index("CH Reyes"), text.index("I'm here"))     # their people, right under the crisis lines
        self.assertNotIn("library says", text)
        self.assertNotIn("page ", text)

    def test_simplify_rewrites_only_the_answer(self):
        from unittest import mock
        seen = {}

        def fake_stream(msgs, max_tokens):
            seen["msgs"] = msgs
            yield "Plain words."
        with mock.patch("vanguard.engine.stream", fake_stream):
            out = "".join(e.get("t", "") for e in Brain(self.lib).simplify("Per AR 670-1, hair must be neat."))
        self.assertEqual(out, "Plain words.")
        self.assertEqual(len(seen["msgs"]), 2)                       # instructions + the answer; no history or profile
        self.assertIn("Keep every fact", seen["msgs"][0]["content"])
        self.assertEqual(seen["msgs"][1]["content"], "Per AR 670-1, hair must be neat.")
        with mock.patch("vanguard.engine.stream", side_effect=RuntimeError("no model")):
            self.assertIn("isn't running", "".join(e.get("t", "") for e in Brain(self.lib).simplify("x")))

    def test_exam_mode(self):
        p = profiles.create(f"exam-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        lib = LibraryTests.lib
        ex = exam.start(lib, "Reports", 5)
        self.assertEqual(len(ex["questions"]), 5)
        self.assertNotIn("key", ex)                                             # the answer key stays on the server
        for q in ex["questions"]:
            self.assertEqual(len(q["choices"]), 4)
            self.assertEqual(len({c.lower() for c in q["choices"]}), 4)        # no duplicate choices
        key = store.read_json("exam_current.json", {})["key"]
        r = exam.submit(ex["id"], {str(i): k["answer"] for i, k in enumerate(key[:3])})   # 3 right, 2 blank
        self.assertEqual((r["right"], r["total"], r["late"]), (3, 5, False))
        with self.assertRaises(ValueError):
            exam.submit(ex["id"], {})                                          # one submission per exam
        self.assertEqual(exam.history()["best"]["Reports"]["right"], 3)
        with self.assertRaises(ValueError):
            exam.start(lib, "No such topic")

    def test_where_am_i_in_basic(self):
        import datetime as dt
        p = profiles.create(f"bct-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        today = dt.date.today()
        self.assertIsNone(daily.bct()["week"])
        st = daily.save_bct((today - dt.timedelta(days=15)).isoformat())       # day 16 -> week 3
        self.assertEqual((st["week"], st["phases"][st["phase"]][0], st["phases"][st["next"]][0]), (3, "Red", "White"))
        st = daily.save_bct((today + dt.timedelta(days=5)).isoformat())
        self.assertEqual((st["week"], st["days_to_start"], st["phases"][st["next"]][0]), (0, 5, "Yellow"))
        self.assertIsNone(daily.save_bct((today - dt.timedelta(days=80)).isoformat())["phase"])   # week 12: done

    def test_rename_profile(self):
        a = profiles.create(f"ren-a-{uuid.uuid4().hex[:8]}")
        b = profiles.create(f"ren-b-{uuid.uuid4().hex[:8]}")
        profiles.rename(a["id"], "  New   Name  " + a["id"][:4])
        self.assertEqual(profiles.get(a["id"])["name"], "New Name " + a["id"][:4])
        with self.assertRaises(ValueError):
            profiles.rename(a["id"], b["name"].upper())                         # names are unique, any case
        with self.assertRaises(ValueError):
            profiles.rename(a["id"], "   ")

    def test_pcs_checklist(self):
        import datetime as dt
        p = profiles.create(f"pcs-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        st = daily.save_pcs({"report_date": (dt.date.today() + dt.timedelta(days=30)).isoformat()})
        self.assertEqual(st["days"], 30)
        self.assertIn("orders", daily.save_pcs({"toggle": "orders"})["done"])
        self.assertNotIn("orders", daily.save_pcs({"toggle": "orders"})["done"])
        c = daily.save_pcs({"add": "Call my sponsor"})["custom"][0]
        daily.save_pcs({"toggle": c["id"]})
        st = daily.save_pcs({"remove": c["id"]})
        self.assertEqual((st["custom"], st["done"]), ([], []))

    def test_family_profile_changes_who_vanguard_talks_to(self):
        from unittest import mock
        p = profiles.create(f"family-test-{uuid.uuid4().hex[:8]}", "family")              # old value still works
        self.assertEqual(profiles.get(p["id"])["kind"], "guardian")
        odd = profiles.create(f"odd-{uuid.uuid4().hex[:8]}", "hacker")
        self.addCleanup(profiles.delete, odd["id"])
        self.assertEqual(odd["kind"], "cadet")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        seen = []
        with mock.patch("vanguard.engine.stream", lambda msgs, max_tokens: (seen.append(msgs), iter(["ok"]))[1]), \
             mock.patch.object(Brain, "_learn", lambda *a: None):
            list(Brain(self.lib).chat("What do ranks mean?", family=True))
            list(Brain(self.lib).chat("What do ranks mean?"))
        self.assertIn("PARENT OR GUARDIAN", seen[0][0]["content"])
        self.assertNotIn("FAMILY MEMBER", seen[1][0]["content"])

    def test_quiz_prefers_missed_questions(self):
        p = profiles.create(f"quiz-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        brain = Brain(self.lib)
        qs = brain.quiz(n=10)
        self.assertEqual(len(qs), 10)
        self.assertEqual(len({q["id"] for q in qs}), 10)


class SafetyTests(unittest.TestCase):
    def test_crisis_detected(self):
        self.assertTrue(safety.check("I don't want to live anymore")["care"])
        self.assertIn("988", safety.check("thinking about killing myself")["banner"])

    def test_assault_detected(self):
        self.assertIn("800-656-4673", safety.check("I was sexually assaulted by someone in my platoon")["banner"])

    def test_normal_message_is_not_crisis(self):
        self.assertFalse(safety.check("my PT run is killing me lol, how do I get faster")["care"])

    def test_opsec(self):
        self.assertTrue(safety.check("we're deploying on March 3 to the border")["opsec"])
        self.assertFalse(safety.check("what is OPSEC?")["opsec"])


class FaithTests(unittest.TestCase):
    def test_references(self):
        self.assertEqual(parse_ref("John 3:16"), ("JHN", 3, 16, 16))
        self.assertEqual(parse_ref("1 Cor 13:4-7"), ("1CO", 13, 4, 7))
        self.assertEqual(parse_ref("Psalm 23"), ("PSA", 23, 0, 0))
        self.assertEqual(parse_ref("Quran 2:255"), ("QUR", 2, 255, 255))
        self.assertEqual(parse_ref("1 Nephi 3:7"), ("1NE", 3, 7, 7))
        self.assertIsNone(parse_ref("hello there"))

    @unittest.skipUnless((ROOT / "faith" / "catalog.json").exists(), "faith library not installed")
    def test_lookup_and_compare(self):
        f = Faith()
        r = f.lookup("John 3:16", [], compare=True)
        self.assertGreaterEqual(len(r["results"]), 4)
        self.assertIn("loved the world", r["results"][0]["verses"][0]["text"])


class VoiceTextTests(unittest.TestCase):
    def test_spoken_numbers_and_terms(self):
        from vanguard.voice import tidy
        cases = {
            "what is an article fifteen and how do i read a great coordinate":
                "What is an article 15 and how do i read a grid coordinate",
            "explain article one hundred twelve a": "Explain article 112 a",
            "i ran two miles in fifteen forty": "I ran 2 miles in 15 40",
            "twenty five push ups": "25 push ups",
            "one hundred and five": "105",
            "article eighty six": "Article 86",
            "the u c m j applies to me": "The UCMJ applies to me",
        }
        for spoken, expected in cases.items():
            self.assertEqual(tidy(spoken), expected)


class StoreTests(unittest.TestCase):
    def setUp(self):
        p = profiles.create(f"store-test-{uuid.uuid4().hex[:8]}")
        self._tok = store.use_profile(profiles.folder(p["id"]))

    def tearDown(self):
        store.reset_profile(self._tok)

    def test_no_profile_no_data(self):
        tok = store.use_profile(None)
        try:
            with self.assertRaises(store.NoProfile):
                store.log_entries()
            with self.assertRaises(store.NoProfile):
                store.add_log("PT", "should not be written anywhere")
        finally:
            store.reset_profile(tok)

    def test_log_and_memory_roundtrip(self):
        e = store.add_log("PT", "2-mile run", score="15:40")
        self.assertTrue(any(x["id"] == e["id"] for x in store.log_entries()))
        self.assertTrue(store.remember("Working on plank time"))
        self.assertFalse(store.remember("Working on plank time"))


class FitnessTests(unittest.TestCase):
    """Values checked by hand against the official AFT score tables (effective 1 June 2025)."""

    def test_event_points_match_the_official_tables(self):
        s = fitness.score_event
        self.assertEqual(s("MDL", 340, 20, "M"), 100)
        self.assertEqual(s("MDL", 220, 20, "F"), 100)
        self.assertEqual(s("MDL", 335, 20, "M"), 98)          # the 99 row is "---" for this column
        self.assertEqual(s("MDL", 140, 20, "M"), 50)          # below 60 the table steps by 10
        self.assertEqual(s("HRP", 15, 20, "M"), 60)
        self.assertEqual(s("SDC", 148, 20, "M"), 60)          # 2:28
        self.assertEqual(s("SDC", 149, 20, "M"), 59)
        self.assertEqual(s("PLK", 220, 20, "F"), 100)         # 3:40
        self.assertEqual(s("2MR", 15 * 60 + 28, 63, "M"), 100)  # over-62 column

    def test_plan_from_logged_tests(self):
        rows = [{"date": "2026-09-01", "text": "AFT (general standard, 22-26): MDL 230 = 77, HRP 38 = 81, SDC 2:05 = 74, PLK 2:00 = 70, 2MR 17:30 = 75"},
                {"date": "2026-10-01", "text": "AFT (general standard, 22-26): MDL 250 = 81, HRP 40 = 83, SDC 1:55 = 78, PLK 2:30 = 80, 2MR 16:30 = 84"},
                {"date": "2026-10-02", "text": "2-mile run 16:40, felt strong"}]
        p = fitness.plan(rows)
        self.assertEqual(len(p["tests"]), 2)                           # the plain run note isn't a test
        self.assertEqual(p["weakest"], "SDC")
        self.assertEqual({r["event"]: r["change"] for r in p["rows"]}["PLK"], 10)
        self.assertIn("from 78 to 88 points", p["goal"]["short"])
        self.assertEqual(fitness.plan([])["tests"], [])

    def test_combat_standard_is_sex_neutral_and_needs_350(self):
        raw = {"MDL": "220", "HRP": "53", "SDC": "1:55", "PLK": "3:40", "2MR": "16:00"}
        general = fitness.score_test(raw, 20, "F", "general")
        combat = fitness.score_test(raw, 20, "F", "combat")
        self.assertEqual(general["total"], 500)
        self.assertLess(combat["total"], 500)
        self.assertEqual((general["min_total"], combat["min_total"]), (300, 350))

    def test_pass_needs_every_event(self):
        r = fitness.score_test({"MDL": "340", "HRP": "58", "SDC": "1:29", "PLK": "3:40"}, 20, "M")
        self.assertFalse(r["complete"])
        self.assertFalse(r["passed"])
        r = fitness.score_test({"MDL": "340", "HRP": "58", "SDC": "1:29", "PLK": "3:40", "2MR": "22:45"}, 20, "M")
        self.assertEqual(r["failed_events"], ["2MR"])
        self.assertFalse(r["passed"])                        # 400 total, but one event under 60
        self.assertTrue(fitness.score_test({"2MR": "16:3x"}, 20, "M")["errors"])


class RadioVoiceTests(unittest.TestCase):
    """Parsing a spoken 9-line (the recognizer itself is optional and not needed here)."""

    def test_spoken_nine_line_splits_into_lines(self):
        r = voice.nine_line("medevac request over line one one seven sierra papa uniform one two three four five six "
                            "seven eight line two three five decimal seven five zero bulldog three one line three one "
                            "alpha break two charlie line four alpha line five one lima break two alpha line six x ray "
                            "line seven charlie line eight alpha break echo over")
        self.assertEqual(r["lines"], {"1": "17SPU12345678", "2": "35.750 BULLDOG 31", "3": "1A BREAK 2C", "4": "A",
                                      "5": "1L BREAK 2A", "6": "X", "7": "C", "8": "A BREAK E"})
        self.assertTrue(r["opened"] and r["closed"])

    def test_missed_line_number_is_taken_in_order(self):
        r = voice.nine_line("line four alpha line five one lima line november line charlie")
        self.assertEqual((r["lines"]["6"], r["lines"]["7"]), ("N", "C"))
        self.assertFalse(r["closed"])

    def test_radio_numbers(self):
        self.assertEqual(voice.radio_tokens("niner tree fife x ray ray"), ["9", "3", "5", "X"])


class BoardTests(unittest.TestCase):
    def test_word_grade(self):
        ref = "Hill, ridge, valley, saddle, depression"
        self.assertEqual(board.word_grade("hill ridge valley saddle and depression", ref)["verdict"], "go")
        g = board.word_grade("a hill and a valley", ref)
        self.assertEqual((g["verdict"], g["missing"]), ("partial", ["ridge", "saddle", "depression"]))
        self.assertEqual(board.word_grade("no idea", ref)["verdict"], "nogo")

    def test_ai_grade_used_when_available_else_words(self):
        from unittest import mock
        with mock.patch("vanguard.engine.quick", return_value='{"verdict": "go", "why": "Same meaning."}'):
            self.assertEqual(board.grade("q", "A chaplain", "the chaplain")["how"], "ai")
        with mock.patch("vanguard.engine.quick", return_value=""):
            self.assertEqual(board.grade("q", "A chaplain", "the chaplain")["how"], "words")

    def test_creed_recitation_marks_each_word(self):
        self.assertTrue(board.recite(board.SOLDIERS_CREED)["perfect"])
        r = board.recite(board.SOLDIERS_CREED.replace("I will never quit.", "I will never give up."))
        self.assertFalse(r["perfect"])
        self.assertEqual(r["right"], r["total"] - 1)
        self.assertEqual([w["w"] for line in r["lines"] for w in line if not w["ok"]], ["quit"])
        self.assertEqual(r["extra"], ["give", "up"])


class PayTests(unittest.TestCase):
    """Values from the DFAS basic pay tables and BAS effective January 1, 2026."""

    def test_pay_questions_get_table_numbers(self):
        # the small model once said an E-4 with 3 years "would be at pay grade E-5" and invented the pay
        a = pay.pay_answer("What does an E-4 with 3 years make in 2026?")["answer"]
        self.assertIn("$3,303.00", a)
        self.assertIn("$476.95", a)
        self.assertIn("E-4", a)
        self.assertIn("$3,142.20", pay.pay_answer("how much does a specialist get paid")["answer"])
        self.assertIn("$2,225.70", pay.pay_answer("pay for an E-1 with 3 months")["answer"])
        self.assertIsNone(pay.pay_answer("what does an E-4 do"))
        self.assertIsNone(pay.pay_answer("How much is BAH for an E-5"))

    def test_years_of_service_columns(self):
        self.assertEqual(pay.basic_pay("E-4", 2), 3142.20)       # "2 or less"
        self.assertEqual(pay.basic_pay("E-4", 2.5), 3303.00)     # "Over 2"
        self.assertEqual(pay.basic_pay("E-1", 0.2, months=2), 2225.70)   # E-1 under 4 months (note 5)
        with self.assertRaises(ValueError):
            pay.basic_pay("E-9", 5)                              # E-9 starts at "Over 10"
        self.assertEqual(pay.basic_pay("O-1", 1), 4150.20)       # officers
        self.assertEqual(pay.basic_pay("W-5", 21), 10169.70)     # W-5 starts at "Over 20"
        with self.assertRaises(ValueError):
            pay.basic_pay("O-10", 10)                            # O-9/O-10 start at "Over 20"

    def test_les_decoder_has_every_block_in_dfas_words(self):
        d = pay.les_fields()
        self.assertEqual([f["n"] for f in d["fields"]], list(range(1, 79)))
        f = {x["n"]: x for x in d["fields"]}
        self.assertEqual(f[19]["label"], "EOM PAY")
        self.assertIn("End-of-Month payday", f[19]["active"])
        self.assertIn("do not have allotments", f[12]["reserve"])          # Reserve/Guard wording kept separately
        self.assertNotIn("reserve", f[13])                                   # same text in both guides
        self.assertTrue(all(any(s["from"] <= n <= s["to"] for s in d["sections"]) for n in f))

    def test_estimate_adds_bas_and_bah(self):
        r = pay.estimate("E-4", 2.5, None, 1200)
        self.assertEqual((r["basic"], r["bas"], r["bah"], r["total"]), (3303.00, 476.95, 1200.0, 4979.95))
        self.assertEqual(r["basic_effective"], "January 1, 2026")


class LettersAndJobsTests(unittest.TestCase):
    def test_letter_opsec_check_flags_what_shares_too_much(self):
        from vanguard import letters
        flags = {f["sentence"]: f["why"] for f in letters.opsec_check(
            "Miss you all. We ship out on March 3rd with 40 guys. Our grid is 18S UJ 2337 0651. "
            "My drill sergeant yelled today. The gate code is 4471.")}
        self.assertNotIn("Miss you all.", flags)
        self.assertNotIn("My drill sergeant yelled today.", flags)
        ship = flags["We ship out on March 3rd with 40 guys."]
        for why in ("mentions movements or missions", "gives a specific date", "gives numbers of people or equipment"):
            self.assertIn(why, ship)
        self.assertIn("gives a location or grid", flags["Our grid is 18S UJ 2337 0651."])
        self.assertIn("mentions security details", flags["The gate code is 4471."])

    def test_letters_and_contacts_are_kept_per_profile(self):
        from vanguard import letters
        p = profiles.create(f"letters-test-{uuid.uuid4().hex[:8]}")
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        c = letters.save_contact({"name": "Mom", "relation": "Mother", "address": "1 Main St"})
        l1 = letters.save_letter({"to": "Mom", "text": "Hi Mom"})
        letters.save_letter({"id": l1["id"], "to": "Mom", "text": "Hi Mom, edited"})      # edit in place
        self.assertEqual([x["text"] for x in letters.letters()], ["Hi Mom, edited"])
        self.assertTrue(letters.delete_contact(c["id"]))
        self.assertEqual(letters.contacts(), [])

    def test_job_search_finds_everyday_words_and_codes(self):
        from vanguard import careers
        lib = ROOT / "library"
        if not (lib / "_jobs.json").exists():
            self.skipTest("job list not downloaded (tools/fetch_library.py)")
        first = lambda q: [j["code"] for j in careers.search(lib, q)["jobs"][:3]]
        self.assertEqual(first("medic")[0], "68W")
        self.assertIn("92G", first("cook"))
        self.assertEqual(first("11B")[0], "11B")
        self.assertEqual(careers.search(lib, "zzqqxx")["jobs"], [])
        self.assertGreater(careers.search(lib)["total"], 200)


class BooksTests(unittest.TestCase):
    """Free books (vanguard/books.py): chapters from each book's headings, contents lists skipped, search, place."""

    def test_chapters_skip_contents_and_keep_book_names(self):
        from vanguard import books
        para = "Some words of the chapter. " * 30
        text = ("CONTENTS\nCHAPTER I. THE FIRST\nCHAPTER II. THE SECOND\n\n" + "Preface text. " * 40 +
                "\n\nBOOK I. ON THINGS\n\nCHAPTER I.\n\n" + para + "\n\nCHAPTER II.\n\n" + para +
                "\n\nSKETCHES FOR BOOK II PLANS\n\nCHAPTER I.\n\n" + para)
        chs = books.split_chapters(text, r"^\s*CHAPTER [IVXL]+\..*$", parts=r"^\s*(SKETCHES FOR )?BOOK [IVX]+\b.*$")
        titles = [c["title"] for c in chs]
        self.assertEqual(titles[0], "Front matter")                         # the contents list isn't a chapter
        self.assertEqual(titles[1], "Book I · Chapter I. The First")        # title borrowed from the contents
        self.assertEqual(titles[-1], "Book II (sketches) · Chapter I. The First")
        self.assertEqual(len(chs), 4)
        self.assertEqual(books.split_chapters("Just one short document.", None)[0]["title"], "Full text")

    def test_gutenberg_license_kept_on_disk_but_not_shown(self):
        from vanguard import books
        raw = "Header\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nThe book.\n*** END OF THE PROJECT GUTENBERG EBOOK X ***\nLicense"
        self.assertEqual(books._body(raw), "The book.")

    def test_search_and_place_per_profile(self):
        import tempfile
        from unittest import mock
        from vanguard import books
        d = Path(tempfile.mkdtemp())
        (d / "declaration.txt").write_text("We hold these truths to be self-evident, that all men are created equal.",
                                           encoding="utf-8")
        p = profiles.create(f"books-test-{uuid.uuid4().hex[:8]}")
        self.addCleanup(profiles.delete, p["id"])
        tok = store.use_profile(profiles.folder(p["id"]))
        self.addCleanup(store.reset_profile, tok)
        with mock.patch.object(books, "BOOKS_DIR", d):
            books._cache.clear()
            self.addCleanup(books._cache.clear)
            hits = books.search("all  men are created")
            self.assertEqual((hits[0]["id"], hits[0]["ch"]), ("declaration", 0))
            self.assertEqual(books.search("ab"), [])                        # too short to search
            books.save_place("declaration", 0)
            shelf = books.shelf()
            row = next(b for b in shelf["books"] if b["id"] == "declaration")
            self.assertTrue(row["installed"])
            self.assertEqual(row["at"], 0)
            self.assertIn("The Art of War", shelf["missing"])               # not downloaded in this test
            with self.assertRaises(ValueError):
                books.read("art-of-war", 0)


if __name__ == "__main__":
    unittest.main()
