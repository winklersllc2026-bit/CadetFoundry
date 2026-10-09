# Vanguard

**Leadership. Learning. Character.** A learning and leadership platform designed to support JROTC instructors and
Cadets. Built by Winklers LLC.

Vanguard runs on the instructor's laptop. Cadets use it in a browser on school computers, tablets or phones on the
classroom network — no cloud, no accounts on outside services, no advertising, no tracking. The instructor stays in
control; Vanguard supplies the tools.

> Vanguard is designed to support JROTC instruction. It is **not** an official JROTC, Army or school product, does not
> replace your instructor or your program's curriculum, and makes no claim of endorsement.

## For Cadets

| Area | What's there today |
|---|---|
| **📘 Learn** | Your assignments from your instructor (lessons with vocabulary, questions and a reflection), 120+ study cards from U.S. government sources and Army manuals (leadership, citizenship and history, military knowledge, health and first aid, careers and money — each names its source), quizzes you type and Vanguard grades (Practice with choices, Challenge typed), timed exams, and a library of public-domain books — the Declaration of Independence, the Constitution, the Bill of Rights, the Federalist Papers, American Military History (U.S. Army Center of Military History), and classics. Questions you miss come back more often. |
| **🧭 Lead** | Live questions and classroom votes from your instructor, and 20 leadership scenarios: real Cadet situations (teammates arguing, peer pressure, online bullying, a hidden injury, a first job, a rumor, a ride home with a driver who's been drinking, and more). You choose, see what happened and why, and write what you'd do next time — saved to your leadership log. No scores, no "wrong answer". |
| **💪 Train** | Your fitness history and goals, measured against your own last result. |
| **🤝 Serve** | Your service hours and what you learned, verified by your instructor; and **Explore Military Service** — for Cadets who want to learn what serving is like: military pay tables, how a military pay statement works, the Army jobs explorer, leave, moving with the military, and letters to family, service members and veterans. Information only; nothing signs you up or contacts a recruiter. |
| **📈 Progress** | Your growth over time — lessons, leadership, fitness, service and recognition — and a printable portfolio. |
| **💬 Ask** | Questions about anything in the library. Answers come from sources stored on the device and name them. |

## For instructors

- **Instructor profile + Instructor PIN.** Class records open only with both.
- **Classes, platoons and squads**, each Cadet's unit and LET level.
- **Lessons:** write a lesson (objective, content, questions, vocabulary, reflection prompt, private notes) and assign
  it to everyone, to units, or to individual Cadets with a due date. See who's complete, in progress or not started,
  with scores and reflections. Cadets who join a unit later get its lessons automatically.
- **Leadership scenarios:** use the twenty practice scenarios or write your own; read each Cadet's leadership log.
- **Classroom mode:** project a scenario, Cadets vote A–D from their devices (anonymous — you see counts only), then
  reveal the discussion guidance.
- **Live pop quiz:** put any quiz question (or your own) on the projector as multiple choice or typed. Cadets answer
  once in 🧭 Lead; Vanguard grades each answer. Results stay hidden until you reveal the answer, and you see how many
  got it right — never who.
- **AI setting** for the whole device: **Off**, **Library only** (default — the AI may only explain what the library
  holds), or **Library + AI**.

## Privacy, in plain words

- Everything stays on the instructor's laptop. Each profile has its own PIN, and its files are encrypted.
- **The instructor sees class records only** — lessons, quizzes, exams, leadership scenarios, fitness and service.
  A Cadet's private check-ins, chats, notes and letters are encrypted with that Cadet's own key, and the instructor
  can't open them.
- Cadets can never see another Cadet's work or anything in the instructor's tools.
- No public leaderboards. Details for IT staff: [SECURITY.md](SECURITY.md).

## Set up the instructor's laptop

**Windows:** double-click `install-vanguard.bat` (needs internet once). It installs Python if needed and offers the
optional parts (offline AI, offline voice, the library). **Linux / Raspberry Pi:** `sh install-vanguard.sh`.

Run it:

```
python run.py              # this computer only (http://127.0.0.1:8780)
python run.py --lan        # Cadets on the classroom network can connect (requires a PIN on every profile)
```

Needs Python 3.10+ and the `cryptography` package (installed by the setup script).

**First steps:** set the Instructor PIN in 👤 Me, then create your own profile and choose **An instructor**, and open
🎓 Instructor. Cadets create their own profile with a PIN the first time they open Vanguard.

**Install as an app:** on a phone, "Add to Home Screen"; on a computer, "Install app" in the browser. Vanguard
then opens full screen with its own icon.

## Run it from a USB drive

Put the whole system on a USB drive and run it on any Windows computer — nothing is installed there, and every
profile and class record stays on the drive (each profile still encrypted with its own PIN):

```
python tools/make_usb.py E:\                  # app + its own Python + the library (about 50 MB)
python tools/make_usb.py E:\ --with-ai        # also the offline AI, copied from this computer (adds about 1–2 GB)
```

On the drive, double-click **Start Vanguard.bat** (this computer only) or **Start Vanguard (classroom).bat** (Cadets
connect over the classroom network). Keep the window open while you use it; close it or use Me → Quit Vanguard
before unplugging. Run the command again to update the drive — the `VanguardData` folder is never touched.
Linux / Mac: `sh start-vanguard-usb.sh` on the drive. Details: `README-USB.txt` on the drive.

## Demo box: Raspberry Pi with its own Wi-Fi

A Raspberry Pi (Zero 2 W or newer) can carry Vanguard anywhere: its own Wi-Fi network, no internet, starts by itself
on power-up, and visitors can download the installer from it. On this computer:

```
python site/build.py                      # the installer that goes on the drive and the Pi
python tools/make_demo_kit.py E:\         # the USB to hand over + demo/ (Pi settings, printable QR card, Pi guide)
```

Then follow `demo/README-PI.txt` on the drive: copy the Vanguard and demo folders to the Pi and run
`sudo sh ~/Vanguard/tools/pi_setup.sh`. Cadets join the "Vanguard" Wi-Fi and open http://vanguard.lan. A Pi Zero 2 W
serves about 10 Cadets at a time, with library answers only (no AI).

## Offline AI (optional)

```
ollama pull qwen2.5:3b
```

Without an AI model, everything except free-form AI explanations still works; answers come straight from the library.
Facts like pay, fitness score tables and job descriptions always come from Vanguard's data, never from the AI.

## Library

Public-domain books: `python tools/fetch_books.py`. Official public documents: drop them into `library/` — see
[LIBRARY.md](LIBRARY.md).

## Data

Stored in `~/.vanguard/` (or `$VANGUARD_DATA`). Back up a profile from 👤 Me → Download backup (sealed with a
password); restore it on another device the same way.
