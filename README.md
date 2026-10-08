# Vanguard

An offline AI study companion and logbook for U.S. Army Soldiers — from Basic Combat Training through AIT and the first duty station. Built on the ideas of [Vanguard](https://github.com/winklersllc2026-bit/Vanguard), stripped down to what a Soldier needs.

**Everything runs on the device, completely offline. No internet, no accounts, no tracking, no GPS.** See [SECURITY.md](SECURITY.md).

## What it does

| Tab | |
|---|---|
| **Ask** | Chat with Vanguard. Answers come from the official library and name their source (e.g. *AR 670-1*, *UCMJ*). If something isn't in the library, Vanguard says so. |
| **Study** | Flashcards and quizzes: creeds & values, general orders, ranks, phonetic alphabet, customs, drill, first aid, land navigation, UCMJ, uniforms, money, OPSEC, reports. Practice drills: land-nav grids, the 9-line MEDEVAC request (type it, or say it like on the radio), and the SALUTE and LACE reports. **Board prep**: an AGSU uniform checklist from DA PAM 670-1, a mock board you answer out loud or by typing, and a word-by-word Soldier's Creed check. **Pocket cards**: print the 9-line, SALUTE/LACE, phonetic alphabet, Soldier's Creed and Army Values on one page to cut out and carry. Questions you miss come back more often. |
| **Faith** | Optional. Public-domain scriptures from 12 texts across Christian (Protestant, Catholic, Orthodox), Jewish, Muslim, Latter-day Saint, Hindu, Buddhist and Taoist traditions. Look up passages, compare translations, search. |
| **Log** | A personal logbook (PT scores, qualifications, training, goals, notes), an **Army Fitness Test scorer** using the official score tables, and **Letters home**: address book, drafts from your notes, and an OPSEC check before you send. |
| **Me** | Profile, what Vanguard remembers, **PIN lock**, and **backup / restore**. |

Built-in care: **My people** (the Soldier's own battle buddy, chaplain, family — shown right under the crisis lines), a sleep tracker with FM 7-22 guidance, crisis support (988 then 1; text 838255), the DoD Safe Helpline, chaplain and Military OneSource — shown before anything else when someone is struggling. OPSEC reminders when someone starts typing unit movements, dates or locations.

**Family profiles**: a spouse or parent can have their own profile on the same device — Vanguard explains Army life in plain words, helps them support their Soldier and keep OPSEC, and hides the Soldier-only tools.

## Set up a device (one click)

**Windows:** double-click `install-vanguard.bat` (needs internet once). It installs Python if it's missing, then asks a few yes/no questions — the faith library, the official Army library, offline voice, the offline AI (Ollama + a small model) and a desktop shortcut — and finishes with a summary. **Linux / Raspberry Pi:** `sh install-vanguard.sh`. Unattended: add `--yes` (and `--no-ai`, `--no-voice`, `--model=1.5b` as needed).

## Run it

Needs Python 3.10+ (standard library only — nothing to install).

```bash
python run.py
```

Opens at http://127.0.0.1:8765. Options: `--no-browser` (kiosk / handheld), `--lan` (other devices on the same Wi-Fi can connect), `--port`.

### Offline AI
Install [Ollama](https://ollama.com) and a small model:

```bash
ollama pull qwen2.5:3b
```

`qwen2.5:3b` is the default and recommended model. Only on a very old or slow device, use `qwen2.5:1.5b` (`--model=1.5b`) — it's about twice as fast but mixes up facts more often. Vanguard picks the best installed model automatically. Without a model, the library, study tools, faith library and logbook still work.

Vanguard has no internet options in its screens. (Technical operators only: online AI can be enabled by editing the config file — see SECURITY.md.)

### Voice (optional)
Read-aloud uses the computer's own built-in voices (nothing leaves the device). To talk to Vanguard, install the offline speech recognizer once (needs internet one time, ~40 MB):

```bash
python tools/install_voice.py
```

Vanguard never uses the browser's built-in speech recognition — that sends audio to cloud servers.

### Faith library (optional)
Downloads the public-domain texts once (~32 MB), then works offline:

```bash
python tools/fetch_faith.py
```

### Official documents
Drop public Army publications (PDF/TXT) into `library/` — see [LIBRARY.md](LIBRARY.md). PDFs need `pip install pypdf`.

## Moving to a new device
**Me → Download backup** saves everything in one file; copy it by USB and use **Me → Restore** on the new device.

## Data
Everything the Soldier enters is stored in `~/.vanguard/` (or `$VANGUARD_DATA`) as plain files: profile, memory, logbook, study progress, recent chat, settings.

## Not an official Army product
Vanguard is a study aid. Standards and regulations change — confirm with your chain of command.
