# Cadet Foundry

**Leadership. Learning. Character.** A learning and leadership platform designed to support JROTC instructors and
Cadets. A free community project — the Cadet Foundry project.

Cadet Foundry runs on the instructor's laptop (or a USB drive, or a Raspberry Pi demo box). Cadets use it in a browser on
school computers, tablets or phones on the classroom network. The instructor stays in control; Cadet Foundry supplies the
tools.

**Cadet Foundry is offline-first.** No student data leaves the instructor's device unless an instructor or IT operator
explicitly enables an online AI provider (it is off by default and has no switch in the app's screens — see
SECURITY.md). No accounts on outside services, no advertising, no tracking.

Version 0.2.5. What's built and what's next: ROADMAP.md. How it fits together: ARCHITECTURE.md.

> Cadet Foundry is designed to support JROTC instruction. It is **not** an official JROTC, Army or school product, does not
> replace your instructor or your program's curriculum, and makes no claim of endorsement.

## Start here

1. **Install:** download Cadet Foundry for Windows from **cadetfoundry.org** and double-click it (or run it from a
   USB drive — below).
2. **Just looking?** On the first screen choose **See a sample class**: a separate copy with eight made-up Cadets,
   lessons, scenarios and a pilot in progress. Leaving it changes nothing.
3. **Set up:** tick the box to agree to the [Terms of use](cadetfoundry/legal/TERMS.md) and
   [Privacy notice](cadetfoundry/legal/PRIVACY.md), choose "I'm the instructor", and make your Class PIN and your own PIN.
4. **Teach:** add the **starter lessons** (one click), open class to phones, and press **▶ Start class**.

Running a pilot? Read [docs/PILOT_CHECKLIST.md](docs/PILOT_CHECKLIST.md) and
[docs/PILOT_DATA_HANDLING.md](docs/PILOT_DATA_HANDLING.md). Questions, problems, security reports, or a copy for
another instructor: **support@cadetfoundry.org**. Please don't pass your copy on — other instructors get their own
clean copy, with no one else's data on it.

## For Cadets

| Area | What's there today |
|---|---|
| **📘 Learn** | Your assignments from your instructor (lessons with vocabulary, questions and a reflection), 200+ study cards from U.S. government sources and Army manuals (leadership, citizenship and history, military knowledge, health and first aid, careers and money — each names its source), quizzes you type and Cadet Foundry grades (Practice with choices, Challenge typed), timed exams, and a library of public-domain books — the Declaration of Independence, the Constitution, the Bill of Rights, the Federalist Papers, American Military History (U.S. Army Center of Military History), and classics. Questions you miss come back more often. |
| **🧭 Lead** | Live questions and classroom votes from your instructor, and 20 leadership scenarios: real Cadet situations (teammates arguing, peer pressure, online bullying, a hidden injury, a first job, a rumor, a ride home with a driver who's been drinking, and more). You choose, see what happened and why, and write what you'd do next time — saved to your leadership log. No scores, no "wrong answer". |
| **💪 Train** | Your fitness history and goals, measured against your own last result. |
| **🤝 Serve** | Your service hours and what you learned, verified by your instructor; and **Explore Military Service** — for Cadets who want to learn what serving is like: military pay tables, how a military pay statement works, the Army jobs explorer, leave, moving with the military, and letters to family, service members and veterans. Information only; nothing signs you up or contacts a recruiter. |
| **📈 Progress** | Your growth over time — lessons, leadership, fitness, service and recognition — and a printable portfolio. |
| **💬 Ask** | Questions about anything in the library. Answers draw on sources stored on the device and name them. Your chats are private: your instructor can't read them. |

## For instructors

- **Instructor profile + Class PIN.** Class records open only with both.
- **Classes, platoons and squads**, each Cadet's unit and LET level.
- **Lessons:** write a lesson (objective, content, questions, vocabulary, reflection prompt, private notes) and assign
  it to everyone, to units, or to individual Cadets with a due date. See who's complete, in progress or not started,
  with scores and reflections. Cadets who join a unit later get its lessons automatically.
- **Starter lessons:** 12 ready-to-assign lessons (citizenship, leadership, values, communication, money, study
  skills), each built from a cited study card with four questions and a reflection — one click on Lessons or in Start
  class. Once added they're yours to edit.
- **Start class:** the instructor's Home plans today in named steps — Opening (a question on the projector), Learn
  (videos), Discuss (scenarios with a class vote), Engage (live questions), Assign (a lesson), Close (an exit question)
  — then runs them from one run sheet and ends on Progress (who's done).
- **Leadership scenarios:** use the twenty practice scenarios or write your own; read each Cadet's leadership log.
  Each has an **instructor debrief** (principles, what Cadets should notice, discussion questions, a follow-up) on
  your screen only — never on the projector or a Cadet's device.
- **Pilot results:** the Pilot screen shows the headline numbers (Cadets, active, assignments completed, Cadets who did a
  scenario, your usefulness rating, would you continue), asks "How useful was Cadet Foundry today?" when you finish class,
  and prints a one-page pilot summary. The numbers describe use, not proof of learning.
- **What Cadet Foundry is — and isn't:** in Settings and Me, plainly: a supplemental, instructor-controlled, offline-first
  tool; not official, not a replacement for your program's systems or records, not a grading authority.
- **Classroom mode:** project a scenario, Cadets vote A–D from their devices (anonymous — you see counts only), then
  reveal the discussion guidance.
- **Live pop quiz:** put any quiz question (or your own) on the projector as multiple choice or typed. Cadets answer
  once in 🧭 Lead; Cadet Foundry grades each answer. Results stay hidden until you reveal the answer, and you see how many
  got it right — never who.
- **Sample class:** see Cadet Foundry with eight made-up Cadets before setting anything up (welcome screen, or 🧪 on
  Home). It's a separate copy with its own throwaway folder; your data is never touched.
- **Pilot mode and End pilot:** online AI stays off, the Pilot screen shows what's stored on the device, and End
  pilot permanently removes the pilot's Cadets and class data (after you save the reports) while keeping your
  lessons and classes.
- **AI setting** for the whole device: **Off**, **Library only** (default — the AI may only explain what the library
  holds), or **Library + AI**.

## Privacy, in plain words

- Everything is stored on the instructor's laptop (or the USB drive Cadet Foundry runs from). Each profile has its own PIN,
  and its files are encrypted. If an operator turns on an online AI service, ordinary Ask questions go to it — without
  names, notes or earlier chats; anything about feeling unsafe never does (SECURITY.md).
- **The instructor sees class records only** — lessons, quizzes, exams, leadership scenarios, fitness and service.
  A Cadet's private check-ins, chats, notes and letters are encrypted with that Cadet's own key, and the instructor
  can't open them.
- Cadets can never see another Cadet's work or anything in the instructor's tools.
- No public leaderboards. Details for IT staff: [SECURITY.md](SECURITY.md).

## Set up the instructor's laptop

**Windows:** double-click `install-cadetfoundry.bat` (needs internet once). It installs Python if needed and offers the
optional parts (offline AI, offline voice, the library). **Linux / Raspberry Pi:** `sh install-cadetfoundry.sh`.

Run it:

```
python run.py              # this computer only (http://127.0.0.1:8780)
python run.py --lan        # Cadets on the classroom network can connect (a profile without a PIN can't be opened from them)
```

Needs Python 3.10+ and the `cryptography` package (installed by the setup script).

**First steps:** set the Class PIN in 👤 Me, then create your own profile and choose **An instructor**, and open
🎓 Instructor. Cadets create their own profile with a PIN the first time they open Cadet Foundry.

**Install as an app:** on a phone, "Add to Home Screen"; on a computer, "Install app" in the browser. Cadet Foundry
then opens full screen with its own icon.

## Run it from a USB drive

Put the whole system on a USB drive and run it on any Windows computer — nothing is installed there, and every
profile and class record stays on the drive (each profile still encrypted with its own PIN):

```
python tools/make_usb.py E:\                  # app + its own Python + the library (about 50 MB)
python tools/make_usb.py E:\ --with-ai        # also the offline AI, copied from this computer (adds about 1–2 GB)
```

On the drive, double-click **Start Cadet Foundry.bat** (this computer only) or **Start Classroom.bat** (Cadets
join from their phones on the same Wi-Fi — it opens a Join screen with a QR code). Keep the window open while you use it; close it or use Me → Quit Cadet Foundry
before unplugging. Run the command again to update the drive — the `Cadet Foundry Data` folder is never touched.
Linux / Mac: `sh start-cadet-foundry-usb.sh` (in the Mac and Linux folder) on the drive. `START HERE.html` on the drive explains which file does what.

## Demo box: Raspberry Pi with its own Wi-Fi

A Raspberry Pi (Zero 2 W or newer) can carry Cadet Foundry anywhere: its own Wi-Fi network, no internet, starts by itself
on power-up, and visitors can download the installer from it. On this computer:

```
python site/build.py                      # the installer that goes on the drive and the Pi
python tools/make_demo_kit.py E:\         # the USB to hand over + demo/ (Pi settings, printable QR card, Pi guide)
```

Then follow `demo/README-PI.txt` on the drive: copy the Cadet Foundry and demo folders to the Pi and run
`sudo sh ~/CadetFoundry/tools/pi_setup.sh`. Cadets join the "Cadet Foundry" Wi-Fi and open http://cadetfoundry.lan. A Pi Zero 2 W
serves about 10 Cadets at a time, with library answers only (no AI).

## Offline AI (optional)

```
ollama pull qwen2.5:3b
```

Without an AI model, everything except free-form AI explanations still works; answers come straight from the library.
Facts like pay, fitness score tables and job descriptions always come from Cadet Foundry's data, never from the AI.

## Library

Public-domain books: `python tools/fetch_books.py`. Official public documents: drop them into `library/` — see
[LIBRARY.md](LIBRARY.md).

## Data

Stored in `~/.cadetfoundry/` (or `$CADETFOUNDRY_DATA`). Back up a profile from 👤 Me → Download backup (sealed with a
password); restore it on another device the same way.
