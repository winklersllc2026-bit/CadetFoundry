# Security

Vanguard is built to run **completely offline** on the instructor's laptop (Cadets connect over the classroom network) or on a single device. No account, no tracking, no GPS, no data sent anywhere.

## What protects the Cadet's data

| Threat | Protection |
|---|---|
| A website open in the same browser tries to send commands to Vanguard (CSRF) | Commands must be JSON (browsers must ask permission first, and Vanguard never grants it); any request from another site's origin is refused; no CORS headers are ever sent. |
| A website tries to read Vanguard's data by pointing its name at this computer (DNS rebinding) | Requests are only accepted for Vanguard's own address (`127.0.0.1` / `localhost`). |
| Another Cadet on a shared device | Each Cadet has their own **profile** (separate folder, own PIN). A session is bound to one profile; every request can only reach that profile's files, and Cadet data can't be read or written at all without an unlocked profile. |
| Someone else on the same network | Vanguard only listens on this device. LAN mode (`--lan`) refuses to start unless every profile has a PIN. |
| One Cadet changing Vanguard for everyone on a shared device | Installing an update (and reloading the library) needs a separate **Instructor PIN**, stored as a salted PBKDF2 hash outside every profile, with the same growing lockouts. A profile PIN is not enough. |
| Someone picks up the device | **PIN lock** (strongly recommended — it also turns on encryption): 6–12 digits, stored only as a salted PBKDF2-SHA256 hash (400,000 rounds). Sessions are random tokens in an HttpOnly, SameSite=Strict cookie and expire after inactivity (5–60 minutes). Five wrong PINs start a lockout that doubles each time (up to 1 hour) and survives restarts. |
| Someone copies the files off the device (stolen tablet, USB, another Windows user) | A profile with a PIN has **its files encrypted** with AES-256-GCM using its own random 256-bit key. That key is stored only locked by the PIN (scrypt, 32 MB, memory-hard) and by the Cadet's recovery code, and is held in memory only while the profile is unlocked. Each file is bound to its name, so changed, damaged, swapped or renamed files are refused, never read. Only `security.json` (PIN hash, locked key) is unencrypted. |
| A crash or power loss while saving | Every file is written to a temporary file, flushed to disk, then renamed into place, so a save is all-or-nothing. |
| Injected scripts (from a document, an answer, a pasted letter) | All text is escaped before display, and a strict Content-Security-Policy only allows Vanguard's own script file. |
| Path tricks to read other files | Only files inside `web/` are served. |
| A tampered download | The private build page shows each zip's SHA-256 fingerprint. |

Automated attack tests for all of the above: `python -m unittest discover tests`.

## Forgotten PINs: the recovery code

When a Cadet sets a PIN, Vanguard shows a **recovery code** once (`XXXXX-XXXXX-XXXXX-XXXXX`, 100 bits). It's a second key to that Cadet's files. If they forget their PIN, **Forgot PIN?** on the lock screen takes the code and a new PIN; the files stay encrypted throughout and a fresh code is issued. Wrong codes count toward the same lockout as wrong PINs. A new code can be made any time in Me → Security (with the PIN).

There is **no master key for private files**: not the device owner, not the instructor, not Vanguard can open a Cadet's private files (check-ins, chats, notes, letters, logbook, profile) without that Cadet's PIN or recovery code. The one deliberate exception is **class records**: the instructor can read those with the Instructor PIN — see "Instructors and class records" below. If a Cadet loses both their PIN and recovery code, their encrypted backup (below) is the way back.

## What the device owner must do too

Vanguard encrypts each Cadet's files, but full-disk encryption still protects everything else on the device (the AI model, the library, Windows itself). **Turn it on:**

- **Windows**: BitLocker (Settings → Privacy & security → Device encryption, or BitLocker on Pro editions). Use a Windows sign-in PIN/password.
- **Linux / Raspberry Pi**: LUKS full-disk encryption at install time.

Also: keep the OS updated, use a standard (non-admin) account for daily use, and don't install other software on a dedicated Vanguard device.

## Backups
**Me → Download encrypted backup** saves one file (profile, logbook, letters, address book, study progress, memory), encrypted with AES-256-GCM under a **backup password of at least 10 characters** that the Cadet chooses (a backup can be attacked offline, so a 6-digit PIN isn't enough). Without the password the file can't be opened. Device settings (AI model, online switch, keys) are never included, and restoring a backup can never change them.

## Library tamper check
When the library is installed, Vanguard records a SHA-256 fingerprint of every manual (`library/integrity.json`). At startup it recomputes them: **Me → Library check** says whether every file still matches, and search marks any result from a changed file. If the publisher signed the list (`tools/sign.py library` → `integrity.json.sig`), the signature is checked too, so editing a manual *and* its fingerprint doesn't go unnoticed.

## Signed offline updates
An update is the normal release zip plus a `.sig` file. On a device: **Me → Install an update from a USB stick**, choose both files. Vanguard installs it only if:
- the signature matches the publisher's public key (`vanguard/data/release_key.pub`, Ed25519);
- it's a **newer** version (no downgrades);
- every file is inside the app's own folders (no unexpected or `..` paths).
Cadets' data (`~/.vanguard`) is never touched. Then restart Vanguard.

**For the publisher (build machine only):**
1. Once: `python tools/sign.py keygen` — writes the private key to `~/.vanguard-release/release_key.pem` (keep it safe and **off every device**; back it up) and the public key to `vanguard/data/release_key.pub` (commit it, so devices get it with the next install).
2. Each release: `python site/build.py` signs the zip automatically when that key is present (`tools/sign.py sign <zip>` does it by hand). Optionally `python tools/sign.py library` before building, to ship a signed library list.
Anyone who has the private key can sign updates — treat it like a password.

**Status (0.1.4):** Vanguard's own key has **not been created yet**. The public key the project was forked with
belonged to the earlier product and was removed in 0.1.4, so devices currently refuse every signed update (fail
closed). Step 1 above creates Vanguard's key.

## Online AI (off by default)
**Vanguard is offline-first: no student data leaves the instructor's device unless an instructor or IT operator explicitly enables an online AI provider.** There is no switch for it in the app's screens. An operator enables it only by editing `config.json` in the data folder (`"online": true` plus a Groq or Gemini key). From then on, questions typed into Ask are sent to that provider. Quizzes, lessons, class records and grading never use it. Leave it off on devices meant to stay fully offline.

## The classroom network (Start Classroom: `--lan`, the Vanguard Classroom shortcut, the USB's Start Classroom file, the Pi demo box)

In the app this is called **class is open**; the **Class PIN** is the code this document also calls the Instructor PIN.

In classroom mode the instructor's computer accepts connections from other devices on the same network. What that means:

| Who | Can | Can't |
|---|---|---|
| Any device on the same Wi-Fi | Open the sign-in screen and the Join screen (`/join`: the class address and a QR code; how many Cadet profiles exist); see **shortened** profile names ("Ana R.") and whether a profile has a PIN; look up which unit a join code belongs to; download the installer if offered | Read anything without a profile's PIN (every profile must have one in classroom mode — enforced at start and when a profile is made); remove a PIN; reach instructor routes |
| A Cadet signed in | Their own work, assignments, live votes and questions; join a unit with its join code | Another Cadet's anything; the instructor's tools (HTTP 403 even with the Instructor PIN); end class for everyone (Quit works only from the instructor's computer or an instructor profile) |
| The instructor, signed in **and** with the Instructor PIN | Class records of every Cadet | Any Cadet's private files |

Known limits, and what to do about them:
- **Traffic is plain HTTP.** Someone capturing Wi-Fi traffic on the same network could read pages and PINs as they're typed. **Recommended pilot setup: a dedicated hotspot with a WPA2/WPA3 password that only the class joins** (a phone hotspot, a travel router, or the Vanguard Pi demo box) — not the school's open or guest Wi-Fi. HTTPS for the classroom network is on the roadmap.
- **PIN guessing** is slowed by growing lockouts (5 wrong PINs → a lockout that doubles, up to an hour, surviving restarts) and scrypt.
- **School Wi-Fi often blocks devices from reaching each other** ("client isolation") — then Cadets can't connect at all; use the dedicated hotspot.
- Close Vanguard when class ends (**End class** on the Join screen, or Me → Quit). Instructor → Today shows "Class is open" while it runs.
- **Join codes** (0.2) are short codes (6 characters from 31, about 887 million combinations) that put a *new* Cadet's own profile in a class, platoon or squad and give it that unit's lessons. They're kept in the clear in `program/join_codes.json` with the unit's name, because a Cadet's session has no program key; they open nothing else and never reveal any Cadet or record. The join waits in `program/joins.json` until an instructor's session (which can open the sealed roster) files it. An instructor can replace a code (the old one stops working). The Join screen shows codes only to an instructor whose class is open.

## For military IT: adding CAC sign-in
Vanguard deliberately ships without CAC/PIV sign-in so that it can be configured by the Army's own IT, with its certificate validation and approval. All sign-in logic is in `vanguard/security.py`: a profile is unlocked by `unlock(profile, secret)`, which creates a session bound to that one profile. A smart-card provider would (1) have the card sign a random challenge with its PIV authentication key, (2) validate the certificate chain against the DoD PKI roots (and revocation, where a network is available), and (3) map the certificate to a profile by a hash of the certificate — never storing the DoD ID number. Nothing else in Vanguard needs to change.

## Official use
Use inside military networks or as an issued device would additionally require formal accreditation (Authority to Operate, STIG compliance). This project is designed to make that process straightforward: no network services, one well-known dependency (`cryptography`, PyCA, for AES via OpenSSL), all data local.

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
