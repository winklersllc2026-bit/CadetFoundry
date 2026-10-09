# HANDOFF — Vanguard (read this first)

Written 2026-10-08 by the desktop Claude session for a cloud Claude session to continue the work.
The owner is Joshua (Winklers LLC). Budget is limited (~$17 of cloud credit): **do Phase 0, then Phase 1, then stop
and report.** Do not start Phase 2+ without the owner's go-ahead.

## What this repo is

Vanguard is a JROTC learning and leadership platform. **Tagline:** "Leadership. Learning. Character." **Built by:**
Winklers LLC. **Site:** vanguard.winklers-llc.com.

The code is a **fresh copy** (no git history) of the owner's other app, an offline study companion for Army
Soldiers. That app's name is still all over this code — removing every trace of it is part of Phase 1. Never link
to it, mention it on the site, or reuse its release signing key.

The owner's full product spec (the "Cursiv Cadet" spec — **ignore that name; the product is Vanguard**) is the
north star: Learn / Lead / Train / Serve / My Progress for Cadets, plus Instructor tools, classroom mode, pilot mode.
Students are just **"Cadets"** — never "Vanguard Cadets".

## Decisions already made by the owner (don't re-ask)

1. **Fresh history.** Remove every trace of "Cursiv" and "Recruit" (code, docs, UI text, file names, installer,
   data folder `~/.cursiv-recruit`, cookie `recruit_session`, env vars `RECRUIT_*`, the `recruit/` package name,
   `install-recruit.*`, `start-recruit.*`, site, tests). No link between the two products.
2. **Classroom model: instructor laptop server.** The instructor's laptop runs Vanguard on the school network;
   Cadets open it in a browser. No cloud required. (The server already has `--lan` mode that is only allowed when
   every profile has a PIN — build on that.)
3. **Military material is KEPT, not removed.** Pay tables, LES decoder, MOS job explorer, PCS help, letters, family
   profiles move into **Serve → "Explore Military Service"**: opt-in, informational, instructor can switch it off,
   no "join now" or recruiter funnels. Checked answers from data (recruit/facts.py) stay exactly as strict.
4. **AI modes:** Off / Library only (**default**) / Library + AI. The existing "library-only mode" becomes the middle
   setting. AI text never poses as official; facts come from data/cards first (see brain.py + facts.py).
5. **New Ed25519 release key for Vanguard**, stored on GitHub and on the owner's device (the owner creates/stores the
   private key — do NOT generate or commit a private key in the cloud; leave a TODO).
6. **Never claim** official, Army, government or JROTC Command approval/endorsement or partnerships. Use "Designed to
   support JROTC instruction."
7. Crisis/care support (recruit/safety.py, 988 etc.) stays — it matters even more for teenagers.

## Audit facts gathered so far (verified on 2026-10-08)

- All tests pass: `python -m unittest discover -s tests` → 80 tests, 1 skipped (faith library not installed).
- Stack: Python standard-library HTTP server (`recruit/server.py`, ~80 JSON routes under `/api/`), plus the
  `cryptography` package for AES-256-GCM. Front end is plain HTML/JS: `web/index.html` + `web/js/{core,ask,study,log,me,
  intake,voice,faith}.js` (~2,300 lines). No build step, no npm.
- Modules (`recruit/`): server, security (PBKDF2 PINs, sessions, CSRF/DNS-rebinding guards, admin PIN, LAN guard),
  vault (AES-GCM per-profile data key wrapped by PIN and by a recovery code), store (all per-profile files, atomic
  writes, sealed when a key is set), profiles (multi-profile, kind = soldier|family), backup (sealed backups),
  integrity (library tamper check + Ed25519-signed offline updates), knowledge (BM25 library + study cards + checked
  answers + number/citation checks), brain (chat pipeline: facts → checked answer → AI "coach" sentences through
  SentenceGate), facts (pay/BAS/AFT/LES/jobs straight from data), engine (Ollama first; Groq/Gemini optional),
  safety, study/quiz/exam/board, daily (Daily 10, check-ins, budget, leave, PCS, faith plans), fitness (AFT tables),
  pay, careers, letters, books (public-domain reader incl. American Military History I/II), faith, voice (Vosk),
  addons (installs Ollama/voice from the app).
- **Missing for Vanguard (biggest gaps):** no instructor/cadet roles, no classes/platoons/squads, no assignments, no
  lessons authored by instructors, no leadership scenario engine, no service-hours log, no portfolio/report export,
  no cross-profile instructor view. Section 47 permission rules (Cadet can never see other Cadets' data, instructor
  notes, admin config, secrets) must be enforced in the server and **tested explicitly**.
- Data folder: `store.DATA = $RECRUIT_DATA or ~/.cursiv-recruit`.
- `library/` and `books/` are gitignored (official manuals and books are fetched by `tools/fetch_library.py` and
  `tools/fetch_books.py`). In the cloud they will be empty; tests that need them may skip or fail — note which.
- Site: `site/build.py` (zip + Inno Setup installer + Cloudflare deploy + GitHub release + signing via
  `tools/sign.py`), `site/worker.js`, `site/wrangler.toml`. **Do not run `--release` or `--deploy` in the cloud.**
- ~65 files / ~570 occurrences of "cursiv"/"recruit" (case-insensitive, excluding library/ and books/).

## PROGRESS LOG (update this as you go)

- 2026-10-08 desktop: Phase 0 docs done. Phase 1 steps done:
  1. Rename: package `vanguard/`, `~/.vanguard`, `VANGUARD_*`, `vanguard_session`, `install/start-vanguard.*`;
     `tests/test_brand.py` blocks the old name (planning docs temporarily allow-listed).
  2. AI modes: `store.ai_mode()` off / library (default) / ai; `/api/admin/ai-mode` (Instructor PIN); Me tab radio
     buttons; "device admin PIN" is "Instructor PIN" everywhere on screen. Version 0.1.0.
  3. Navigation: Learn (study) / Lead / Train (logbook → fitness) / Serve / Progress tabs; Ask, Me, Instructor in the
     header; `web/js/shell.js` holds Lead/Serve/Progress/Instructor pages; Serve → Explore Military Service works.
     NOTE: the page CSP blocks inline `onclick` — always attach listeners in JS.
  4. Cadet wording: AI persona (high-school Cadets, instructor is the authority, nurse/counselor/trusted adult),
     APP_HELP, guardian note, welcome text and suggested questions; crisis banners use 988 call/text, Crisis Text
     Line, RAINN, Childhelp, "tell a trusted adult" (no military lines, never promise secrecy).
- 2026-10-08 desktop (later): owner chose **class records only** for instructor visibility and **roles + instructor
  first**. Done: Phase 2 roles (cadet/guardian/instructor, `profiles.role_of`); Phase 3 security core (per-Cadet
  class key for `store.CLASS_FILES`, X25519 program key locked by the Instructor PIN, `security.unlock_program`);
  `vanguard/instructor.py` roster (classes/platoons/squads, unit + LET level, sealed) and `/api/instructor/*` routes;
  tests in `tests/test_classroom.py` and `test_security.py`. Installable app: `web/manifest.webmanifest` + icons.
- **Owner requirement (2026-10-08): phone-first AND desktop.** Every new screen must work at 375 px wide with large
  touch targets, and on a laptop/projector. Installable via "Add to Home Screen"/"Install app".
  Known limit: full offline PWA (service worker) needs HTTPS, which a LAN laptop server doesn't have — phones use
  the installed shortcut while on the classroom network; that's fine because the data lives on the laptop.
- **Phase 3 DONE (2026-10-08):** Instructor screen (Instructor PIN unlock, units, unit + LET per Cadet, record
  status), instructor option on the new-profile screen, instructors skip the Cadet interview/tour, phone header fits
  375 px, SECURITY.md section "Instructors and class records". Checked in the browser at phone width.
- **Phase 4 DONE (2026-10-08):** `vanguard/lessons.py` + routes (`/api/instructor/lesson|lessons|assign-lesson|
  assignment`, Cadet `/api/lessons`, `/api/lesson`, `/api/lesson/submit`), `web/js/lessons.js` (Cadet "My
  assignments" in Learn + lesson page; instructor lesson editor, assign form, progress + details), tests in
  `tests/test_lessons.py`. Verified in the browser at 375 px: write → assign to platoon → Cadet completes → instructor
  sees score and reflection. Late joiners: `lessons.sync_cadet` gives a Cadet who joins a unit its assignments (only them; no duplicates).
- **Phase 5 DONE (2026-10-08):** `vanguard/scenarios.py` (+ 8 practice scenarios in `vanguard/scenarios/`, not
  combat, no verdicts), leadership log (`scenarios.jsonl`, class record), instructor scenarios (editing a practice one
  saves a copy), classroom mode (one live anonymous vote, counts only, reveal guidance), `web/js/scenarios.js` (Lead
  tab, log, instructor section, projector view), `tests/test_scenarios.py`. Verified in the browser: phone (Cadet
  scenario + log) and desktop (classroom mode). README/SECURITY rewritten for JROTC (Phase 1 item c, mostly done).
- **Phase 6 DONE (2026-10-08):** `vanguard/train.py` (instructor-chosen events, suggested set until then, no
  built-in standard; results + goals are class records; stats first/previous/latest/best/improvement/%), Train tab
  (`web/js/train.js`: cards, trend line, goal, log a result, history; private logbook link), instructor events +
  test-day recording; AFT scorer moved to Serve → Explore Military Service; `tests/test_train.py`. Fixed: the date
  box used UTC (tomorrow on US evenings). Verified in the browser at 375 px.
- **JROTC audit (2026-10-08, owner: "still feels like a Soldier app"):** Cadet interview/profile = name, grade,
  interests, goals only (no rank/MOS/stage/station/height/weight/sex); every card has a `category:`; Learn shows
  Leadership / Citizenship / Military Knowledge / Health & Fitness / Careers / Explore Military Service, and
  **Basic Training & Beyond only when the Cadet opts in** ("I plan to join the military", Serve) and the instructor
  allows it — enforced server-side via `knowledge.use_categories`; instructor switches per category; 7 new cards from
  USA.gov, National Archives, CDC, BLS (FAFSA flagged unverified). Rule for new content: U.S. government sources,
  fetched and cited; anything unverified gets `verified: no`.
- **Phase 7 DONE (2026-10-08):** `vanguard/service.py` (service log in class records, instructor projects, verify /
  return-with-note / un-verify, verified entries locked, totals), `web/js/service.js` (Serve: hours, log form, status;
  Instructor: review queue, hours by Cadet, projects), `tests/test_service.py`. Verified in the browser end to end.
- **Branches: Army JROTC only** (owner, 2026-10-08) until another branch approaches for a pilot.
- **Quizzes (owner's rules, 2026-10-08):** every quiz is a chat feed graded on the device -- never self-reported, and
  the answer isn't sent to the screen before answering. Two ways in: 📝 Practice (multiple choice) and 🎯 Challenge
  (type the answer; key words + offline AI for meaning; yes/no handled). Daily 10's set is fixed for the day and its
  score is counted from graded answers. Mock board grades by question id (no "count it right"). The note on every
  quiz: missing one means nothing bad; the more you miss now, the more you have to look forward to.
- **Planned additions (owner):**
  - Phase 9 or 11: the instructor can **view and edit the quiz questions** of the built-in cards for their program, and
    give a **pop quiz** (their own questions; live in class like the scenario vote, or assigned). Today a lesson with
    only questions already works as an assigned pop quiz.
  - **Phase 11: much more content** -- same rule: U.S. government sources, fetched and cited, `verified: no` when not
    checked; Army JROTC only.
- **Next:** owner testing (run from C:\Code\Vanguard with `python run.py`), then Phase 7 Serve (service log +
  instructor verification), 8 Progress, 9 Instructor analytics, 10 Pilot. Phase 1 loose ends below.
- **Phase 1 still to do:** (a) module on/off flags in config (explore_military, faith, letters, voice) with
  Instructor PIN, hiding the matching UI; (b) remaining "Soldier" wording outside Explore Military Service:
  intake questions (`web/js/intake.js`), study/log/me screens, study cards that address "you" as a Soldier;
  (c) rewrite README, SECURITY, LIBRARY,
  CLAUDE.md for Vanguard, then remove the planning docs from the brand-test allow-list (reword them);
  (d) site: new landing page, /pilot, /security (`site/build.py`, `site/worker.js`, wrangler name `vanguard`);
  (e) REPORT.md.

## PHASE 0 — DONE (2026-10-08, desktop session): ARCHITECTURE.md, REUSE_PLAN.md, MIGRATION_PLAN.md are committed. Skip to Phase 1.

## (Phase 0 original instructions, for reference)

Write three files at the repo root:
1. **ARCHITECTURE.md** — how it fits together: server + security + vault/store + profiles, library/knowledge/brain/
   facts/engine pipeline, study engines, fitness, books, integrity/updates, build/release, tests. Include the request
   lifecycle and where per-profile encryption keys live.
2. **REUSE_PLAN.md** — a table for every module and every web/js file: Keep as-is / Adapt / Move to Serve→Explore
   Military Service / Retire, with the reason. Map to the spec's areas (Learn, Lead, Train, Serve, Progress,
   Instructor). Fitness: AFT scorer becomes configurable personal-best tracking (no hard-coded pass/fail).
3. **MIGRATION_PLAN.md** — target layout (spec section 30: core / curriculum / instructor / ai / cadet / security /
   reports, as Python sub-packages), the rename plan (package `recruit` → `vanguard`), data-model additions
   (role, program, class/platoon/squad, LET level, assignments, lessons, scenarios, service log), the permission
   model for LAN classroom use, and the phases 1–10 from the spec with deliverables and tests for each.

Commit: "Phase 0: architecture, reuse and migration plans".

## PHASE 1 — product shell (only after Phase 0 is committed)

1. **Rebrand everything** to Vanguard: package `recruit/` → `vanguard/` (update all imports, tests, tools, site),
   data folder `~/.vanguard`, env vars `VANGUARD_*`, cookie `vanguard_session`, launch scripts `install-vanguard.*`
   / `start-vanguard.*`, installer names, README/SECURITY/LIBRARY/CLAUDE.md, UI text ("Soldier" → "Cadet" in
   generic UI; keep "Soldier" only inside Explore Military Service content where it's factually about Soldiers).
2. Add a test that fails if "cursiv" or "recruit" (case-insensitive) appears anywhere in tracked files except
   where the word is genuinely about military recruiting inside Explore Military Service content (keep an explicit
   allow-list, and keep it tiny).
3. Navigation: Learn / Lead / Train / Serve / My Progress for Cadets; a separate Instructor area (placeholder pages
   are fine in Phase 1). Serve contains "Explore Military Service" (pay, LES, jobs, PCS, letters).
4. Product config + feature flags (enabled modules, AI mode Off / Library only / Library + AI, default Library only),
   locked behind the existing device admin PIN (rename it "Instructor PIN" in the UI).
5. Version starts at **0.1.0** (owner convention for updates later: keep the major fixed, use a U-suffix for routine
   updates, e.g. 0.1.0-U01).
6. Run all tests; everything must pass. Commit: "Phase 1: Vanguard product shell".

Then **stop and write a short report** in REPORT.md (what you found, changed, why, what's preserved, files touched,
how tested, what's left) and push.

## Rules

- Don't delete working functionality without documenting why. Isolate, don't casually delete.
- No new dependencies unless unavoidable. No cloud requirements. Don't weaken security.
- Don't fabricate JROTC curriculum, sources, partnerships or approvals. Flag uncertain curriculum.
- Commit messages end with: `Co-Authored-By: Claude <noreply@anthropic.com>`
- Run the full test suite before every commit; never commit with failing tests.
