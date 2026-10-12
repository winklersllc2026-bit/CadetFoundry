# Cadet Foundry — architecture (version 0.1.x)

Cadet Foundry is a learning and leadership platform for JROTC instructors and Cadets. One computer (the instructor's
laptop, a USB drive, or a Raspberry Pi demo box) runs everything; Cadets use a web browser on the same network.

## Shape

```
Cadet / instructor browser  ──HTTP (classroom network)──▶  run.py  →  cadetfoundry/server.py   (Python standard library)
                                                                        │
                       web/ (one page: index.html + web/js/*.js) ◀──────┤  static files, strict CSP, no inline scripts
                                                                        │
                       cadetfoundry/*.py — features (below)                 │
                                                                        ▼
                       data folder: ~/.cadetfoundry, or $CADETFOUNDRY_DATA (USB: Cadet Foundry Data\, Pi: /var/lib/cadetfoundry)
                       optional: Ollama on 127.0.0.1:11434 (offline AI), Vosk (offline voice)
```

* **No runtime dependencies beyond Python 3.10+ and `cryptography`.** The Windows installer and USB drive carry
  their own Python (official embeddable build, pinned by SHA-256 in `site/build.py`).
* **Offline.** Nothing leaves the device; there is no online AI (removed 2026-10-12). Study content, quizzes and
  grading never need a network.

## The server (`cadetfoundry/server.py`, `cadetfoundry/security.py`)

* One `ThreadingHTTPServer`, exclusive use of its port (two copies never share an address). Default port 8780;
  `--lan` listens on the network; the Pi demo box uses port 80.
* Every request: Host check (DNS rebinding; any host in `--lan`), Origin check (no cross-site requests), JSON-only
  POSTs, session cookie (HttpOnly, SameSite=Strict) bound to one profile. Public routes: the app shell, `/api/lock`,
  sign-in/profile creation, `/download` and `/downloads/<file>` (installers only).
* `/api/instructor/*` needs an instructor profile session **and** the Class PIN entered in that session.

## Data and encryption (`store.py`, `vault.py`, `profiles.py`, `instructor.py`)

* Each profile: own folder, own PIN, own random data key (AES-256-GCM; key locked by the PIN with scrypt and by a
  one-time recovery code). Private files (check-ins, chats, notes, letters, logbook, profile) use that key only.
* **Class records** (`store.CLASS_FILES`: study, exams, lessons, assignments, scenarios, service, fitness, goals,
  recognition) use a second per-Cadet **class key**, sealed to the program's X25519 public key. The program private
  key is locked by the **Class PIN**. So an instructor reads class records, never private files.
* Device-wide settings: `config.json` (AI mode, Learn categories, optional-tool switches, demo flag, portfolio
  sections). Program data the instructor builds: `DATA/program/` (lessons, scenarios, units, pilot, quiz edits).
* In classroom mode (`--lan`) new profiles must have a PIN, a PIN can't be removed, and a profile without a PIN can't
  be opened from another device. Only this computer's own address is accepted as Host (DNS-rebinding guard).

## Features

| Area | Modules | Screens (`web/js/`) |
|---|---|---|
| Learn: study cards, quizzes typed and graded on the server, exams, Daily 10, library search, books, faith texts | `knowledge.py` (cards in `cadetfoundry/cards/*.md`, each citing its source), `brain.py`, `board.py` (grading), `exam.py`, `daily.py`, `books.py`, `faith.py`, `quiz_edits.py` | `study.js`, `faith.js`, `ask.js` |
| Lessons and assignments, pop quizzes | `lessons.py` | `lessons.js`, `dashboard.js` |
| Lead: leadership scenarios, leadership log, classroom vote (several in a row), live pop quiz | `scenarios.py` (`cadetfoundry/scenarios/*.md`), `live_quiz.py` | `scenarios.js`, `dashboard.js` |
| Train: fitness against yourself | `train.py` | `train.js` |
| Serve: service hours, instructor verification; Explore Military Service (opt-in) | `service.py`, `pay.py`, `facts.py`, `careers.py`, `fitness.py`, `letters.py` | `service.js`, `log.js`, `shell.js` |
| Progress, portfolio, recognition | `progress.py` | `progress.js` |
| Instructor: roster and units, dashboard, CSV report, program backup, pilot tools | `instructor.py`, `reports.py`, `program_backup.py`, `pilot.py` | `shell.js`, `dashboard.js`, `pilot.js` |
| AI (optional): Ollama on this computer only | `engine.py`, `addons.py` | — |
| Safety: crisis lines, OPSEC reminders on every message | `safety.py` | — |

Visibility: Learn categories (`leadership, citizenship, military, health, careers, explore, basic`) are filtered
per request; *Basic Training & Beyond* only for a Cadet who opted in and only if the instructor allows it.

## Distribution

| Form | Built by | Data |
|---|---|---|
| Windows installer | `site/build.py` (Inno Setup, `site/installer.iss`) | `%USERPROFILE%\.cadetfoundry` |
| Zip (Linux, Mac, Pi) | `site/build.py` | `~/.cadetfoundry` |
| USB drive | `tools/make_usb.py` (+ `--with-ai` copies Ollama and a model) | `Cadet Foundry Data\` on the drive |
| Raspberry Pi demo box | `tools/make_demo_kit.py` then `tools/pi_setup.sh` on the Pi | `/var/lib/cadetfoundry` |
| Website | `site/build.py --deploy` (Cloudflare Worker, `site/worker.js`) | — |

Signed offline updates (`integrity.py`) need the publisher's Ed25519 key — not created yet; see ROADMAP.md.
Until it exists, devices refuse every signed update.

## Tests

`python -m unittest discover -s tests` — security (every route, attack cases), classroom records and keys, a full
class day end to end (`test_class_day.py`), live quiz, demo box, USB, grading, content rules.

History (the fork from the earlier product, phase-by-phase handoff notes): `docs/history/`.
