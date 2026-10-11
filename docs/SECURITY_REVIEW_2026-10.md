# Security review, October 2026: final report

Scope: the hardening spec, Phases 2–12, carried out 2026-10-10 to 2026-10-11 on the private `Vanguard` repository.
Review range: `cb8a4c3..72ee8de` (12 commits, 46 files, +2,311 / −218 lines). Version in the repo: **0.2.3 (not yet
released)**. The published 0.2.2 contains **none** of these fixes.

Order of work: authorization came first, as the spec asked. Signing (Phase 4) was done before outbound AI
(Phase 7), and dependencies (Phase 6) after Phase 7. Signing came early because its new end-to-end test showed the
updater refused every real release, which blocks shipping any fix at all.

---

## A. Changes made

**Code**

| File | Purpose |
|---|---|
| `vanguard/server.py` | One gate for device-wide changes (`_device_admin`): only an instructor profile may try the Class PIN, and the first Class PIN can only be set on this computer. Exact-address Host check. Instructor-only classroom switch kept local. PIN-less profiles can't be opened from other devices. Pending restores and updates are finished at start |
| `vanguard/security.py` | `host_ok` accepts loopback, or in classroom mode only the socket's own local address and port (blocks DNS rebinding) |
| `vanguard/instructor.py` | Join requests sealed to the program public key. Class overview survives one Cadet's damaged records |
| `vanguard/pilot.py` | Pilot setup, snapshots and feedback sealed with the program data key. Survey answers sealed per answer, stored in random order. Old plain files migrate in place |
| `vanguard/live_quiz.py`, `vanguard/scenarios.py` | Live answers (tied to profile ids) are kept in memory only. Older on-disk files are taken over, then deleted |
| `vanguard/program_backup.py` | Restore validates everything first, stages it, keeps a safety copy and replaces completely. Interrupted restores are finished or undone at start. Join codes, titles and joins are now backed up |
| `vanguard/integrity.py` | Updater file lists match the real release (it refused every release before). Signatures are checked strictly. Unsafe names are refused. Replaced files are backed up, with rollback on failure or interruption |
| `vanguard/engine.py`, `vanguard/brain.py` | Online AI only for ordinary Ask questions, without personal context. Crisis messages, grading, quick calls and letters stay local |
| `vanguard/safety.py` | More first-person disclosures caught (slang, misspellings, "not safe at home"). Topic-only mentions get a neutral help line |
| `vanguard/backup.py` | Personal restore skips files of the wrong shape |
| `vanguard/reports.py` | Class report survives one Cadet's damaged records |
| `vanguard/addons.py`, `tools/install_voice.py` | Voice add-on downloads fixed by URL and SHA-256; `vosk` pinned |
| `site/build.py`, `site/bundle-requirements.txt` | Installer Python 3.14.8 (hash-pinned), with packages bundled through `pip --require-hashes`. `wrangler` pinned. Public security page corrected. 0.2.3 roadmap |
| `tools/setup.py`, `tools/make_usb.py` | Source installs require `cryptography>=50.0.0`. The USB Mac/Linux starter refuses older versions |
| `tools/check_deps.py` (new) | Checks every pinned package against OSV |
| `tools/remove_profile.py` (new) | Device owner removes a profile whose owner can't sign in |
| `web/index.html`, `web/js/core.js`, `web/js/me.js`, `web/js/shell.js` | Ask says chats are private and unmonitored, and says so when online AI is on. "Everything stays on this device" claims are made accurate. "Damaged records" line on the class card |
| `vanguard/__init__.py` | Version 0.2.3 |
| `.gitignore` | Keys, certificates, `.env`, wrangler `.dev.vars` |

**Tests (new or extended):** `test_authz`, `test_sessions`, `test_network`, `test_program_data`, `test_program_restore`,
`test_security`, `test_outbound_ai`, `test_safety`, `test_dependencies`, `test_pilot`, `test_demo_box`.

**Docs:**
- `SECURITY.md`: network, signing, online AI, safety check, backups, dependencies, device-change rule.
- `docs/DATA_INVENTORY.md` (new).
- `docs/PILOT_DATA_HANDLING.md` (new).
- `docs/PILOT_CHECKLIST.md` (new).
- `README.md`, `ARCHITECTURE.md`, `ROADMAP.md` and `CONTENT_REFRESH.md`.

## B. Security findings

"Confirmed" means a test reproduced the problem. "Inspection" means it was found by reading the code; in both cases
the fix is covered by a test that now passes.

| # | What was wrong | How found | What changed | Evidence |
|---|---|---|---|---|
| 1 | Any signed-in Cadet could send 5 wrong Class PINs to a device-wide route and lock the instructor out for up to an hour. The first Class PIN could be set from any device | Inspection | One `_device_admin` gate: Cadets are refused before the PIN is checked; first PIN only on this computer | `test_authz.test_a_cadet_cannot_change_the_device_or_lock_the_instructor_out`, `test_the_first_class_pin_is_only_set_on_this_computer` |
| 2 | Classroom mode accepted any Host header, so a website a Cadet opened could reach the instructor's computer by DNS rebinding | Inspection | Host must be loopback or the socket's own address and port | `test_network` (rebinding → 421). Manually on this PC's Wi-Fi address; a fresh-copy launch returned 421 for a foreign Host |
| 3 | Live votes and live-quiz answers were written to disk in plain text with profile ids | Inspection | In memory only; old files taken over and deleted | `test_program_data` |
| 4 | Pilot setup, notes, snapshots, survey answers and join requests were plain files | Inspection | Sealed (program data key / program public key); survey answers in random order | `test_program_data`, `test_pilot` (nothing readable on disk) |
| 5 | Program restore wrote into the live folder file by file and left stale files behind; an interruption left a mix | Inspection | Validate → stage → safety copy → swap; finished or undone at start | `test_program_restore` (stale files, bad password, malformed, path traversal, both interruptions) |
| 6 | **The updater refused every real release** (`books/` and `start-classroom.*` were missing from its lists) | **Confirmed** (new end-to-end test with a real release zip) | Lists fixed, and a test keeps them in step with `site/build.py` | `test_security` real-release-chain test |
| 7 | Signature parsing ignored junk after the base64 padding; `:` and control characters were allowed in update file names | Inspection | Strict base64, exactly 64 bytes; names refused | `test_security` |
| 8 | A failed or interrupted update could leave a half-installed app | Inspection | Backup of replaced files, rollback, `finish_pending_update` at start | `test_security` failed/interrupted install tests |
| 9 | With online AI on, ordinary Ask questions sent the Cadet's profile, memories and history; crisis messages, grading and letters could also go online. SECURITY.md said grading never did | Inspection | Online only for ordinary Ask questions, without personal context; everything else stays local; docs corrected | `test_outbound_ai` (4 tests) |
| 10 | The safety check missed common first-person phrasings (kms, unalive, misspellings, "not safe at home", "my dad hits me") | Confirmed by testing phrase lists | Patterns widened; topic-only line added; known misses listed in the test | `test_safety` (5 tests, including `KNOWN_MISSES`) |
| 11 | **One Cadet's malformed `study.json` (e.g. from a hand-made personal backup) crashed the instructor's class overview and class report for the whole class** | **Confirmed** (new test errored on the old code) | Restore skips wrong-shape files; overview and report skip one Cadet's damaged records and show a note | `test_sessions.test_one_cadets_damaged_records_dont_break_the_class_views` fails on the old code and passes now |
| 12 | Installer bundled Python 3.12.10, the last 3.12 with Windows builds (later security fixes never reach it); `cryptography` unpinned; add-on downloads unverified; deploy tool unpinned | Inspection | Python 3.14.8 (hash matches python.org), hash-pinned packages, hashed add-on downloads, pinned `vosk`/`wrangler` | `test_dependencies`; full suite run **on the bundled interpreter** |
| 13 | Docs and the public page overstated privacy ("everything stays on this device", "quizzes can't be faked", "a name and a PIN") and named an old version (README 0.1.4) | Inspection | Reworded to what the code does | Section C, doc review |

Checked and found sound: every `/api/instructor/*` route refuses no session, a Cadet, and an instructor without the
Class PIN. A Cadet never sees another Cadet's lessons or an answer key. Live results are counts only. Signing out,
idle expiry and a PIN change end sessions. Forged cookies open nothing. A deleted profile's session stops. Knowing
the Class PIN doesn't make a Cadet an instructor. Eight simultaneous submissions count once. The class report CSV is
instructor-only. A crafted personal backup can't write grades, settings or roles. No secrets were found in git
history (searched for private keys, cloud and GitHub tokens, the DVIDS key and the old site password; the only
match was a code template and a public key).

## C. Test results

All commands were actually run on Windows 11, 2026-10-11.

| Command | Result |
|---|---|
| `python -X utf8 -m unittest discover -s tests` (system Python 3.14.3, cryptography 48.0.0, at `72ee8de`) | **208 tests, OK, 0 skipped** (about 290 s) |
| The same suite on the **bundled Python 3.14.8 + cryptography 50.0.2**, from a fresh `git archive` of HEAD plus the downloaded library | **208 tests, OK, 1 skipped** (brand check: needs a git checkout; it passes in the repo run above) |
| `node --check` on all 22 `web/js/*.js` files and `site/worker.js` | 23 files OK |
| `python -m pyflakes vanguard tools run.py site/build.py tests` | No undefined names or errors. 15 unused imports / variables (two are deliberate "is vosk installed" checks) |
| `python tools/check_deps.py` | cryptography 50.0.2, cffi 2.1.1, pycparser 3.0, vosk 0.3.45: no known vulnerabilities |
| First launch: `python\python.exe run.py` from the fresh copy, empty data folder | `GET /` 200; first-run state (no profiles, no Class PIN); foreign Host → 421 |
| Review diff check (`cb8a4c3..HEAD`) | Same 143 API routes; no files deleted; no tests removed (152 → 208 test functions). The device-admin assertions removed in `6c6733d` are all present again under an instructor profile, plus new refusals. New skips are only "cryptography not installed". No secret patterns in added lines |

**Not run, and why:**
- **Full installer build** (`site/build.py`, Inno Setup). It rebuilds `site/dist`, which holds the 0.2.2 files the USB
  tool uses. The bundling step it runs (`bundle_python`) was run on its own and tested above.
- **Install on a clean Windows machine**, and the **signed update chain end to end on a clean device**. These need a
  separate machine or VM and a published release.
- **Real phones on a classroom network** during this review. The Host rule was checked against this PC's real Wi-Fi
  address.
- **The online-AI notice in a live browser.** No online provider is configured; the server side is covered by
  `test_outbound_ai`.
- **Flaky test, not seen this time.** `test_quiz_answers_are_typed_and_graded_never_self_reported` timed out once
  earlier in the review (it may reach a local Ollama). It passed in every run above.

## D. Migration and compatibility

- **0.2.2 → 0.2.3: reinstall; don't update.** 0.2.2's updater refuses every real release (finding 6), so 0.2.2
  copies must run the 0.2.3 installer. The data folder (`~/.vanguard`, or `VanguardData` on a USB) is kept.
- **Program data:**
  - Plain pilot files and join requests are sealed the first time an instructor opens class records on 0.2.3.
  - `live.json` and `live_quiz.json` are taken over and deleted.
  - The migration is idempotent and atomic, and leaves no plain copy behind.
- **Rollback:** take a **program backup before upgrading**. A rolled-back 0.2.2 can't read sealed pilot files (they
  aren't lost; 0.2.3 reads them again). To roll back, reinstall 0.2.2 from the releases page and restore that backup.
- **Program restore:**
  - It now leaves `program.before-restore-<date>` safety copies (newest 3 kept) next to the program folder.
  - A restore interrupted mid-way is finished or undone at the next start.
  - Older program backups still restore.
- **Updates:** replaced files are kept in `.update-previous` until the install finishes. An interrupted install is
  rolled back at the next start.
- **Bundled Python moves 3.12 → 3.14.** Add-ons installed into the old Python (voice) may need installing again from
  Settings, because compiled packages are version-specific. Ollama isn't affected.
- **Source installs** (Linux, Pi, Mac): setup upgrades `cryptography` to 50 or newer. The USB's Mac/Linux starter
  asks for the upgrade if an older version is present.
- **Formats:** personal backups are unchanged; files of the wrong shape are skipped on restore. Config is unchanged.
  Sessions are in memory, so everyone signs in again after the upgrade.

## E. Remaining risks

No Critical issues are known. The ranking assumes the safeguards in section F.

| Rank | Risk | Why it matters | What resolves it |
|---|---|---|---|
| **High** | Classroom network is plain HTTP | PINs, session cookies and pages (including a Cadet's private chats) cross the Wi-Fi unencrypted. On a WPA2-Personal network anyone with the password can, with tools, decrypt others' traffic | HTTPS needs a certificate the Cadets' devices trust (publisher infrastructure; SECURITY.md explains why there's no toggle). Until then: a dedicated hotspot only the class joins, **WPA3-Personal where devices support it** (it stops one client decrypting another's traffic), unique PINs |
| **High** | 0.2.3 isn't released, and the release/install chain hasn't been verified on a clean device | Every fix here is only in the repo; 0.2.2 can't update itself | Owner releases 0.2.3, installs it on a clean machine, then publishes a 0.2.4 test update to check the signed update path end to end |
| **Medium** | Installer isn't code-signed | Windows shows "Windows protected your PC". Trust for the first install rests on GitHub's HTTPS download | Code-signing certificate in the company's name |
| **Medium** | The safety check is pattern matching and notifies no one | Indirect wording is missed (listed in `test_safety`). Nobody is alerted to a Cadet in danger | By design, not hidden: say it to Cadets and parents (pilot checklist). Any notification feature would need a school policy decision first |
| **Medium** | Laptop-level protection depends on the owner | Without BitLocker, deleted data is recoverable. Names in the profile list, lesson text and answer keys are plain on disk | BitLocker, standard account, screen lock (checklist) |
| **Medium** | Online AI provider terms not reviewed | If turned on, ordinary questions go to a third party | Keep it off for the pilot, or review the provider's terms for minors' data |
| **Medium** | No security contact published | Schools and parents have no private reporting route | Owner publishes one |
| **Low** | Practice history restored from a personal backup is self-reported | A Cadet could inflate practice counts and practice-exam scores, though not assigned-lesson grades | Documented. Could be signed per device later |
| **Low** | No in-app way to remove a Cadet who left | `tools/remove_profile.py` needs the device owner | An instructor "remove Cadet" action (future) |
| **Low** | `vosk` (optional voice) last released 2022 | Unmaintained dependency, though OSV lists no vulnerabilities | Watch it with `check_deps.py`; replace if it becomes a problem |
| **Low** | 150 of 202 cards lack a per-card "checked" date | Harder to see how fresh each fact is (a full check was done 2026-10-09) | Add dates at the next refresh (CONTENT_REFRESH.md) |
| **Low** | No license file; `docs/history/` and git history contain the old product names | Reuse terms unclear. The brand rule applies to anything published | Owner chooses a license. The repo is private and the release zip carries neither, so leave as is unless the repo is made public (history rewrite only with your approval) |

## F. Pilot recommendation

**Suitable for a restricted pilot under explicit safeguards, once 0.2.3 is released and installed. Until then, not
ready for student data:** the published 0.2.2 has findings 1–11.

Evidence for the restricted pilot:
- Every instructor route and device-wide change is tested against no session, Cadets, and instructors without the
  Class PIN.
- Private files are encrypted per Cadet, and the instructor can't open them (tested).
- Program data, pilot data, survey answers and joins are sealed at rest.
- Restores and updates are validated, staged and recoverable.
- Online AI is off by default, and limited when on.
- 208 tests pass on both the development Python and the exact Python the installer ships.

Why not broader: the classroom network is still plain HTTP; the release chain hasn't been verified on a clean device;
and the safety check can't detect everything or alert anyone.

Safeguards for the pilot:
- A dedicated WPA3 (or WPA2) hotspot only the class joins.
- Online AI off.
- BitLocker on the laptop.
- A dry run with fictional profiles.
- Retention and parent notice decided first.
- Cadets told plainly that Ask isn't monitored.
- All of these are in `docs/PILOT_CHECKLIST.md`.

## G. Owner-controlled actions

1. **Release 0.2.3:** `python site/build.py --release` (check that it prints "Signed:"), then
   `python site/build.py --deploy` and `python tools/make_usb.py <drive> --with-ai`. Reinstall every 0.2.2 copy.
   Take a program backup before upgrading any installation that already has real data.
2. **Verify on a clean machine:** install 0.2.3, run the dry run in the checklist, then publish a small 0.2.4 and
   confirm the in-app update installs it. Only after that can the release chain be called verified end to end.
3. **Keep the release key safe:** `~/.vanguard-release/release_key.pem` backed up offline, never on a school device or
   in git.
4. **Code-signing certificate** for the Windows installer (company name).
5. **HTTPS decision** for the classroom network (needs certificate infrastructure). Until then, the hotspot
   safeguards above.
6. **Online AI:** keep it off, or review a provider's terms for minors' data before turning it on.
7. **Data retention, device owner and parent notice:** approve them with the school (`docs/PILOT_DATA_HANDLING.md`).
8. **Publish a security contact address.**
9. **License, and repository visibility:** both are your decisions. The source repo is private and the releases repo
   is public. Nothing was changed, and no history was rewritten.
10. **Rotate the old website password** if it's used anywhere else (it was typed into a terminal command earlier;
    it isn't in the repository).
