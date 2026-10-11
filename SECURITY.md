# Security

Cadet Foundry is built to run **completely offline** on the instructor's laptop (Cadets connect over the classroom network) or on a single device. No account, no tracking, no GPS, no data sent anywhere.

## What protects the Cadet's data

| Threat | Protection |
|---|---|
| A website open in the same browser tries to send commands to Cadet Foundry (CSRF) | Commands must be JSON (browsers must ask permission first, and Cadet Foundry never grants it); any request from another site's origin is refused; no CORS headers are ever sent. |
| A website tries to read Cadet Foundry's data by pointing its name at this computer (DNS rebinding) | Requests are only accepted for Cadet Foundry's own address (`127.0.0.1` / `localhost`). |
| Another Cadet on a shared device | Each Cadet has their own **profile** (separate folder, own PIN). A session is bound to one profile; every request can only reach that profile's files, and Cadet data can't be read or written at all without an unlocked profile. |
| Someone else on the same network | Cadet Foundry only listens on this device. LAN mode (`--lan`) refuses to start unless every profile has a PIN. |
| One Cadet changing Cadet Foundry for everyone on a shared device | Device-wide changes (AI mode, updates, add-ons, reloading the library, the Class PIN itself) need an **instructor profile** and the separate **Class PIN**, stored as a salted PBKDF2 hash outside every profile, with the same growing lockouts. A Cadet's attempts are refused before the Class PIN is even checked, so they can't lock the instructor out. Before a Class PIN exists, only the computer Cadet Foundry runs on can set one. |
| Someone picks up the device | **PIN lock** (strongly recommended — it also turns on encryption): 6–12 digits, stored only as a salted PBKDF2-SHA256 hash (400,000 rounds). Sessions are random tokens in an HttpOnly, SameSite=Strict cookie and expire after inactivity (5–60 minutes). Five wrong PINs start a lockout that doubles each time (up to 1 hour) and survives restarts. |
| Someone copies the files off the device (stolen tablet, USB, another Windows user) | A profile with a PIN has **its files encrypted** with AES-256-GCM using its own random 256-bit key. That key is stored only locked by the PIN (scrypt, 32 MB, memory-hard) and by the Cadet's recovery code, and is held in memory only while the profile is unlocked. Each file is bound to its name, so changed, damaged, swapped or renamed files are refused, never read. Only `security.json` (PIN hash, locked key) is unencrypted. |
| A crash or power loss while saving | Every file is written to a temporary file, flushed to disk, then renamed into place, so a save is all-or-nothing. |
| Injected scripts (from a document, an answer, a pasted letter) | All text is escaped before display, and a strict Content-Security-Policy only allows Cadet Foundry's own script file. |
| Path tricks to read other files | Only files inside `web/` are served. |
| A tampered download | The private build page shows each zip's SHA-256 fingerprint. |

Automated attack tests for all of the above: `python -m unittest discover tests`.

## Forgotten PINs: the recovery code

When a Cadet sets a PIN, Cadet Foundry shows a **recovery code** once (`XXXXX-XXXXX-XXXXX-XXXXX`, 100 bits). It's a second key to that Cadet's files. If they forget their PIN, **Forgot PIN?** on the lock screen takes the code and a new PIN; the files stay encrypted throughout and a fresh code is issued. Wrong codes count toward the same lockout as wrong PINs. A new code can be made any time in Me → Security (with the PIN).

There is **no master key for private files**: not the device owner, not the instructor, not Cadet Foundry can open a Cadet's private files (check-ins, chats, notes, letters, logbook, profile) without that Cadet's PIN or recovery code. The one deliberate exception is **class records**: the instructor can read those with the Instructor PIN — see "Instructors and class records" below. If a Cadet loses both their PIN and recovery code, their encrypted backup (below) is the way back.

## What the device owner must do too

Cadet Foundry encrypts each Cadet's files, but full-disk encryption still protects everything else on the device (the AI model, the library, Windows itself). **Turn it on:**

- **Windows**: BitLocker (Settings → Privacy & security → Device encryption, or BitLocker on Pro editions). Use a Windows sign-in PIN/password.
- **Linux / Raspberry Pi**: LUKS full-disk encryption at install time.

Also: keep the OS updated, use a standard (non-admin) account for daily use, and don't install other software on a dedicated Cadet Foundry device.

## Backups
**Me → Download encrypted backup** saves one file (profile, logbook, letters, address book, study progress, memory), encrypted with AES-256-GCM under a **backup password of at least 10 characters** that the Cadet chooses (a backup can be attacked offline, so a 6-digit PIN isn't enough). Without the password the file can't be opened. Device settings (AI model, online switch, keys) are never included, and restoring a backup can never change them.

A backup is a file its owner controls, so restoring one is treated as the owner's own word: it can never change device settings, make anyone an instructor, or write assigned-lesson grades (`assignments.json` isn't in a backup), and a file of the wrong shape is skipped. It **can** bring back the owner's own practice history (`study.json`, `exams.jsonl`), which instructors also see — so practice counts and practice-exam scores are self-reported, while assigned-lesson scores are graded by Cadet Foundry. Restoring is selective: files in the backup replace the matching files; files it doesn't hold are left as they are.

## Library tamper check
When the library is installed, Cadet Foundry records a SHA-256 fingerprint of every manual (`library/integrity.json`). At startup it recomputes them: **Me → Library check** says whether every file still matches, and search marks any result from a changed file. If the publisher signed the list (`tools/sign.py library` → `integrity.json.sig`), the signature is checked too, so editing a manual *and* its fingerprint doesn't go unnoticed.

## Signed offline updates
An update is the normal release zip plus a `.sig` file. On a device: **Me → Install an update from a USB stick**, choose both files, and give the Class PIN (instructor profiles only). Cadet Foundry installs it only if:
- the signature is a well-formed Ed25519 signature (exactly 64 bytes, strict base64) that matches the publisher's public key (`vanguard/data/release_key.pub`);
- it's a **newer** version (no downgrades, no reinstalling the same version);
- every file is inside the app's own folders (no unexpected names, `..`, drive letters, `:` stream names or control characters).

A copy without a public key refuses every update (fail closed). Everything is unpacked before anything changes, and
every file the update replaces is copied aside first: if a step fails, the app is put back exactly as it was, and if
Cadet Foundry stops part-way, the next start rolls it back. Cadets' data (`~/.vanguard`) is never touched. Then restart
Cadet Foundry. Tested in `tests/test_security.py` (valid, tampered, unsigned, malformed, wrong key, downgrade, equal
version, unsafe paths, no public key, failed and interrupted installs).

**The release chain.** `python site/build.py` → the release zip (and the Windows installer) → signed with the private
key into `<zip>.sig` → both published on the public releases page → a device verifies the `.sig` against the public
key it already has, then installs. The public key ships inside the app; a device trusts only the key it was installed
with. Note: the Windows **installer** (`CadetFoundry-Setup-*.exe`) is a separate, first-time install path — it is not
checked by this key. Windows code signing (a paid certificate in the company's name) is what makes Windows trust the
installer itself; it's an owner action that hasn't been done yet, so Windows shows "Windows protected your PC".

**For the publisher (build machine only):**
1. **Create (once):** `python tools/sign.py keygen` — writes the private key to `~/.vanguard-release/release_key.pem`
   and the public key to `vanguard/data/release_key.pub`. Commit only the `.pub`. Done by the owner on 2026-10-11.
2. **Store:** keep `release_key.pem` only on the build computer (BitLocker on, standard account), never in git, a
   zip, a USB that goes to schools, chat or email. A test checks that no private key is tracked in the repository.
3. **Back up:** one offline copy (a password manager's secure file, or an encrypted USB kept locked away). Without it
   no further update can be signed for devices already installed.
4. **Each release:** `python site/build.py --release` signs the zip automatically when the key is present ("Signed:" in
   the output; `tools/sign.py sign <zip>` does it by hand). Optionally `python tools/sign.py library` first, to ship a
   signed library list.
5. **Rotate or recover:** if the key is lost or may have been copied, make a new one (`keygen --force`), commit the new
   `.pub` and release a new version. Devices with the old key can't verify updates signed with the new one, so they
   must be reinstalled from the new installer (their data folder is kept). Tell schools when this happens.
Anyone who has the private key can sign updates — treat it like a password.

**Status (2026-10-11):** the owner created Cadet Foundry's key; `release_key.pub` is in the app. Releases from now on are
signed. A full end-to-end check (build → sign → install on a clean device from the signed zip) is on the pilot
checklist and hasn't been run yet.

## Online AI (off by default)
**Cadet Foundry is offline-first: no student data leaves the instructor's device unless an instructor or IT operator explicitly enables an online AI provider.** There is no switch for it in the app's screens. An operator enables it only by editing `config.json` in the data folder (`"online": true` plus a Groq or Gemini key; the key is stored there in plain text). Leave it off on devices meant to stay fully offline, and read the provider's terms (data retention, use of minors' data) before turning it on.

**Pilot mode** (Instructor → Reports → Pilot) overrides that file: while it's on, nothing goes online, whatever `config.json` says (`engine.online_ready`; tested in `tests/test_sample_and_pilot.py`).

When it is on, exactly this goes to the provider (security review, 2026-10-11 — tested in `tests/test_outbound_ai.py`):
- **Ask, ordinary questions only:** the question, Cadet Foundry's rules, and the public library passages that matched.
  **Not** the Cadet's name, profile, remembered facts, logbook or earlier chat.
- **Never:** a message that shows signs of crisis or harm (answered on this device only), grading of typed quiz answers
  (it carries answer keys), memory learning from chats, letter drafts, "say it simpler", lessons, class records,
  instructor notes, PINs or anything about other Cadets.

**Corrected 2026-10-11:** before this, every AI task tried the online provider first, with the full personal context
(profile, remembered facts, logbook, the last 8 chat messages) — including crisis messages, grading and letters —
even though this section said grading never used it.

## Safety check on Ask (what it does and doesn't do)

Every message typed into **Ask** is checked against patterns for self-harm, suicide, abuse, sexual assault and
hazing (`vanguard/safety.py`). What happens:
- **A first-person disclosure** ("I want to…", "my dad hits me"): help comes first — call or text 988, text HOME to
  741741, RAINN, Childhelp, 911, and the Cadet's own trusted people if they added any — then a short, caring reply that
  encourages them to reach a person now. It works with no internet and no AI (a fixed caring message).
- **The topic only** ("explain the suicide prevention brief"): a short neutral line (988, a trusted adult, 911), then a
  normal answer.

What it **doesn't** do:
- **It notifies no one.** No instructor, parent, counselor or anyone at the Cadet Foundry project is told. Nothing is flagged or reported;
  the conversation stays in the Cadet's own private, encrypted chat history, which the instructor can't read.
- **It is best-effort pattern matching, not a crisis detector.** It misses indirect or new wording ("I just want
  everything to stop"), can't know anyone's intent, and sometimes shows resources when someone is joking.
  `tests/test_safety.py` lists what it catches, accepted false positives and known misses.
- **It only checks Ask.** Check-ins, journal notes, reflections and survey comments are not scanned.

Schools must fit Cadet Foundry into their own safeguarding and incident-response procedures; Cadet Foundry is not one of them.
Tell Cadets plainly: Cadet Foundry is not monitored — if you're in danger or thinking about hurting yourself, tell an adult
or call 988 or 911.

**What's private, in plain words (tell Cadets):** your check-ins, notes, chats with Ask and letters are yours alone
— not even your instructor can open them. Your instructor can see class work: lessons, quizzes, exams, leadership
log, fitness and service. Votes in class are anonymous (counts only). Cadet Foundry doesn't watch or read your private
things, and no one is alerted by anything you type.

## The classroom network (Open class to phones on the instructor's Home; `--lan`, the Cadet Foundry Classroom shortcut, the USB's Start Classroom file, the Pi demo box)

In the app this is called **class is open**; the **Class PIN** is the code this document also calls the Instructor PIN.

In classroom mode the instructor's computer accepts connections from other devices on the same network. What that means:

| Who | Can | Can't |
|---|---|---|
| Any device on the same Wi-Fi | Open the sign-in screen and the Join screen (`/join`: the class address and a QR code; how many Cadet profiles exist); see **shortened** profile names ("Ana R.") of profiles that have a PIN; look up which unit a join code belongs to; download the installer if offered | Read anything without a profile's PIN; see or open a profile that has **no PIN** (those open only on the instructor's own computer, and the instructor is told which ones they are); remove a PIN; reach instructor routes; try the Class PIN |
| A Cadet signed in | Their own work, assignments, live votes and questions; join a unit with its join code | Another Cadet's anything; the instructor's tools (HTTP 403); change device settings or guess the Class PIN (only instructor profiles may try it, so a Cadet can't lock the instructor out); end class for everyone (Quit works only from the instructor's computer or an instructor profile) |
| The instructor, signed in **and** with the Class PIN | Class records of every Cadet; open or close class to phones (from their own computer only) | Any Cadet's private files |

**Which addresses Cadet Foundry answers to** (security review, 2026-10-11). Every request's `Host` header must name
Cadet Foundry itself with Cadet Foundry's port: `127.0.0.1`, `localhost` or `[::1]` from this computer, and in classroom mode
also this computer's own IP address — exactly the address the device connected to (what the QR code shows). A domain
name is refused in classroom mode, which blocks DNS rebinding (a website pointing its own name at the instructor's
computer so a Cadet's browser would treat Cadet Foundry as that site). Before this fix, classroom mode accepted any Host.
Requests that carry an `Origin` must come from Cadet Foundry's own address; POSTs must be JSON (which forces browsers to
ask first, and Cadet Foundry refuses those preflights); the session cookie is `HttpOnly; SameSite=Strict` with no
`Domain`. Tested in `tests/test_network.py`.

Known limits, and what to do about them:
- **Traffic is plain HTTP.** Someone capturing Wi-Fi traffic on the same network could read pages and PINs as they're
  typed. A protected Wi-Fi network is a mitigation, not a replacement for encryption in transit.
  **Restricted pilot configuration until HTTPS exists:** a dedicated hotspot or travel router with a WPA2/WPA3
  password that only the class joins — not the school's open or guest Wi-Fi; Cadets use PINs they don't use anywhere
  else; and **fictional test profiles**, not real Cadets, until the school approves the data practices.
- **Why there is no HTTPS switch yet** (evaluated 2026-10-11): a classroom server has no public name, so a normal
  certificate can't be issued for it. A self-signed certificate makes every Cadet's phone show a full-page security
  warning that has to be clicked through, which trains people to ignore warnings and doesn't stop an active
  attacker; installing a classroom certificate authority on every Cadet's personal phone isn't practical. The
  workable design is the one some media servers use: a public domain the publisher controls with a per-installation
  name that resolves to the laptop's private address, and a real certificate for it issued through DNS validation.
  That needs publisher-run infrastructure (a domain, DNS, certificate issuance and renewal) and is an owner decision.
  Until then Cadet Foundry doesn't offer an HTTPS option that would leave PINs exposed or produce unusable warnings.
- **PIN guessing** is slowed by growing lockouts (5 wrong PINs → a lockout that doubles, up to an hour, surviving restarts) and scrypt.
- **School Wi-Fi often blocks devices from reaching each other** ("client isolation") — then Cadets can't connect at all; use the dedicated hotspot.
- Close Cadet Foundry when class ends (**End class** on the Join screen, **Close to phones** on Home, or Me → Quit). The instructor's Home shows "Class is open" while it runs.
- **Join codes** (0.2) are short codes (6 characters from 31, about 887 million combinations) that put a *new* Cadet's own profile in a class, platoon or squad and give it that unit's lessons. They're kept in the clear in `program/join_codes.json` with the unit's name, because a Cadet's session has no program key; they open nothing else and never reveal any Cadet or record, and they're not secret (they're on the projector, and in the QR code's `?join=` link). The join request is sealed to the program key in `program/joins.json` until an instructor's session files it. An instructor can replace a code (the old one stops working). The Join screen shows codes on the instructor's own computer, never to other devices.

## Dependencies (reviewed 2026-10-11)
Cadet Foundry is Python's standard library plus one package, `cryptography` (PyCA). Everything else is optional and only fetched when someone with the device-admin role asks for it.

| What | Where it comes from | How it's fixed |
|---|---|---|
| Python 3.14.8, embeddable (Windows installer) | python.org | exact URL + SHA-256 in `site/build.py` (matches the hash python.org publishes) |
| `cryptography` 50.0.2, `cffi` 2.1.1, `pycparser` 3.0 (Windows installer) | PyPI | exact versions + SHA-256 in `site/bundle-requirements.txt`; the build uses `pip --require-hashes`, so a changed file stops the build |
| `cryptography` (Linux, Raspberry Pi, Mac, source installs) | PyPI, through `tools/setup.py` | at least 50.0.0 (every earlier release has published advisories); not exact, because each platform needs its own wheel. The USB's Mac/Linux starter refuses an older copy and says how to upgrade |
| Voice add-on: pip 26.2.1 (as one file), `vosk` 0.3.45, the small English model 0.15 | bootstrap.pypa.io, PyPI, alphacephei.com | pip and the model: exact URL + SHA-256 in `vanguard/addons.py`, refused on mismatch. `vosk` and its own dependencies: exact `vosk` version only |
| AI add-on: Ollama | ollama.com (latest installer) | Windows checks the installer's Authenticode signature is valid and from Ollama before running it; the model is pulled by Ollama itself |
| `wrangler` 4.141.0 (publishing the website only, owner's computer) | npm | exact version in `site/build.py` |
| `pypdf` (`tools/setup.py`, converts official PDFs on the owner's computer) | PyPI | not pinned; it never ships to Cadets |

**Before every release:** `python tools/check_deps.py` asks the OSV database (osv.dev) about every pinned package and fails if one has a known vulnerability; only names and version numbers are sent. On 2026-10-11 it reported none. To update a pin: choose a release that is at least two weeks old, check it with OSV, download the wheels with `pip download --only-binary=:all: --platform win_amd64 --python-version 3.14`, record their SHA-256, then build and run the test suite **on the bundled Python** (`app/python/python.exe -m unittest discover -s tests`) — that was done for this set (193 tests, OK).

**Python itself:** the 3.12 line stopped getting Windows builds at 3.12.10, so later 3.12 security fixes never reached the installer; the installer moved to 3.14 (the current line with Windows builds) on 2026-10-11. When 3.14 reaches its security-only phase, move to the next line the same way.

**Secrets:** the repository is checked by `tests/test_security.py` for a release private key, and history was searched for keys and passwords during the 2026-10 review (see the review report). If a secret is ever found, rotate it first — removing it from the files doesn't un-publish it.

## Sample class and End pilot (added 2026-10-11)
- **Sample class** (`vanguard/sample.py`): a separate Cadet Foundry process on this computer only (127.0.0.1, its own port), with its own data folder next to the real one (`<data>-sample`, marked by `SAMPLE_DATA.txt`; only a marked folder is ever deleted, and it's rebuilt from scratch each time). Its people are made up, it uses its own cookie name so it never signs anyone out of the real Cadet Foundry, it refuses device settings and opening to the network, and it closes itself after 45 idle minutes or on Leave sample. Only the library's public search index is copied in; nothing is read from or written to the real data. Starting it is allowed only from the instructor's own computer.
- **End pilot** (`pilot.end`): instructor session with the Class PIN open, **on the instructor's own computer**, the Class PIN typed again, and the word DELETE. It removes every Cadet and guardian profile (via `profiles.delete`, which deletes the whole profile folder), their sessions, assignments, the roster's Cadets, titles and pending joins, live answers, the pilot's files, and `program.before-restore-*` safety copies; units keep going with new join codes. It doesn't touch personal or program backups already saved elsewhere, and it doesn't wipe free disk space.

## For military IT: adding CAC sign-in
Cadet Foundry deliberately ships without CAC/PIV sign-in so that it can be configured by the Army's own IT, with its certificate validation and approval. All sign-in logic is in `vanguard/security.py`: a profile is unlocked by `unlock(profile, secret)`, which creates a session bound to that one profile. A smart-card provider would (1) have the card sign a random challenge with its PIV authentication key, (2) validate the certificate chain against the DoD PKI roots (and revocation, where a network is available), and (3) map the certificate to a profile by a hash of the certificate — never storing the DoD ID number. Nothing else in Cadet Foundry needs to change.

## Official use
Use inside military networks or as an issued device would additionally require formal accreditation (Authority to Operate, STIG compliance). This project is designed to make that process straightforward: no network services unless an instructor opens class to phones, one well-known dependency (`cryptography`, PyCA, for AES via OpenSSL; see Dependencies), all data local.

## Instructors and class records (added 2026-10-08)

Decision by the program owner: **an instructor can read a Cadet's class records, and nothing else.**

- **Two keys per Cadet.** A Cadet with a PIN has a private data key (as above) and a separate **class key**. The
  class key seals only class-record files: `study.json`, `exams.jsonl`, `lessons.json`, `assignments.json`,
  `scenarios.jsonl`, `service.jsonl`, `fitness.jsonl`, `goals.json` (`store.CLASS_FILES`). Everything else -- check-ins,
  chats, memories, letters, logbook, profile -- stays sealed with the private key only.
- **How the instructor gets the class key.** The class key is stored twice in the Cadet's `security.json`: sealed
  with the Cadet's data key (so PIN changes and recovery codes keep working), and sealed to the **program public
  key** (X25519 + HKDF-SHA256 + AES-256-GCM). The program private key is in `program.json`, locked by the
  **Instructor PIN** (scrypt + AES-256-GCM, like a profile PIN).
- **Two factors to read class records:** an instructor profile session (its own PIN) **and** the Instructor PIN,
  entered in that session. The program key lives only in that session's memory and is dropped at sign-out or
  timeout. Cadet sessions get HTTP 403 on every `/api/instructor/*` route, even if they know the Instructor PIN.
- **Creating an instructor profile** requires the Instructor PIN and the new profile's own PIN. A restored backup
  can never turn a profile into an instructor.
- **The roster** (classes, platoons, squads, each Cadet's unit and LET level) is sealed with a key derived from the
  program private key; it is ciphertext on disk.
- **Timing.** A Cadet who set a PIN before the Instructor PIN existed shares class records at their next sign-in
  (the instructor screen shows "Waiting"). A Cadet without a PIN has no encryption at all; LAN classroom mode
  refuses to start until every profile has a PIN.
- **Resetting the Instructor PIN** (deleting `admin.json`) creates a fresh program key: Cadets re-share at their next
  sign-in, and the old roster can't be read and starts over. Changing the Instructor PIN with the current PIN keeps
  the same key.
- Tests: `tests/test_classroom.py` (keys and files) and `tests/test_security.py`
  (`test_instructor_routes_need_an_instructor_profile_and_the_instructor_pin`).
