# Vanguard — Reuse Plan (Phase 0, 2026-10-08)

Every inherited module, what happens to it, and why. **Nothing working is deleted**: Soldier-specific features move
behind the **Serve → Explore Military Service** boundary (opt-in, informational, the instructor can switch it off).

Legend: **Keep** (as is, renamed) · **Adapt** (reused with changes) · **Serve/Military** (moved into Explore
Military Service) · **Retire** (removed, with the reason).

## Platform (core / security)

| Module | Decision | Vanguard area | Notes |
|---|---|---|---|
| server.py | Adapt | core | Same server and routes; add role checks per route (Cadet / Instructor / Admin) and LAN classroom mode as the normal setup. |
| security.py | Adapt | security | PINs, sessions, lockouts, CSRF/rebinding guards all kept. Admin PIN → **Instructor PIN**. Add roles. |
| vault.py | Keep | security | AES-256-GCM, key wrapping, recovery codes, sealed backups. |
| store.py | Adapt | core / cadet | Keep the sealed per-profile store; add new record types (lessons done, scenarios, service log, goals). |
| profiles.py | Adapt | cadet / instructor | `kind` gains roles: cadet, instructor, guardian (was family). Add program/class/squad, LET level. |
| backup.py | Keep | security | Add instructor-controlled class export later. |
| integrity.py | Keep | core | New Vanguard release key (owner generates). |
| addons.py | Keep | ai | Installs the offline AI model from inside the app. |
| engine.py | Keep | ai | Offline-first AI. Respect the new AI mode setting. |
| safety.py | Keep | core | Crisis care stays for every profile; adjust wording for teenagers (school counselor, trusted adult, 988). |

## Knowledge and AI (learn / ai)

| Module | Decision | Area | Notes |
|---|---|---|---|
| knowledge.py | Keep | curriculum | Source-first library, cards, BM25, checked answers, citation and number checks — the strongest part of the inherited app. Cards gain optional `program`, `let_level`, `competency`, `objective`. |
| brain.py | Adapt | ai | Same pipeline. AI modes: **Off** (no AI), **Library only** (default — existing library-only mode), **Library + AI** (coach sentences, labeled). Persona rewritten for Cadets. |
| facts.py | Serve/Military | serve | Pay, BAS, LES, jobs answers stay exactly as strict; shown in Explore Military Service. AFT lookups move to Train as reference data. |
| cards/*.md | Split | curriculum | General cards (values, customs and courtesies, ranks, drill, first aid, heat injuries, nutrition, sleep, H2F, OPSEC, citizenship) → Learn. Soldier-life cards (LES, GI Bill, TA, training pipeline, MEDEVAC, SALUTE/LACE, UCMJ) → Explore Military Service. Each card gets curriculum tags; nothing claims to be official JROTC curriculum. |

## Learn

| Module | Decision | Notes |
|---|---|---|
| study (Brain.quiz / progress) | Adapt | Becomes concept-level mastery (spec §22): track per concept, not per question. |
| exam.py | Adapt | Lesson quizzes and instructor-assigned tests. |
| daily.py → Daily 10 | Adapt | Instructor-configurable category mix (spec §21); missed concepts feed review. |
| books.py | Keep | Library shelf: Constitution, Bill of Rights, Federalist, American Military History I/II, classics. |
| board.py | Adapt | Becomes oral-question practice (useful for JROTC boards/competitions); instructor-enabled. |
| faith.py | Retire from default build | Public schools: keep the module in code, **off by default and not shown**; documented, not deleted. |

## Lead (new)

Nothing inherited. New scenario engine, decision log and portfolio (MIGRATION_PLAN.md, Phase 5).

## Train

| Module | Decision | Notes |
|---|---|---|
| fitness.py | Adapt | Keep table scoring as an optional reference. Default view: **personal improvement** (current, previous, goal, trend), instructor-defined events and units, no pass/fail language. |
| log (logbook) | Adapt | Fitness and goal history. |
| check-ins / sleep (daily.py) | Adapt | Private healthy-habits check-in; never shown to other Cadets; instructor sees only what policy allows (decide in Phase 3). |

## Serve

| Module | Decision | Notes |
|---|---|---|
| (new) service log | New | Projects, hours, dates, organization, role, reflection, instructor verification. |
| pay.py, facts.py pay/LES | Serve/Military | "What military pay looks like", "Reading a military pay statement". |
| careers.py | Serve/Military | Army jobs explorer (also the spec's "military careers"). |
| daily.py PCS / leave / budget | Serve/Military (PCS, leave) · Learn (budget → financial literacy) | |
| letters.py | Serve | Letters to family, service members, veterans; OPSEC check stays. |
| family profiles | Adapt | Become guardian profiles (spec: secondary users), off by default. |
| voice.py 9-line radio | Serve/Military | Optional; off by default. Speech input/read-aloud stay for accessibility. |

## My Progress / Instructor (new, built on store + reports)

Portfolio, competency mastery, growth metrics, instructor dashboard, assignments, classroom mode, pilot mode and
reports are new. They reuse store, profiles, security and the existing printable views.

## Web front end

| File | Decision | Notes |
|---|---|---|
| index.html | Adapt | New navigation: Learn / Lead / Train / Serve / My Progress; Instructor area; calm, professional theme (spec §37). |
| core.js | Keep | Fetch wrapper, lock screen, PIN recovery, backup UI. |
| ask.js | Adapt | "Ask" becomes a helper inside Learn, not the home screen (spec §4). |
| study.js | Adapt | Learn: lessons, cards, quizzes, books. Jobs move to Serve. |
| log.js | Split | Train (fitness, goals), Serve (service log, Explore Military Service: pay, PCS, letters). |
| me.js | Adapt | Profile, PIN; instructor settings move to the Instructor area. |
| intake.js | Adapt | First run for a Cadet (name, class, LET level) or an Instructor (program setup). |
| voice.js | Keep | Read-aloud and speech input (accessibility). |
| faith.js | Retire from default build | See faith.py. |

## Tools, site, tests

| Item | Decision |
|---|---|
| tools/fetch_library.py, fetch_books.py, cmh_convert.py, sign.py, setup.py, install_voice.py | Keep (renamed). |
| tools/pay_*.py, les_fields.py, aft_tables.py | Keep — data builders for Serve/Train reference data. |
| tools/fetch_faith.py | Keep in code, not run by default. |
| site/ | Rebuild: Vanguard landing page, /pilot, /security (spec §34–36). Build/sign/release flow kept with a new key and a new Cloudflare worker for vanguard.winklers-llc.com. |
| tests/ | Keep all; rename; add role, permission and data-isolation tests from Phase 2 on. |
