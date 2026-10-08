# Vanguard — Migration Plan (Phase 0, 2026-10-08)

## 1. Target layout (spec §30)

Rename the package `recruit/` → `vanguard/`, then split it into sub-packages in small, tested steps (never one big
move):

```
vanguard/
  core/        server, config, feature flags, store, profiles, integrity, addons
  security/    security (PINs, sessions, roles), vault, backup
  curriculum/  knowledge (library + cards), books, lessons, scenarios, curriculum tags
  ai/          brain, engine, facts, safety
  cadet/       study/mastery, daily, fitness, service log, goals, portfolio
  instructor/  classes, assignments, dashboard, classroom mode, pilot
  reports/     portfolio and pilot reports (printable HTML → PDF via the browser)
  serve_military/  pay, careers, letters, PCS (Explore Military Service, behind a flag)
content/
  cards/       study cards (moved out of the code package), each tagged program / LET / competency
  scenarios/   leadership scenarios (markdown, same pattern as cards)
data/          reference tables (pay, LES, AFT)
```

Content (cards, scenarios, lessons from instructors) never lives in generic application code (spec §30, §48).

## 2. Phase 1 rename checklist

- Package `recruit` → `vanguard`; imports in code, tests, tools, site/build.py, installer.iss, run.py.
- Data folder `~/.cursiv-recruit` → `~/.vanguard`; env `RECRUIT_DATA`, `RECRUIT_NO_WARMUP` → `VANGUARD_*`.
- Cookie `recruit_session` → `vanguard_session`.
- Scripts `install-recruit.*`, `start-recruit.*` → `install-vanguard.*`, `start-vanguard.*`.
- Installer/app names, window titles, update zip names (`Vanguard-<version>.zip`), release tags.
- Docs: README, SECURITY, LIBRARY, CLAUDE.md rewritten for Vanguard.
- UI wording: "Soldier" → "Cadet" in general UI; Soldier wording stays only where content is about Soldiers.
- A test fails if "cursiv" or "recruit" appears in tracked files (tiny allow-list for genuine uses such as
  "military recruiting" inside Explore Military Service content).
- New release key: owner generates it locally (`python tools/sign.py --new-key`), commits only the public key.
- Version 0.1.0.

## 3. Data model additions

| Record | Where | Fields |
|---|---|---|
| program (device config) | core | name, program_type (JROTC), branch (Army first; Navy/Air Force/Marine/Space Force later), school, curriculum id, standards id |
| profile (extended) | profiles index | role: cadet / instructor / guardian; class, platoon, squad; LET level |
| class / unit | instructor store | id, name, kind (class/platoon/squad), parent, members |
| lesson | content + instructor store | title, LET level, competency, objective, source, content, questions, vocabulary, scenario ids, reflection prompt, instructor notes (instructor-only) |
| assignment | instructor store | lesson/quiz/scenario/reflection refs, recipients (cadets/units/all), due date |
| assignment status | cadet store | assignment id, state (not started / in progress / complete), score, submitted reflection |
| scenario | content/scenarios | situation, choices, per-choice outcome, principles, strengths, weaknesses, alternatives, competency |
| leadership log entry | cadet store | situation, decision, reasoning, outcome, reflection, lesson learned |
| service entry | cadet store | project, date, hours, organization, role, reflection, verified_by, verified_at |
| fitness entry / goal | cadet store | event (instructor-defined), value, unit, date; goal value and date |
| concept mastery | cadet store | concept id → attempts, correct, last seen, next review |
| pilot config / feedback | instructor store | school, program, instructor, dates, cadet count, metric toggles, survey answers |

## 4. Permission model for the laptop-server classroom

The instructor's laptop runs Vanguard in LAN mode; Cadets use a browser on school devices or phones.

- **Every profile has a PIN** (already required for LAN mode). Cadet data stays sealed with the Cadet's own key.
- **Instructor visibility without breaking encryption:** each Cadet's data key is additionally wrapped for the
  **program key** (unlocked by the Instructor PIN), the same way the recovery code wraps it today. The instructor
  can then read assignment status, scores, fitness, service and reflections for reports. Private check-ins and
  any field marked private are stored in a separate file that is **not** readable with the program key.
  (Decide with the owner before Phase 3; document it on the /security page.)
- **Route roles:** every `/api/` route declares cadet / instructor / admin. Cadet sessions can only touch their own
  profile. Instructor routes need an instructor session. Admin settings (AI mode, modules, standards, exports)
  need the Instructor PIN again.
- **Never reachable from a Cadet session:** other Cadets' data, instructor notes, instructor analytics, other
  grades, admin config, security settings, API keys, source management. Each gets an explicit test (spec §47).
- No public leaderboards by default; competition is an instructor opt-in (spec §27).

## 5. Phases, deliverables and tests

| Phase | Deliverables | Tests |
|---|---|---|
| 0 | ARCHITECTURE.md, REUSE_PLAN.md, MIGRATION_PLAN.md | existing suite green |
| 1 | Rebrand; Cadet + Instructor navigation; product config; feature flags; AI modes (Off / Library only default / Library + AI); Instructor PIN; Serve → Explore Military Service | no-trace test, flags, AI-mode routing |
| 2 | Cadet model: roles, class membership, LET level, goals, progress records | role assignment, data isolation |
| 3 | Instructor: profile, program setup, classes/platoons/squads, add Cadets, program-key wrapping | instructor sees only what policy allows; Cadet can't reach instructor routes |
| 4 | Lessons: create, assign, complete, track | assignment delivery, completion counts |
| 5 | Leadership scenarios: engine, choices, explanation, reflection, leadership log; classroom mode voting | scenario scoring, log storage, no combat content |
| 6 | Train: configurable fitness events, personal bests, trends, goals; AFT table as optional reference | improvement math, no pass/fail wording |
| 7 | Serve: service log, hours, roles, reflections, instructor verification | verification permissions |
| 8 | My Progress: dashboard, concept mastery, growth metrics, printable portfolio | progress math, export content controls |
| 9 | Instructor analytics: class dashboard, completion, participation, growth, reports | aggregates, no cross-Cadet leakage |
| 10 | Pilot: config, metrics, feedback, end-of-pilot report | report generation |

Each phase ends with: all tests green, a short REPORT entry (found / changed / why / preserved / files / tested /
remaining), commit, push.

## 6. Open questions for the owner

1. Instructor visibility: is the program-key design in §4 acceptable, and which Cadet fields stay private from
   the instructor (proposed: check-ins and anything the Cadet marks private)?
2. Guardian profiles in the pilot: off (proposed) or on?
3. Faith library: off and hidden in Vanguard (proposed), or available as an instructor opt-in?
4. Which JROTC program for the pilot (Army JROTC assumed), and which curriculum documents may be used as sources?
   Until known, lessons carry only instructor content and public-domain sources; nothing is labeled official.
