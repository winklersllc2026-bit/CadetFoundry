# Vanguard — Architecture (as inherited, Phase 0 audit, 2026-10-08)

This describes the code as it exists **before** the Vanguard rebrand. Package and file names still use the
inherited names (`recruit/`, `RECRUIT_DATA`, …); Phase 1 renames them. Verified state: 80 tests, all passing
(1 skipped when the optional faith library isn't installed).

## 1. Shape of the system

```
browser (web/index.html + web/js/*.js, no build step)
   │  JSON over HTTP, session cookie (HttpOnly, SameSite=Strict)
   ▼
run.py ──► recruit/server.py  (Python standard-library ThreadingHTTPServer, ~80 routes under /api/)
              │  every request: security checks → profile + key context → handler
              ├─ security.py   PINs, sessions, lockouts, admin PIN, CSRF / DNS-rebinding / LAN guards
              ├─ store.py      all per-profile data (JSON / JSONL files), sealed with the profile key
              ├─ vault.py      AES-256-GCM, scrypt key wrapping, sealed backups
              ├─ profiles.py   several people on one device, one folder each
              ├─ knowledge.py  library + study cards + search + checked answers + citation/number checks
              ├─ brain.py      one chat turn (facts → checked answer → AI help through SentenceGate)
              ├─ facts.py      answers straight from data tables (pay, BAS, AFT, LES, jobs)
              ├─ engine.py     AI backends: Ollama (local, first) → optional Groq / Gemini keys
              └─ feature modules: study (quiz/exam/board), daily, fitness, pay, careers, letters,
                 books, faith, voice, backup, integrity, addons
```

The only third-party Python package is `cryptography`. Everything else is the standard library. The AI is optional:
with no model installed, every feature except free-text AI explanation still works (Ask falls back to quoting the
library).

## 2. Request lifecycle (recruit/server.py → Handler)

1. **Host check** — the Host header must be the app's own address (`127.0.0.1/localhost/[::1]:port`), or any
   address in LAN mode. Blocks DNS rebinding.
2. **Origin check / CSRF** — commands must be JSON POSTs (forces a CORS preflight, which is never answered) and any
   Origin header must match the host.
3. **Session** — the cookie token maps to `[profile id, last activity, data key]` in memory
   (`security._sessions`). Sessions expire after the profile's idle timeout. With a PIN set, everything except the
   lock screen and a short allow-list (`/api/unlock`, `/api/recover`, status) answers 401 without a session.
4. **Context** — the handler sets the active profile folder (`store.use_profile`) and the profile's data key
   (`store.use_key`) as context variables for this request only, so one request can never read another
   profile's files.
5. **Route** — the handler for the path runs and returns JSON (or a stream of JSON lines for `/api/chat`).

LAN mode (`run.py --lan`, binds 0.0.0.0) is refused unless **every** profile has a PIN.

## 3. Data and encryption

- Data folder: `$RECRUIT_DATA` or `~/.cursiv-recruit` (renamed in Phase 1). Layout:
  `profiles/index.json`, `profiles/<id>/…` (profile.json, log.jsonl, study.json, chats, letters, books.json, …),
  `security.json` per profile (PIN hash, wrapped keys — never sealed), device `config.json`, admin PIN file.
- **PIN:** PBKDF2-SHA256, 400,000 iterations, per-profile salt; wrong guesses throttled with growing lockouts that
  survive restarts.
- **Encryption at rest:** a profile with a PIN gets a random 256-bit data key. The key is wrapped (scrypt
  n=2^15, r=8, p=1 + AES-GCM) twice: by the PIN and by a one-time **recovery code**. Files are sealed as
  `RCV1 | 12-byte nonce | AES-256-GCM ciphertext` with the file name as associated data (a sealed file can't be
  swapped for another). The data key exists in memory only while the profile is unlocked.
- **Writes are atomic** (temp file + fsync + rename). JSONL readers skip a damaged line instead of failing.
- **Backups:** one file per profile, sealed with a password of at least 10 characters (`vault.seal_backup`).
  Device config is never exported or restored.
- **Admin PIN** (device-wide): guards device settings such as library-only mode. This becomes the
  **Instructor PIN** foundation.

## 4. Knowledge, answers and AI

- `knowledge.Library` loads **study cards** (`recruit/cards/*.md`: front matter with title/topic/source/verified,
  a body, and `## Quiz` lines `Q: … | A: … | ALSO: other phrasings`) and **library documents**
  (`library/*.md|txt`, the official manuals, fetched by tools). Search is BM25 over an inverted index; cards get a
  1.3× boost. `edition()` reads each document's publication date.
- **Checked answers:** a question that matches a verified card's quiz question (or an ALSO phrasing) gets that
  answer word for word. One-word questions need an exact phrasing.
- **facts.py:** pay, BAS, non-existent grades, AFT score-table lookups, LES blocks, Army jobs — answered from data
  files, never by the AI. `final` answers skip the AI entirely.
- **brain.Brain.chat** order: safety check → app-help → facts/checked answer → unknown-publication refusal
  ("I won't guess") → library context → AI. When a checked answer exists, the AI only gets "coach" rules (≤3
  plain sentences, no numbers/lists/repeats). Every AI sentence passes `SentenceGate`: sentences with numbers the
  sources don't contain, or manuals the library doesn't have, are dropped. `MarkerFilter` strips any attempt by
  the AI to write the ✅ badge, ⚠️ notices or links.
- **Library-only mode** (admin setting): no AI writing at all — checked answers and quoted library text only.
- `engine.py`: Ollama first (qwen2.5:3b, warm-up, num_ctx 8192, temperature 0.3); optional Groq/Gemini keys are
  upgrades, never requirements.
- `safety.py`: every message is checked first. Crisis language gets a care response (988 etc.) and the AI is
  never allowed to answer it with library search results. OPSEC-sensitive messages get a note.

## 5. Feature modules (inherited)

| Module | What it does |
|---|---|
| study (in brain/knowledge) | flashcards weighted to missed/unseen questions, progress per topic |
| exam.py | timed multiple-choice tests from cards, graded on device, history |
| board.py | mock promotion board, answer grading by keywords, Creed recitation |
| daily.py | Daily 10 + streak, private check-ins, sleep summary, support contacts, budget, leave, PCS, faith plans |
| fitness.py | AFT scoring from official tables (`data/aft_tables.json`), history, improvement plan |
| pay.py / facts.py | 2026 DFAS pay + BAS, LES block meanings (`data/pay_tables.json`, `data/les_fields.json`) |
| careers.py | 263 Army job summaries (library/_jobs.json) |
| letters.py | address book, AI drafts from notes, OPSEC check |
| books.py | public-domain reader: chapters, place saving, search, read-aloud |
| faith.py | optional scripture library (several traditions), reading plans |
| voice.py | optional offline speech-to-text (Vosk), 9-line radio parsing |
| addons.py | installs Ollama / voice model from inside the app, with signature checks |
| integrity.py | library tamper check (fingerprints) and Ed25519-signed offline updates |
| backup.py | sealed export / restore |

## 6. Front end

`web/index.html` (layout + CSS tokens) and plain ES modules: `core.js` (fetch wrapper, lock screen, PIN recovery,
backup UI, tabs), `ask.js` (chat stream, citations, read-aloud), `study.js` (cards, quiz, exam, board, books,
jobs), `log.js` (logbook, AFT, check-ins, pay, leave, budget, PCS, letters), `me.js` (profile, PIN, recovery code,
admin PIN, library-only, add-ons, updates), `intake.js` (first-run questions), `voice.js` (speech in/out),
`faith.js`. No framework, no bundler; works offline.

## 7. Build, release, update

- `site/build.py` builds the update zip, the Windows installer (Inno Setup, `site/installer.iss`), the landing page,
  signs the zip with `tools/sign.py` (Ed25519 private key kept off the repo), publishes a GitHub release
  (`--release`) and deploys the site to Cloudflare Workers (`--deploy`, `site/worker.js`, `wrangler.toml`).
- Devices install updates offline from a USB stick: `integrity.inspect_update` verifies the signature against
  `data/release_key.pub` before anything is replaced; user data is never touched.
- Vanguard needs its **own** key pair (owner generates it locally; never committed).

## 8. Tests

`tests/test_basics.py` (library, answers, safety, faith, voice text, store, fitness, radio, board, pay, letters/jobs,
books) and `tests/test_security.py` (PINs, sessions, lockouts, encryption, recovery codes, backups, host/origin
guards, LAN guard, signed updates). AI calls are mocked in tests. Tests that need `library/` or `books/` content
skip or use small fixtures when it's missing.

## 9. What does not exist yet (needed for Vanguard)

- Roles: instructor vs Cadet (today every profile is equal; `kind` is soldier|family).
- Program / class / platoon / squad membership, LET level.
- Instructor-authored lessons, assignments, due dates, completion tracking.
- Leadership scenario engine and decision log.
- Service-learning log with instructor verification.
- Portfolio and reports (printable/PDF), pilot configuration and pilot report.
- An instructor view across Cadets' data — which must not weaken per-profile encryption (see MIGRATION_PLAN.md §4).
