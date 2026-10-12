# Pilot data handling

For the school, the instructor and parents. It says what Cadet Foundry stores during a pilot, who can see it, and how to
export it, delete it, or remove a Cadet who leaves. Technical detail: [DATA_INVENTORY.md](DATA_INVENTORY.md) and
[../SECURITY.md](../SECURITY.md). Written 2026-10-11 for version 0.2.3; Pilot mode and End pilot need 0.2.4.

## What is stored, and where

Everything is stored in one folder on the instructor's computer: `.cadetfoundry` in the user's home folder, or
`Cadet Foundry Data` on the USB drive when Cadet Foundry runs from a USB. Nothing is stored on Cadets' phones or tablets, which
only show pages. There is no Cadet Foundry project server, cloud account or analytics.

| What | Example | Protection |
|---|---|---|
| Profile name and PIN | "Cadet Ruiz", a 6-digit PIN | Name is in the profile list in plain text (it's shown on the sign-in screen). The PIN is stored only as a slow, salted hash |
| Private files | Ask chats, check-ins, notes, letters, logbook, address book | Encrypted with the Cadet's own key. **Nobody else can open them**: not the instructor, not the device owner, not the Cadet Foundry project |
| Class records | Assigned lessons and scores, practice and exam results, leadership scenarios, fitness, service hours, goals, recognition | Encrypted with a per-Cadet class key that only an instructor profile with the Class PIN can open |
| Program data | Units, roster details (Cadet rank, billet, year), lessons, pilot setup, notes, snapshots, survey answers | Sealed with the program key (opened by the Class PIN). Lesson text and answer keys, assignments and Cadet titles are kept in the clear so they work before sign-in. They hold no private information |
| Live class votes and pop-quiz answers | "B", "4" | Kept in memory only while class runs; the instructor sees counts, never who |

**What Cadet Foundry doesn't ask for:** email, phone number, address, photos, birth date, sex, or body measurements
beyond what a Cadet types into Train themselves. Cadets can type anything into free-text fields, so tell them not to
put other people's private information in notes or letters.

## Who sees what

| | The Cadet | Other Cadets | Instructor (profile + Class PIN) | Device owner / IT, without PINs |
|---|---|---|---|---|
| Private files | ✓ | ✗ | ✗ | ✗ (encrypted) |
| Their class records | ✓ | ✗ | ✓ | ✗ (encrypted) |
| Names in the profile list | ✓ | shortened, on the sign-in screen | ✓ | ✓ |
| Live answers | their own | ✗ | counts only | ✗ |
| Pilot survey answers | ✗ after sending | ✗ | yes, with no name or ID, in random order | ✗ (sealed) |

**Nobody is monitoring Ask.** It has a safety check that shows help numbers (988, 911, Childhelp, RAINN) when a
message sounds like someone is unsafe. It **notifies no one**, so a Cadet in danger must still tell a trusted adult.
Instructors should say this to the class in plain words.

**Pilot mode** (Instructor → Reports → Pilot) lists what is
stored on the device in counts, and offers End pilot (below). Recommended for every pilot.

**There is no online AI.** Nothing is sent to the internet; the only AI is the optional offline one on the
instructor's computer.

## Exporting

- **Class report:** Instructor → Reports → Class report (spreadsheet). It holds class records for every Cadet: treat it like a gradebook,
  don't email it unencrypted, and delete copies when the pilot report is done.
- **Pilot report:** Instructor → Reports → Print pilot report. Totals and changes only.
- **A Cadet's own data:** Me → Download encrypted backup (protected by a password of 10+ characters the Cadet chooses).
- **Program backup:** Instructor → Settings → Program backup. Lessons, units and the program key, password-protected. It never
  contains any Cadet's files.

## Deleting, and when a Cadet leaves

- **A Cadet deletes their own profile:** Me → Delete profile (needs their PIN). Every file in their folder is
  deleted, private files and class records alike, and their open sessions end.
- **A Cadet who left and can't sign in:** there is no instructor button for this yet. With Cadet Foundry closed, the
  device owner runs `python tools/remove_profile.py` (it lists the profiles), then
  `python tools/remove_profile.py "Cadet Name"` and types DELETE. From a USB drive, use the drive's own Python:
  `"Cadet Foundry\python\python.exe" "Cadet Foundry\tools\remove_profile.py" "Cadet Name" --data "Cadet Foundry Data"`. Or keep the
  profile until the school's retention period ends; decide this before the pilot (below).
- **End of the pilot:** turn on **Pilot mode** (Instructor → Reports → Pilot) and use **End pilot**. It asks you to
  save the class report and the pilot report first, then needs the Class PIN and the word DELETE, and works only on
  the instructor's own computer. It permanently removes every Cadet and guardian profile (private files and class
  records), the assignments, the pilot's setup, snapshots and survey answers, pending joins, and program safety
  copies; it keeps instructor profiles, the Class PIN, your lessons and your classes (with new join codes). To remove
  everything, uninstall Cadet Foundry and delete the data folder instead. Deleting a file doesn't wipe the disk, so
  full-disk encryption (BitLocker) on the instructor's laptop is what protects deleted data.
- **Lost or stolen laptop or USB drive:** private files and class records stay encrypted without the PINs. Names in
  the profile list and program data in the clear (lesson text, units) are readable. Change the Class PIN and treat
  it as a data incident under the school's policy.

## Decide before the pilot (school and owner)

1. **Retention:** how long class records are kept after the pilot, and who deletes them.
2. **Who is the device owner** (the instructor, or school IT) and where the laptop is kept.
3. **Offline AI on the instructor's computer:** optional; decide whether Cadets may use Ask with it in class.
4. **Parent notice:** what is stored, who sees it, that Ask isn't monitored, and how to ask for deletion.
5. **Use fictional profiles** ("Cadet Alpha", "Cadet Bravo") for demos, screenshots and the dry run, never real
   Cadets.

## Reporting a security problem

Report suspected vulnerabilities privately to **support@cadetfoundry.org**, not in a public issue. The same address
answers questions, requests for deletion help, and instructors who'd like their own copy.
