# What Vanguard stores, and how it's protected

Last reviewed: 2026-10-11 (security review, Phase 2). This lists every file Vanguard writes, what's in it, how
sensitive it is, how it's protected at rest, and who can read it. It also states the limits plainly. Encryption at
rest and access control are separate things; both are listed for each file.

All data lives in one folder: `%USERPROFILE%\.vanguard` on an installed computer, or `VanguardData\` on a USB drive.
Nothing is sent anywhere unless the instructor turns on online AI with their own key (see "Leaving the device").

## Keys

| Key | What it is | Where it lives | Who holds it in memory |
|---|---|---|---|
| A profile's data key | Random 256-bit AES-GCM key | `profiles/<id>/security.json`, wrapped by the profile's PIN (scrypt) | That profile's signed-in session |
| A Cadet's class key | Random key for the Cadet's class records | Sealed by the data key, and sealed TO the program public key | The Cadet's session; an instructor session after the Class PIN |
| Program key pair | X25519 key pair for the whole program | `program.json`: public key plain, private key wrapped by the Class PIN (scrypt) | An instructor session after the Class PIN |
| Program data key | Derived from the program private key | Never stored | Same as the program key |

No key is stored unwrapped on disk. Losing every PIN and backup code makes the matching data unreadable; there is no
master key.

## Each person's own folder: `profiles/<id>/`

| File | Contents | Sensitivity | At rest | Who can read it |
|---|---|---|---|---|
| `security.json` | PIN hash (PBKDF2), wrapped data key, sealed class key, lockout counter | Secret material, but no plaintext secrets | Hashes and wrapped keys only | The server, to check a PIN |
| `profile.json`, `memory.jsonl`, `log.jsonl`, `checkins.jsonl`, `chat(s).json`, `letters.jsonl`, `contacts.json`, budgets, plans… | Private notes, chats with Ask, check-ins, letters | **High** (private; may include wellbeing disclosures) | AES-256-GCM with the data key | Only that person's signed-in session. **Never the instructor.** |
| Class records: `study.json`, `exams.jsonl`, `assignments.json`, `scenarios.jsonl`, `service.jsonl`, `fitness.jsonl`, `goals.json`, `recognition.jsonl`, `lessons.json` | Quiz progress, exams, lesson work, leadership log, service hours, fitness results | **Medium** (education records) | AES-256-GCM with the Cadet's class key | The Cadet; an instructor session after the Class PIN |
| `pilot_feedback.json` | Only "this Cadet answered the survey" | Low | Sealed with the data key | That Cadet |

**A profile with no PIN is not encrypted.** Its files are plain JSON. Vanguard shows "No PIN on this profile —
records aren't protected", and on the classroom network such a profile can only be opened on the instructor's own
computer.

## The program folder: `program/`

| File | Contents | Sensitivity | At rest | Who writes / reads |
|---|---|---|---|---|
| `roster.json` | Units, which Cadet is in which unit, year level | Medium | Sealed with the program data key | Instructor session only |
| `lesson_notes.json` | The instructor's private lesson notes | Medium | Sealed with the program data key | Instructor session only |
| `joins.json` | Join requests waiting to be filed ("profile X asked to join unit Y") | Low–Medium | Each request sealed TO the program public key | Written by the joining Cadet's session (it can't read it back); read by an instructor session |
| `pilot.json` | Pilot setup: school, instructor name, dates, notes | Medium | Sealed with the program data key | Instructor session only |
| `pilot_snapshots.json` | Weekly class totals | Low–Medium | Sealed with the program data key | Instructor session only |
| `feedback_instructor.json` | The instructor's own feedback | Low | Sealed with the program data key | Instructor session only |
| `feedback_cadets.json` | Anonymous Cadet survey answers (no name, no id) and optional comments | Medium (free text) | Each answer sealed TO the program public key, stored in random order | Written by a Cadet's session (it can't read any back); read by an instructor session |
| `pilot_survey.json` | Only "is the survey open" | None | Plain (a Cadet's screen needs it) | Anyone |
| `lessons.json` | Lesson text, questions, vocabulary, **and the answer key** | Low (content); answer keys matter for academic honesty | **Plain** — see limits | Read by Cadet sessions to show a lesson and grade it; the answer key is never sent to a Cadet |
| `assignments.json` | Which lesson is assigned to which Cadet profile ids, due dates | Low–Medium | **Plain** — see limits | Read by Cadet sessions (to list their own) and the instructor |
| `cadet_titles.json` | A Cadet's cadet rank and billet (job), by profile id | Low | **Plain** — see limits | Read by the Cadet's own Home screen |
| `join_codes.json` | Each unit's join code and name | Low (codes are shown on the projector) | Plain | Needed before sign-in |
| `scenarios.json`, `quiz_overrides.json`, `service_projects.json`, `fitness_events.json` | The instructor's own content and settings | None–Low | Plain | Instructor writes; Cadets read what applies to them |
| Live classroom vote, live question | Who voted for what / answered what, during one class | Medium | **Never written to disk** (memory only; ends when Vanguard closes) | Cadets see only their own; the instructor and projector see counts only |

## Device files

| File | Contents | At rest |
|---|---|---|
| `profiles.json` | Each profile's id, **display name**, role, created date | Plain — the sign-in screen lists names before anyone signs in. Other devices on the classroom network see shortened names ("Ana R."). |
| `admin.json` | Class PIN hash (PBKDF2) and lockout counter | Hash only |
| `program.json` | Program public key; private key wrapped by the Class PIN | Wrapped only |
| `config.json` | Device settings (AI mode, Learn categories, online-AI keys if the instructor added any) | Plain — **online-AI keys, if entered, are stored here in plain text** |
| `library_index.json` | Search index of the public library | Not personal |
| `vanguard.log` | Startup messages for the installed app (no requests, PINs or answers are logged) | Plain |

## Backups and exports

- **Personal backup** (Me → Download encrypted backup): that person's files, sealed with a backup password (scrypt +
  AES-256-GCM). Never includes anyone else's files.
- **Program backup** (Instructor → Settings): the program folder, `program.json` and `admin.json`, sealed with a
  backup password. Never includes any Cadet's files. Sealed files inside stay sealed.
- **Class report CSV**: plain text the instructor downloads on purpose. It holds class records; treat it like a
  gradebook.

## Leaving the device

Vanguard never connects to the internet on its own. It does so only when someone chooses to:

- **Online AI**: only if the instructor turns it on and enters their own provider key. Then a Cadet's Ask question
  (and the library passages used to answer it) go to that provider. See SECURITY.md.
- **Add-on installs** (offline AI, voice): a download from the provider, started by the instructor.
- **Links** (YouTube, DVIDS pages) open in the browser like any link.
- **The classroom network**: in classroom mode, Cadets' devices on the same Wi-Fi talk to the instructor's computer.
  This traffic is plain HTTP today (see SECURITY.md, "The classroom network").

## Known limits (not fixed by encryption)

1. **Lesson answer keys are plain on disk.** Grading happens in the Cadet's own session, which has no program key,
   so the key can't be sealed without removing instant grading. Cadets never receive an answer key over the
   network. Someone who can read the instructor's data folder can read it: use BitLocker and a standard Windows
   account, and don't let Cadets use the instructor's Windows account.
2. **Names are plain** in `profiles.json` (the sign-in screen needs them before anyone signs in).
3. **Assignments and cadet titles are linked to profile ids in plain files.** Cadet sessions read them without the
   program key. Low sensitivity (which lesson, which rank), but they are education-related records.
4. **Anonymous survey limits.** Answers carry no name or id and are stored in random order, but a free-text comment,
   the answer date, or an unusual combination of answers can still identify someone in a small class. Tell Cadets
   not to put names or personal details in comments.
5. **Live votes are anonymous to people, not to the server.** While a vote is running, the server holds which
   profile voted for what (one vote each, and each Cadet sees their own). It is never shown or saved.
6. **A profile without a PIN isn't encrypted.**
7. **Encryption at rest doesn't protect a computer that's on and unlocked.** While a session is open, its keys are in
   memory. Lock Windows when you step away; Vanguard signs people out after inactivity.
8. **Class PIN reset.** Resetting the Class PIN (without the old one) makes a new program key: the old roster,
   pilot files and sealed join requests can no longer be opened.
9. **None of this alone establishes FERPA or state student-privacy compliance.** The school decides whether and how
   Vanguard fits its policies.
