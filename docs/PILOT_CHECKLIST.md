# Pilot checklist

One page to go through before, during and after a classroom pilot. Data rules: [PILOT_DATA_HANDLING.md](PILOT_DATA_HANDLING.md).

## Before (owner and school)

- [ ] Install **0.2.4 or newer** from the website (it has the sample class, Pilot mode and End pilot). 0.2.2 can't take updates, so reinstall it; 0.2.3 updates itself.
- [ ] Laptop: BitLocker on, Windows updated, a standard (non-admin) account for daily use, a screen lock.
- [ ] Retention, device owner, parent notice and the offline AI decided (PILOT_DATA_HANDLING.md → "Decide before the pilot").
- [ ] A security contact published, so a school or parent can report a problem privately.
- [ ] Classroom network: a **dedicated hotspot or travel router** that only the class joins (not open or guest Wi-Fi).
      Traffic between phones and the laptop is plain HTTP on that network; see SECURITY.md → "The classroom network".
- [ ] Test the school Wi-Fi once if you'll use it: some school networks block devices from reaching each other, and
      then phones can't open the Join page.

## Dry run (with fictional profiles, never real Cadets)

- [ ] Optional first look: **See a sample class** (on the welcome screen, or the 🧪 tile on the instructor's Home). It
      opens a separate copy of Cadet Foundry with eight made-up Cadets; Leave sample closes it and nothing of yours changes.

- [ ] Set the Class PIN, then make an instructor profile with its own PIN.
- [ ] Make a class, press **▶ Start class**, and present a short plan on the projector with the arrow keys.
- [ ] Turn Cadet phones on, and join from two phones as "Cadet Alpha" and "Cadet Bravo".
- [ ] Assign a lesson. Complete it on one phone; check the score on the instructor's screen.
- [ ] Run a scenario with a class vote and a live question: the instructor sees counts, not names.
- [ ] Ask on a phone; check the help line shows for "I want to kill myself" and doesn't for "this homework is
      killing me". It notifies no one.
- [ ] Download the class report and print the pilot report.
- [ ] Program backup: make one and keep it off the laptop with its password.
- [ ] Close class to phones. Delete the fictional profiles (`python tools/remove_profile.py`).

## First day with Cadets

- [ ] Tell them in plain words: your chats in Ask are private and **nobody is watching them**. If you're not safe,
      tell an adult you trust or call or text 988 (911 in an emergency).
- [ ] Tell them: pick a PIN nobody can guess, don't share it, and keep the backup code somewhere safe.
- [ ] Turn on **Pilot mode** and take the pilot snapshot (Instructor → Reports → Pilot).

## Every week

- [ ] Take a snapshot. Close class to phones when class ends.
- [ ] When you press **Finish class**, answer "How useful was Cadet Foundry today?" (a few seconds; you can skip it).

## After

- [ ] Open the Cadet survey, then close it. Print the **one-page summary** (and the full pilot report if the school wants it).
- [ ] Export what the school keeps, then **End pilot** (Instructor → Reports → Pilot) per the retention decision
      (PILOT_DATA_HANDLING.md).
