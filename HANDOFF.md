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
