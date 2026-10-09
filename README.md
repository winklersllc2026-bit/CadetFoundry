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
| **📘 Learn** | Your assignments from your instructor (lessons with vocabulary, questions and a reflection), study cards, quizzes and timed exams, and a library of public-domain books — the Declaration of Independence, the Constitution, the Bill of Rights, the Federalist Papers, American Military History (U.S. Army Center of Military History), and classics. Questions you miss come back more often. |
| **🧭 Lead** | Leadership scenarios: a real Cadet situation (two teammates arguing, a teammate who stopped participating, a deadline, peer pressure, criticism, delegation, a new Cadet left out, falling short). You choose, see what happened and why, and write what you'd do next time — saved to your leadership log. No scores, no "wrong answer". |
| **💪 Train** | Your fitness history and goals, measured against your own last result. |
| **🤝 Serve** | Service learning (being built), and **Explore Military Service** — for Cadets who want to learn what serving is like: military pay tables, how a military pay statement works, the Army jobs explorer, leave, moving with the military, and letters to family, service members and veterans. Information only; nothing signs you up or contacts a recruiter. |
| **📈 Progress** | Your growth over time (being built). |
| **💬 Ask** | Questions about anything in the library. Answers come from sources stored on the device and name them. |

## For instructors

- **Instructor profile + Instructor PIN.** Class records open only with both.
- **Classes, platoons and squads**, each Cadet's unit and LET level.
- **Lessons:** write a lesson (objective, content, questions, vocabulary, reflection prompt, private notes) and assign
  it to everyone, to units, or to individual Cadets with a due date. See who's complete, in progress or not started,
  with scores and reflections. Cadets who join a unit later get its lessons automatically.
- **Leadership scenarios:** use the eight practice scenarios or write your own; read each Cadet's leadership log.
- **Classroom mode:** project a scenario, Cadets vote A–D from their devices (anonymous — you see counts only), then
  reveal the discussion guidance.
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
