# Vanguard roadmap

Current version: **0.1.4** (2026-10-09). Released on GitHub (private repo) and vanguard.winklers-llc.com (password).

## Where it stands

Built and tested (128 automated tests, including a full class day end to end):
roles and the Instructor PIN · classes, platoons and squads · lessons and assignments · 120+ sourced study cards ·
quizzes typed and graded by Vanguard · exams · 20 leadership scenarios with a classroom vote (several in a row) ·
live in-class pop quiz · Train · Serve with instructor verification · Progress and printable portfolio ·
instructor dashboard and CSV report · program backup · pilot tools · Windows installer · USB drive (with optional
offline AI) · Raspberry Pi demo box · website.

## Before the first classroom pilot (owner)

1. **Vanguard's release-signing key.** The key the fork shipped with belonged to the earlier product and was
   removed in 0.1.4. On the build PC: `python tools/sign.py keygen`, keep `~/.vanguard-release/release_key.pem`
   safe (and backed up), commit `vanguard/data/release_key.pub`, release a new version. Until then devices refuse
   signed updates.
2. **Code-sign the Windows installer** so Windows doesn't show "Windows protected your PC" (needs a code-signing
   certificate in the company's name; then sign `Vanguard-Setup-*.exe` in `site/build.py`).
3. **Run the Raspberry Pi demo box once on real hardware** (`tools/pi_setup.sh` has only been checked here).
4. **Walk the pilot flow once by hand** on the classroom setup you'll use (below).

## Next work

**Classroom security** (see SECURITY.md → "The classroom network")
- [x] LAN threat model written down; a dedicated hotspot is the recommended pilot setup.
- [x] On the classroom network, other devices see shortened profile names on the sign-in screen.
- [x] A "classroom network" notice on the instructor's screen while `--lan` is on.
- [ ] HTTPS on the classroom network (needs a certificate the Cadets' devices trust — investigate a per-device
      certificate the instructor installs once, or the Pi box serving a known name).

**Pilot polish — one flow that works beautifully**
Instructor installs → creates instructor profile → creates class → Cadets join → instructor creates lesson →
Cadets complete it → instructor runs a scenario → class votes → instructor sees results → Cadets see progress →
instructor exports the report. Covered end to end by `tests/test_class_day.py`; walk it by hand before a pilot.

**Content** — yearly refresh in CONTENT_REFRESH.md. Open owner decision: low-fat (FM 7-22) vs full-fat (2025–2030
Dietary Guidelines) dairy on `nutrition_hydration`.

**Later** — Linux/Mac installer, more scenarios and lessons from instructors' own material, Spanish.
