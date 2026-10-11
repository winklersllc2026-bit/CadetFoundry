> **Next session: read ROADMAP.md (what's next) and ARCHITECTURE.md (how it fits together).** Earlier phase-by-phase
> handoff notes are in docs/history/ — historical only.

# Vanguard — notes for anyone (or any AI session) working on this repo

Learning and leadership platform for JROTC Cadets and instructors (see README.md, ROADMAP.md). Everything runs on the
device: Python 3.10+ standard library server (`run.py`, `vanguard/`), one-page web UI (`web/`), optional
Ollama model, optional Vosk voice. **No internet at runtime** — tools in `tools/` download things once on a
setup machine.

## Ground rules
- **Every fact needs a source.** Study cards cite the publication *and* paragraph/table/figure
  (`source:` line). Check wording against the actual text in `library/` (or an official page) before
  writing it. If no current public source exists, leave it out and add a roadmap item — never fill gaps
  from memory. CAC-only publications (`/epubs/DR_pubs/DR_c/` on armypubs) are never used.
- **Safety first.** Crisis messages (`vanguard/safety.py`) always get the crisis lines and the Cadet's own
  people, never library text, even with no AI model. OPSEC reminders stay.
- **Offline and private.** No network calls from `vanguard/` at runtime (except the optional online AI a
  technical operator enables). Cadet data lives in `~/.vanguard` (or `$VANGUARD_DATA`), encrypted
  per profile when a PIN is set. New per-profile files must be added to `vanguard/backup.py`.

## Study cards (`vanguard/cards/*.md`)
```
---
title: …
topic: …                       (topics group cards in Study; "Board: Leadership & Programs" feeds the mock board)
source: AR 600-20, Army Command Policy (15 April 2026), paras 2-1, 2-19
---
Body in Markdown (lists, **bold**; no tables — the renderer doesn't draw them).

## Quiz
Q: question | A: answer as verified | ALSO: another way Cadets ask it; another way
```
- Quiz answers are shown word for word as "checked answers". Only add an `ALSO:` phrasing if the answer
  fits it exactly ("what happens if I go AWOL" → "Article 86" does NOT fit).
- A card with several sources separates them with `;` — checked answers then name all of them.

## Library (`library/`, not in git)
`python tools/fetch_library.py` downloads public manuals (armypubs `DR_a` only), goarmy.com and va.gov
pages, converts PDFs to text once, records editions (`manifest.json`) and SHA-256 fingerprints
(`integrity.json`). Add new publications to `ARMY_PUBS` there.

## Books (`books/`, not in git)
`python tools/fetch_books.py` downloads public-domain books (catalog in `vanguard/books.py`; each book's chapter-heading
pattern lives there). Books are for reading in Study → 📚 Books — **never** add them to `library/` or to Ask's
search: Ask answers only from official sources. A Cadet's place in each book is `books.json` (per profile, in backups).

## Tests — run before every push
```
python -m unittest discover tests
```
`tests/test_security.py::test_0_every_route…` calls every `/api` route on a live server — it catches a
route that crashes (e.g. a module used but not imported). For UI changes, also drive the page in a
browser (Playwright/Chromium) and look at a screenshot, including red-light (night) mode.

## Working with two sessions
Two AI sessions have worked on this repo at once. Before starting: `git pull` on `main` (or merge
`origin/main` into your branch). Keep commits small and described; push when tests pass. Don't rewrite
history. If both changed the same file, merge — don't overwrite.

## Releases
**Release signing key (Ed25519): created by the owner on 2026-10-11.** The public key is
`vanguard/data/release_key.pub` (committed); the private key is on the owner's build PC only
(`~/.vanguard-release/release_key.pem` — never in git, a zip, a device or chat output). `site/build.py` signs the
release zip with it automatically. A session must never make, move, read out or replace the key on the owner's behalf;
replacing it locks out every device with the old public key.

Bump `vanguard/__init__.py` `__version__` for every release (signed updates refuse equal/older versions).
`python site/build.py` builds `site/dist/` (page + zip, signed if `~/.vanguard-release/release_key.pem`
exists — see `tools/sign.py`); `--deploy` publishes with wrangler (needs a Cloudflare login). `--release` publishes the installer and zip as a GitHub release (needs the `gh` CLI, logged in).
The Windows installer (`Vanguard-Setup-<version>.exe`, from `site/installer.iss`) is built with Inno Setup 6
when it's installed (`winget install -e --id JRSoftware.InnoSetup`); without it only the zip is built. The installer bundles
Python (official embeddable build, pinned SHA-256 in `site/build.py`, plus `cryptography`) and starts Vanguard with
`pythonw.exe` — no console. It must only copy files and make shortcuts: never run scripts mid-install (Defender's ML
flagged that as Trojan:Win32/Wacatac.B!ml). Optional extras install from inside the app (`vanguard/addons.py`).
