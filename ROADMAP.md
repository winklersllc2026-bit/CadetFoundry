# Vanguard roadmap

Current version: **0.2.2** (2026-10-11). Downloads: the public Vanguard-releases repo on GitHub; page: vanguard.winklers-llc.com (public).

## Where it stands

**0.2 — every branch, and simpler for everyone:** Learn covers the Army, Navy, Air Force, Marine Corps and Space Force
(each card checked against an official page) · the instructor picks their program and labels follow it (LET / NS /
LE / Year) · cadet rank and billet · first-run setup wizard · Join screen with a QR code and join codes per class or
platoon · 30-second Cadet sign-up · Home screen and 4-tab bar · instructor menu (Today, Class, Lessons, Present,
Reports, Settings) · jobs explorer for every service from official recruiting sites (Air Force jobs show published
ASVAB minimums) · ASVAB practice for the four AFQT subtests with exact scoring · Start Classroom launchers.

Built before 0.2 and still here: roles and the Class PIN · classes, platoons and squads · lessons and assignments ·
quizzes typed and graded by Vanguard · exams · 20 leadership scenarios with a classroom vote · live in-class pop
quiz · Train · Serve with instructor verification · Progress and printable portfolio · instructor dashboard and CSV
report · program backup · pilot tools · Windows installer · USB drive (with optional offline AI) · website.

**0.2.1:** branch cards up toward the Army set: Navy 21, Air Force 21, Space Force 20, Marine Corps 15 (drill,
ceremonies, ranks, fitness, history, organization, joining), each checked against an official source · official
military videos in Learn (DVIDS public-domain videos play offline once saved with tools/fetch_videos.py; YouTube
entries link to each service's own channel) · the desktop icon recovers when its port is held by a broken copy.

**0.2.2 — Class day:** the instructor's Home is a setup checklist (make a class, put Cadets in it, open class to
phones) and a big Start class: pick the class and today's lesson, scenarios, live questions and videos, then run them
from one run sheet · Start Classroom opens even if a profile has no PIN (phones can't open that profile) · the Join
screen shows join codes on the instructor's computer before sign-in · a join QR code in the Start Classroom window ·
USB drives get a "Make more flash drives" folder for clean Cadet drives · public website with real screenshots.

## Next: Cadet drives that sync

A Cadet studies at home on their own drive; at school their class records go to the instructor -- over the classroom
network when it allows, or by plugging the drive into the instructor's computer (no clicks). Records travel encrypted
to the Class PIN; private notes never leave the drive; new lessons come back to the drive.

## Next: branch content up to the depth of the Army set

The Army set has 46 cards. Navy, Air Force and Space Force are past 20 and the Marine Corps has 15; more official
sources (Enlisted Force Structure, Air Force Symbol, SPFMAN 36-2905, Marine Corps manuals) will bring them closer.

## Before the first classroom pilot (owner)

1. ~~Vanguard's release-signing key~~ — done 2026-10-11: `vanguard/data/release_key.pub` is committed and releases
   sign themselves. Keep `~/.vanguard-release/release_key.pem` backed up somewhere safe, off every school device.
2. **Code-sign the Windows installer** so Windows doesn't show "Windows protected your PC" (needs a code-signing
   certificate in the company's name; then sign `Vanguard-Setup-*.exe` in `site/build.py`).
3. ~~Raspberry Pi demo box~~ — no Pi now (2026-10-10); the instructor's laptop is the first device. The Pi tools stay in the repo.
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
