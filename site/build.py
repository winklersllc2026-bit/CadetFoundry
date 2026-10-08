"""
Build the private page for recruit.winklers-llc.com.

    python site/build.py            build site/dist (page + Windows installer + download zip)
    python site/build.py --deploy   build, then publish with wrangler
    python site/build.py --release  build, then publish the installer + zip as a GitHub release (needs gh)

The zip contains the app plus the installed faith library, so a test device
needs no internet after downloading it.
"""
from __future__ import annotations

import hashlib
import html
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DIST = SITE / "dist"
sys.path.insert(0, str(ROOT))
from recruit import __version__  # noqa: E402

REPO = "https://github.com/winklersllc2026-bit/Cursiv-Recruit"
LATEST = "Cursiv-Recruit-Setup-latest.exe"            # uploaded with every release (python site/build.py --release)
LATEST_URL = f"{REPO}/releases/latest/download/{LATEST}"

INCLUDE_DIRS = ["recruit", "web", "tools", "tests", "faith", "library", "books"]
INCLUDE_FILES = ["run.py", "start-recruit.bat", "start-recruit.sh", "install-recruit.bat", "install-recruit.sh", "README.md", "LIBRARY.md", "SECURITY.md"]

ROADMAP = [
    (True, "Ask: library-grounded chat that names its sources"),
    (True, "Study: 15 cards, 85+ quiz questions, missed questions come back more often"),
    (True, "Faith: 12 public-domain texts, 7 traditions — lookup, compare, search"),
    (True, "Logbook, profile and memory — all on the device"),
    (True, "Crisis support and OPSEC reminders"),
    (True, "Red-light night mode"),
    (True, "Letters home: address book, drafts from notes, OPSEC check, large print"),
    (True, "Backup / transfer to a new device (USB, offline)"),
    (True, "Security hardening: PIN lock, anti-CSRF / DNS-rebinding, strict CSP, attack tests"),
    (True, "Encryption at rest: each PIN-protected profile's files sealed with AES-256-GCM; key locked by the PIN (scrypt)"),
    (True, "Recovery codes: forgot your PIN? Your own one-time code sets a new one — no master key exists"),
    (True, "Encrypted backups (password of 10+ characters); a backup can never change device settings"),
    (True, "Crash-safe saving · made-up manual names flagged · letter OPSEC check catches dates like \"March 3rd\" and headcounts"),
    (True, "Purely offline — no internet options in the app"),
    (False, "Test on the Dell 7202 rugged tablet (qwen2.5:3b offline — check answer speed)"),
    (True, "Official library: UCMJ + 10 public Army publications downloaded automatically (AR 670-1, DA PAM 670-1, TC 7-21.13, FM 7-22, AR 600-20 …)"),
    (False, "Tune answers for small offline models (fuller explanations)"),
    (True, "Army jobs (MOS) explorer: 263 public job summaries from goarmy.com, searchable offline (\"cook\" finds 92G)"),
    (True, "Army Fitness Test scorer: official score tables (effective 1 Jun 2025), combat + general standards, saves to the logbook, \"how to improve\" from FM 7-22"),
    (True, "Report drills: 9-line MEDEVAC (ATP 4-02.2), SALUTE and LACE (TC 3-21.76) — practice scenarios, line-by-line check"),
    (True, "Say the 9-line out loud: offline radio-word recognition fills the form and checks it"),
    (False, "Test spoken 9-line with real voices on the tablet (grids/frequencies are the hard part)"),
    (False, "Radio prowords card (needs a current public source — ATP 6-02.53 (2025) dropped the table)"),
    (True, "Daily 10 with streaks · land-nav grid practice"),
    (True, "Daily check-in · tactical breathing coach · faith reading plans"),
    (True, "Leave tracker (2.5 days/month, 10 U.S.C. § 701) · budget planner"),
    (True, "Kiosk mode (start-recruit.bat --kiosk)"),
    (True, "Board prep: AGSU uniform check (DA PAM 670-1), mock board graded against the cards, Soldier's Creed recitation"),
    (True, "Board topics from AR 600-20 (Apr 2026): chain of command, NCO support channel, open door, discipline, EO, harassment, complaints"),
    (True, "Board topics: SHARP (AR 600-52, Feb 2025) and counseling (ATP 6-22.1, Feb 2024); FM 6-22 added to the library"),
    (True, "ASVAB, AFQT and line scores (GT and the other nine) from goarmy.com · GI Bill card (Post-9/11 and Montgomery) from va.gov"),
    (True, "Tuition Assistance and Credentialing Assistance card from AR 621-5 (March 2026)"),
    (True, "Heat, cold, carbon monoxide and sleep card from TC 4-02.3"),
    (True, "Official TSP summary in the library + TSP calculator using its exact BRS rules"),
    (True, "Pay estimate from the DFAS tables (basic pay by grade and years, BAS, your BAH) → budget and TSP"),
    (True, "2026 pay tables: enlisted, warrant, officer O-1 to O-10, prior-enlisted O-1E to O-3E and BAS (copied from dfas.mil → tools/pay_paste.py)"),
    (True, "LES decoder: all 78 blocks in DFAS's own words, active duty and Reserve/Guard, searchable"),
    (True, "Multiple Soldiers per device: separate profiles, each with its own PIN, fully isolated"),
    (True, "Offline voice: read-aloud with the computer's own voices; talk to Recruit with Vosk (tools/install_voice.py)"),
    (True, "Exam mode: timed multiple-choice tests by topic with a score history"),
    (True, "Library tamper check (SHA-256, signed list) and signed offline updates from a USB stick"),
    (False, "Publisher: run tools/sign.py keygen once and commit recruit/data/release_key.pub"),
    (False, "Idea (low priority): a Battle School-style strategy/decision game — see notes"),
    (True, "Tap any source under an answer to read the exact passage it came from"),
    (True, "Timed report drills with a personal best per Soldier"),
    (True, "Library freshness check: tools/fetch_library.py --check flags newer editions on armypubs"),
    (True, "Printable pocket cards: 9-line, SALUTE/LACE, phonetic alphabet, Soldier's Creed, Army Values (one page, black on white)"),
    (False, "General Orders: find a current public source (no longer in TC 7-21.13, 2025) before printing them"),
    (True, "Code of Conduct card from Executive Order 10631 (National Archives) and TC 7-21.13 (2025); Army song, anthem and bugle calls from AR 600-25 (2026) and TC 3-21.5"),
    (True, "📚 Books: Army history (CMH), the Declaration, Constitution, Bill of Rights and Federalist Papers, and classics (Art of War, On War, Meditations, Grant, Red Badge, Franklin, Lincoln) — offline reader with search and your place saved"),
    (True, "Trust in AI answers: 🤖 label on AI text, invented numbers flagged, AI can't forge the ✅ badge or make up links, library-only mode for locked-down devices"),
    (True, "AFT events card (no pull-ups) and checked answers for FM 7-22 vs the rifle manual (TC 3-22.9)"),
    (True, "First-run interview: a question is never saved as your name; read-aloud stops with a second tap"),
    (True, "Windows installer (Setup.exe, Inno Setup like Cursiv): desktop + Start menu icon (7.62 round), Add/Remove Programs, keeps data on update/uninstall"),
    (False, "Code-sign the installer so Windows doesn't show the 'Windows protected your PC' warning (needs a code-signing certificate)"),
    (True, "First-run interview: Recruit asks about the Soldier (rank, age, height/weight, MOS, post, goals), fills the Me tab, requires a PIN"),
    (True, "Conversations: separate chats in a sidebar on the left (slides in on a phone), named after their first question"),
    (True, "Answers: Army terms always given to the AI (no more made-up acronyms), 'How does this work?' explains Recruit, sources only when used"),
    (True, "One-step install: Python inside the installer, no console window; offline AI and voice install from Me → Add-ons with a progress bar"),
    (True, "Board packet: print your profile, AFT history, exam scores and logbook on one page"),
    (True, "First-run tour of the five tabs (Me tab → Take the tour to see it again)"),
    (True, "Device admin PIN: needed to install updates, separate from every profile PIN"),
    (False, "NCO Creed and Army song lyrics: army.mil and TRADOC Pam 600-4 not reachable — add once a public copy can be checked"),
    (True, "Sleep: weekly average, short nights and sleep debt from the check-ins, with FM 7-22 guidance"),
    (True, "My people: the Soldier's own support contacts, shown right under the crisis lines"),
    (True, "🔁 Simpler: re-say any answer in plain words, keeping every fact and source (needs the offline AI)"),
    (True, "PCS / first duty station checklist (Military OneSource guidance), report-date countdown, your own items"),
    (True, "Family profiles: spouses and parents get family-focused help, OPSEC and letters; Soldier-only tools hidden"),
    (False, "CAC / smart-card sign-in — left for Army IT to add (see SECURITY.md)"),
    (True, "Study cards from the manuals: field hygiene (ATP 4-25.12), weapons safety and range (TC 3-22.9); drill, courtesies, OPSEC, ranks, uniforms and UCMJ re-checked with paragraph numbers"),
    (True, "Backups keep a family member's profile type when restored on a new device"),
    (False, "Land nav card: marked unverified (TC 3-25.26 is CAC-only; no public manual covers it) — find a public source"),
    (True, "First aid card rebuilt from TC 3-21.76 (Sep 2025) ch. 15: TCCC phases and MARCH PAWS; old editions flagged wherever cited"),
    (True, "Checked answers: when a question matches a study-card quiz question, Recruit shows the verified answer first, word for word"),
    (True, "Offline AI sticks to the source: checked cards first, answer rules last, no loops; 3B model is now the default"),
    (True, "Speed: word index makes library search 175x faster (138 ms to under 1 ms); the AI loads at startup, so the first answer starts in about half a second"),
    (True, "Search the manuals: instant results without AI, exact page, edition date and a warning on old editions"),
    (True, "Where am I in Basic? week-by-week timeline (goarmy.com's four phases); rename profiles; large text and bigger buttons"),
    (True, "One-click setup: install-recruit.bat / .sh — Python, libraries, voice, offline AI, shortcut, self-check"),
]


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def make_zip(dest: Path) -> int:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in INCLUDE_FILES:
            if f.endswith(".bat"):                # Windows cmd needs CRLF, whatever machine builds the zip
                text = (ROOT / f).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
                z.writestr(f"Cursiv-Recruit/{f}", text)
            else:
                z.write(ROOT / f, f"Cursiv-Recruit/{f}")
        for d in INCLUDE_DIRS:
            for p in sorted((ROOT / d).rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    if d == "books" and p.suffix.lower() == ".pdf":
                        continue                  # the converted text ships; a saved source PDF stays on the build PC
                    z.write(p, f"Cursiv-Recruit/{p.relative_to(ROOT).as_posix()}")
    return dest.stat().st_size


def iscc() -> str | None:
    """Inno Setup's compiler (winget install -e --id JRSoftware.InnoSetup): on PATH or in its usual folders."""
    found = shutil.which("iscc")
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 os.environ.get("LOCALAPPDATA") and str(Path(os.environ["LOCALAPPDATA"]) / "Programs")):
        for compiler in (sorted(Path(base).glob("Inno Setup */ISCC.exe"), reverse=True) if base and not found else []):
            found = str(compiler)                 # Inno Setup 6 or 7, whichever winget installed
            break
    return found


# Python ships inside the Windows installer, so a Soldier's laptop needs no Python, no console and no setup step.
# The official embeddable build from python.org, pinned by its SHA-256.
PYTHON_EMBED = ("https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
                "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3")
PYTHON_PACKAGES = ["cryptography"]               # encryption of each Soldier's files (vault.py) and update signatures
PYTHON_UNUSED = ("sqlite3.dll", "_sqlite3.pyd", "_elementtree.pyd", "_lzma.pyd", "_bz2.pyd", "_decimal.pyd", "python.cat")


def bundle_python(app: Path) -> bool:
    """Put Python 3.12 (embeddable) + the cryptography package in app/python. Recruit then runs as
    python\\pythonw.exe run.py -- no console window."""
    import io
    import urllib.request
    url, sha = PYTHON_EMBED
    cached = SITE / ".cache" / url.rsplit("/", 1)[1]
    if not cached.exists() or hashlib.sha256(cached.read_bytes()).hexdigest() != sha:
        print("Downloading Python for the installer (once) …")
        cached.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        if hashlib.sha256(data).hexdigest() != sha:
            print("The Python download doesn't match its known fingerprint — not using it.")
            return False
        cached.write_bytes(data)
    py = app / "python"
    shutil.rmtree(py, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(cached.read_bytes())) as z:
        z.extractall(py)
    for name in PYTHON_UNUSED:
        (py / name).unlink(missing_ok=True)
    pth = next(py.glob("python3*._pth"))
    # The app folder (..) holds run.py and recruit/; Lib\site-packages holds cryptography and add-ons.
    pth.write_text(f"{pth.stem}.zip\r\n.\r\nLib\\site-packages\r\n..\r\nimport site\r\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-compile",
                        "--target", str(py / "Lib" / "site-packages"), "--only-binary=:all:", "--platform", "win_amd64",
                        "--python-version", "3.12", "--implementation", "cp", *PYTHON_PACKAGES],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("Couldn't add Python packages to the installer:\n" + (r.stdout + r.stderr)[-1500:])
        return False
    for junk in (py / "Lib" / "site-packages").rglob("__pycache__"):
        shutil.rmtree(junk, ignore_errors=True)
    return True


def make_installer(zip_path: Path, dest: Path) -> bool:
    """Cursiv-Recruit-Setup-<version>.exe (Inno Setup, like Cursiv's): copies the app and makes the icons.
    Setup (Python, libraries, AI) runs only from the checkbox on its last page."""
    exe = iscc()
    if not exe:
        print("No installer built: Inno Setup isn't installed (winget install -e --id JRSoftware.InnoSetup). The zip still works.")
        return False
    stage = SITE / ".stage"
    shutil.rmtree(stage, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(stage)
    shutil.rmtree(stage / "Cursiv-Recruit" / "tests", ignore_errors=True)    # not needed on a Soldier's device
    if not bundle_python(stage / "Cursiv-Recruit"):
        shutil.rmtree(stage, ignore_errors=True)
        print("No installer built.")
        return False
    nums = [int(x) for x in __version__.split(".")[:3] if x.isdigit()] + [0, 0, 0, 0]
    script = (SITE / "installer.iss").read_text(encoding="utf-8")
    for k, v in {"@VERSION@": __version__, "@VIVERSION@": ".".join(map(str, nums[:4])), "@OUTDIR@": str(dest.parent),
                 "@OUTNAME@": dest.stem, "@ICON@": str(ROOT / "web" / "icon.ico"),
                 "@STAGE@": str(stage / "Cursiv-Recruit")}.items():
        script = script.replace(k, v)
    iss = stage / "installer.iss"
    iss.write_text(script, encoding="utf-8-sig")
    r = subprocess.run([exe, "/Q", str(iss)], capture_output=True, text=True)
    shutil.rmtree(stage, ignore_errors=True)
    if r.returncode != 0 or not dest.exists():
        print("Installer build failed:\n" + (r.stdout + r.stderr)[-2000:])
        return False
    return True


def page(zip_name: str, size: int, commit: str, history: list[tuple[str, str, str]], sha: str = "",
         setup: tuple[str, int, str] | None = None) -> str:
    esc = html.escape
    rows = "".join(f"<li><span class='mono'>{esc(h)}</span> <span class='faint'>{esc(d)}</span><br>{esc(s)}</li>"
                   for h, d, s in history)
    road = "".join(f"<li class='{'done' if done else ''}'>{'✅' if done else '⬜'} {esc(t)}</li>" for done, t in ROADMAP)
    if setup:
        download = (f'<p><a class="btn" href="/{esc(setup[0])}">⬇ Download Cursiv Recruit {esc(__version__)} for Windows</a></p>'
                    f'<p class="faint">Or from GitHub (sign in first — the repo is private): <a href="{LATEST_URL}" style="color:var(--tan)">newest release</a></p>'
                    f'<p class="faint">{setup[1] / 2**20:.1f} MB installer. SHA-256: <span class="mono" style="word-break:break-all">{esc(setup[2])}</span></p>'
                    f'<p class="faint">Other ways: <a href="/{esc(zip_name)}" style="color:var(--tan)">zip of the same files</a> '
                    f'({size / 2**20:.1f} MB) for Linux, a USB stick, or a signed update.</p>')
    else:
        download = (f'<p><a class="btn" href="/{esc(zip_name)}">⬇ Download Cursiv Recruit {esc(__version__)}</a></p>'
                    f'<p class="faint">{size / 2**20:.1f} MB zip — the app plus the faith library.</p>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>Cursiv Recruit — builds</title><link rel="icon" href="/icon.svg" type="image/svg+xml">
<style>
:root {{ --bg:#0f120e; --card:#1a2017; --line:rgba(220,210,180,.12); --text:#ece6d6; --muted:#a7a08c; --tan:#cdb57c; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
.wrap {{ max-width:820px; margin:0 auto; padding:28px 16px 60px; }}
h1 {{ margin:0 0 4px; font-size:28px; }} h2 {{ font-size:19px; margin:0 0 10px; }}
.sub {{ color:var(--muted); margin:0 0 22px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; margin:0 0 14px; }}
.btn {{ display:inline-block; background:var(--tan); color:#1b1608; font-weight:700; text-decoration:none; padding:12px 18px; border-radius:10px; }}
.faint {{ color:var(--muted); font-size:14px; }} .mono {{ font-family:ui-monospace,Consolas,monospace; font-size:13px; color:var(--tan); }}
ol, ul {{ padding-left:20px; }} li {{ margin:6px 0; }} ul.road {{ list-style:none; padding:0; }} ul.road li.done {{ color:var(--muted); }}
code {{ font-family:ui-monospace,Consolas,monospace; background:rgba(0,0,0,.35); padding:2px 6px; border-radius:6px; font-size:14px; }}
</style></head><body><div class="wrap">
<h1>✦ Cursiv Recruit</h1>
<p class="sub">Private build page — not shared. Version <b>{esc(__version__)}</b> · built {time.strftime('%Y-%m-%d %H:%M')} · commit <span class="mono">{esc(commit or 'local')}</span></p>

<div class="card"><h2>Download</h2>
{download}
<p class="faint">Zip SHA-256: <span class="mono" style="word-break:break-all">{esc(sha)}</span><br>Check on Windows: <code>certutil -hashfile FILE SHA256</code></p></div>

<div class="card"><h2>Set up a device (Windows laptop or tablet)</h2><ol>
<li>Download and open <b>Cursiv-Recruit-Setup</b>. If Windows says <i>"Windows protected your PC"</i> (the installer isn't code-signed yet), click <b>More info → Run anyway</b>.</li>
<li>Click through the installer — no admin rights, no extra downloads. Python and the full library are inside. It puts a <b>Cursiv Recruit</b> icon on the desktop and in the Start menu, then starts Recruit.</li>
<li>Recruit asks a few questions about you and has you set a PIN. That's it — it works offline from here.</li>
<li>Optional: <b>Me → Add-ons</b> installs the offline AI (about 2 GB) or voice, with a progress bar. Each needs internet once. To close Recruit: <b>Me → Quit Recruit</b>.</li>
</ol><p class="faint">Updating: run the newer installer — profiles and logbooks are kept. Uninstall from Windows Settings → Apps; Soldiers' data in <code>%USERPROFILE%\\.cursiv-recruit</code> is kept unless you delete it.<br>
Zip instead: unzip, double-click <code>install-recruit.bat</code>. Linux / Raspberry Pi: unzip, <code>sh install-recruit.sh</code>, then <code>sh start-recruit.sh</code>.</p></div>

<div class="card"><h2>Roadmap</h2><ul class="road">{road}</ul></div>

<div class="card"><h2>Build history</h2><ul>{rows or '<li class="faint">No commits yet.</li>'}</ul></div>

<p class="faint">Code: github.com/winklersllc2026-bit/Cursiv-Recruit (private).</p>
</div></body></html>"""


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    for old in DIST.glob("*"):
        old.unlink()
    if not (ROOT / "faith" / "catalog.json").exists():
        print("Note: faith library not installed — run python tools/fetch_faith.py first to include it.")
    zip_name = f"Cursiv-Recruit-{__version__}.zip"
    size = make_zip(DIST / zip_name)
    commit = git("rev-parse", "--short", "HEAD")
    history = []
    for line in git("log", "-15", "--pretty=format:%h|%ad|%s", "--date=short").splitlines():
        h, d, s = (line.split("|", 2) + ["", ""])[:3]
        history.append((h, d, s))
    sha = hashlib.sha256((DIST / zip_name).read_bytes()).hexdigest()
    setup_name, setup = f"Cursiv-Recruit-Setup-{__version__}.exe", None
    if make_installer(DIST / zip_name, DIST / setup_name):
        data = (DIST / setup_name).read_bytes()
        setup = (setup_name, len(data), hashlib.sha256(data).hexdigest())
        print(f"Installer: {setup_name} ({len(data) / 2**20:.1f} MB)")
    for name in [zip_name] + ([setup_name] if setup else []):
        if (DIST / name).stat().st_size > 25 * 2**20:
            print(f"Warning: {name} is over 25 MB — Cloudflare won't host files that big.")
    shutil.copy(ROOT / "web" / "icon.svg", DIST / "icon.svg")
    (DIST / "index.html").write_text(page(zip_name, size, commit, history, sha, setup), encoding="utf-8")
    (DIST / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    print(f"Built {DIST}: index.html + {zip_name} ({size / 2**20:.1f} MB)")
    key = Path.home() / ".cursiv-recruit-release" / "release_key.pem"     # tools/sign.py keygen puts it here
    if key.exists():
        sys.path.insert(0, str(ROOT / "tools"))
        import sign
        print("Signed:", sign.sign_file(DIST / zip_name, sign.load_key(key)).name,
              "— copy it next to the zip on the USB stick for Me → Install an update")
    else:
        print("Not signed (no release key). Devices only install signed updates — see tools/sign.py.")
    if "--release" in sys.argv:                 # like Cursiv: the installer as a plain GitHub release download
        setup_exe = DIST / f"Cursiv-Recruit-Setup-{__version__}.exe"
        if setup_exe.exists():                    # a fixed name, so the page's button always gets the newest one
            shutil.copy(setup_exe, DIST / LATEST)
        files = [str(p) for p in sorted(DIST.glob("Cursiv-Recruit*")) if p.suffix in (".exe", ".zip", ".sig")]
        tag = f"v{__version__}"
        notes = "Windows: download Cursiv-Recruit-Setup and run it (More info -> Run anyway). Linux: the zip."
        r = subprocess.run(["gh", "release", "create", tag, *files, "--title", f"Cursiv Recruit {__version__}",
                            "--notes", notes, "--target", "main"], cwd=ROOT)
        if r.returncode != 0:                     # release already there: replace its files
            r = subprocess.run(["gh", "release", "upload", tag, *files, "--clobber"], cwd=ROOT)
        if r.returncode != 0:
            return r.returncode
        print(f"Released {tag}: {REPO}/releases/tag/{tag}\nThe page's download button: {LATEST_URL}")
    if "--deploy" in sys.argv:
        return subprocess.run("npx --yes wrangler deploy", cwd=SITE, shell=True).returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
