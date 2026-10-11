"""
Build the private page for vanguard.winklers-llc.com.

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
from vanguard import __version__  # noqa: E402

REPO = "https://github.com/winklersllc2026-bit/Vanguard"
LATEST = "Vanguard-Setup-latest.exe"            # uploaded with every release (python site/build.py --release)
LATEST_URL = f"{REPO}/releases/latest/download/{LATEST}"

INCLUDE_DIRS = ["vanguard", "web", "tools", "tests", "faith", "library", "books"]
INCLUDE_FILES = ["run.py", "start-vanguard.bat", "start-vanguard.sh", "start-classroom.bat", "start-classroom.sh", "install-vanguard.bat", "install-vanguard.sh", "README.md", "LIBRARY.md", "SECURITY.md"]

ROADMAP = [
    (True, "0.2: every branch — Army, Navy, Air Force, Marine Corps and Space Force sections in Learn; your program's labels"),
    (True, "0.2: simple setup — first-run wizard, Join screen with a QR code, join codes per class or platoon, 30-second sign-up"),
    (True, "0.2: Home screen and a 4-tab bar (Home, Learn, Lead, Me); an instructor menu (Today, Class, Lessons, Present, Reports, Settings)"),
    (True, "0.2: military jobs in every service from official sites; ASVAB practice with exact scoring"),
    (True, "0.2.1: deeper Navy, Air Force, Space Force and Marine Corps cards; official military videos (offline once saved)"),
    (True, "Roles: Cadet, guardian and instructor profiles; Class PIN; class records only for the instructor"),
    (True, "Classes, platoons and squads; lessons assigned to everyone, units or Cadets (late joiners get them once)"),
    (True, "Learn: 150+ study cards from official U.S. government and military sources, each citing its source"),
    (True, "Quizzes typed and graded by Vanguard — Practice (multiple choice) and Challenge (typed); never self-reported"),
    (True, "Leadership scenarios (20) with a leadership log; classroom vote on the projector"),
    (True, "Live in-class pop quiz: one question on the projector, Cadets answer on their devices, counts only"),
    (True, "Train: fitness events and goals measured against yourself"),
    (True, "Serve: service hours with instructor verification; Explore Military Service (opt-in, information only)"),
    (True, "Progress: growth over time, achievements, recognition, printable portfolio"),
    (True, "Instructor dashboard, class report CSV, program backup and restore, quiz editor, assigned pop quizzes"),
    (True, "Pilot tools: setup, weekly snapshots, anonymous Cadet survey, instructor feedback, pilot report"),
    (True, "Installable app on phones and computers; works offline on the classroom network"),
    (False, "Publisher: run tools/sign.py keygen once and commit vanguard/data/release_key.pub"),
    (False, "Code-sign the Windows installer (needs a code-signing certificate)"),
    (False, "Navy, Air Force, Marine Corps and Space Force cards brought up to the depth of the Army set"),
    (False, "First classroom pilot"),
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
                z.writestr(f"Vanguard/{f}", text)
            elif f.endswith(".sh"):               # and Linux / Raspberry Pi needs LF
                z.writestr(f"Vanguard/{f}", (ROOT / f).read_bytes().replace(b"\r\n", b"\n"))
            else:
                z.write(ROOT / f, f"Vanguard/{f}")
        for d in INCLUDE_DIRS:
            for p in sorted((ROOT / d).rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    if d == "books" and p.suffix.lower() == ".pdf":
                        continue                  # the converted text ships; a saved source PDF stays on the build PC
                    if p.suffix == ".sh":             # shell scripts run on Linux / a Pi: LF, whatever the build PC did
                        z.writestr(f"Vanguard/{p.relative_to(ROOT).as_posix()}", p.read_bytes().replace(b"\r\n", b"\n"))
                        continue
                    z.write(p, f"Vanguard/{p.relative_to(ROOT).as_posix()}")
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


# Python ships inside the Windows installer, so the instructor's laptop needs no Python, no console and no setup step.
# The official embeddable build from python.org, pinned by its SHA-256.
PYTHON_EMBED = ("https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
                "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3")
PYTHON_PACKAGES = ["cryptography"]               # encryption of each profile's files (vault.py) and update signatures
PYTHON_UNUSED = ("sqlite3.dll", "_sqlite3.pyd", "_elementtree.pyd", "_lzma.pyd", "_bz2.pyd", "_decimal.pyd", "python.cat")


def bundle_python(app: Path) -> bool:
    """Put Python 3.12 (embeddable) + the cryptography package in app/python. Vanguard then runs as
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
    # The app folder (..) holds run.py and vanguard/; Lib\site-packages holds cryptography and add-ons.
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
    """Vanguard-Setup-<version>.exe (Inno Setup, like Vanguard's): copies the app and makes the icons.
    Setup (Python, libraries, AI) runs only from the checkbox on its last page."""
    exe = iscc()
    if not exe:
        print("No installer built: Inno Setup isn't installed (winget install -e --id JRSoftware.InnoSetup). The zip still works.")
        return False
    stage = SITE / ".stage"
    shutil.rmtree(stage, ignore_errors=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(stage)
    shutil.rmtree(stage / "Vanguard" / "tests", ignore_errors=True)    # not needed on the instructor's laptop
    if not bundle_python(stage / "Vanguard"):
        shutil.rmtree(stage, ignore_errors=True)
        print("No installer built.")
        return False
    nums = [int(x) for x in __version__.split(".")[:3] if x.isdigit()] + [0, 0, 0, 0]
    script = (SITE / "installer.iss").read_text(encoding="utf-8")
    for k, v in {"@VERSION@": __version__, "@VIVERSION@": ".".join(map(str, nums[:4])), "@OUTDIR@": str(dest.parent),
                 "@OUTNAME@": dest.stem, "@ICON@": str(ROOT / "web" / "icon.ico"),
                 "@STAGE@": str(stage / "Vanguard")}.items():
        script = script.replace(k, v)
    iss = stage / "installer.iss"
    iss.write_text(script, encoding="utf-8-sig")
    r = subprocess.run([exe, "/Q", str(iss)], capture_output=True, text=True)
    shutil.rmtree(stage, ignore_errors=True)
    if r.returncode != 0 or not dest.exists():
        print("Installer build failed:\n" + (r.stdout + r.stderr)[-2000:])
        return False
    return True


STYLE = """
:root { --bg:#0f120e; --card:#1a2017; --line:rgba(220,210,180,.12); --text:#ece6d6; --muted:#a7a08c; --tan:#cdb57c; }
* { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--text); font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
.wrap { max-width:820px; margin:0 auto; padding:28px 16px 60px; }
h1 { margin:0 0 4px; font-size:28px; } h2 { font-size:19px; margin:0 0 10px; }
.sub { color:var(--muted); margin:0 0 22px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; margin:0 0 14px; }
.btn { display:inline-block; background:var(--tan); color:#1b1608; font-weight:700; text-decoration:none; padding:12px 18px; border-radius:10px; }
.faint { color:var(--muted); font-size:14px; } .mono { font-family:ui-monospace,Consolas,monospace; font-size:13px; color:var(--tan); }
ol, ul { padding-left:20px; } li { margin:6px 0; } ul.road { list-style:none; padding:0; } ul.road li.done { color:var(--muted); }
code { font-family:ui-monospace,Consolas,monospace; background:rgba(0,0,0,.35); padding:2px 6px; border-radius:6px; font-size:14px; }
nav { display:flex; gap:16px; flex-wrap:wrap; margin:0 0 18px; } nav a { color:var(--tan); text-decoration:none; }
nav a.on { color:var(--text); font-weight:700; }
"""

DISCLAIMER = ("Vanguard is designed to support JROTC instruction. It is not an official JROTC, Army or school product, "
              "does not replace your instructor or your program's curriculum, and makes no claim of endorsement.")


def shell(title: str, here: str, body: str) -> str:
    links = "".join(f'<a href="{href}" class="{"on" if key == here else ""}">{label}</a>'
                    for key, href, label in (("home", "/", "Home"), ("pilot", "/pilot", "Pilot"),
                                             ("security", "/security", "Security")))
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>{html.escape(title)}</title><link rel="icon" href="/icon.svg" type="image/svg+xml">
<style>{STYLE}</style></head><body><div class="wrap">
<h1>✦ Vanguard</h1><nav>{links}</nav>
{body}
<p class="faint">{html.escape(DISCLAIMER)}<br>Built by Winklers LLC.</p>
</div></body></html>"""


def page(zip_name: str, size: int, commit: str, history: list[tuple[str, str, str]], sha: str = "",
         setup: tuple[str, int, str] | None = None) -> str:
    esc = html.escape
    rows = "".join(f"<li><span class='mono'>{esc(h)}</span> <span class='faint'>{esc(d)}</span><br>{esc(s)}</li>"
                   for h, d, s in history)
    road = "".join(f"<li class='{'done' if done else ''}'>{'✅' if done else '⬜'} {esc(t)}</li>" for done, t in ROADMAP)
    if setup:
        download = (f'<p><a class="btn" href="/{esc(setup[0])}">⬇ Download Vanguard {esc(__version__)} for Windows</a></p>'
                    f'<p class="faint">Or from GitHub (sign in first — the repo is private): <a href="{LATEST_URL}" style="color:var(--tan)">newest release</a></p>'
                    f'<p class="faint">{setup[1] / 2**20:.1f} MB installer. SHA-256: <span class="mono" style="word-break:break-all">{esc(setup[2])}</span></p>'
                    f'<p class="faint">Other ways: <a href="/{esc(zip_name)}" style="color:var(--tan)">zip of the same files</a> '
                    f'({size / 2**20:.1f} MB) for Linux, a USB stick, or a signed update.</p>')
    else:
        download = (f'<p><a class="btn" href="/{esc(zip_name)}">⬇ Download Vanguard {esc(__version__)}</a></p>'
                    f'<p class="faint">{size / 2**20:.1f} MB zip.</p>')
    body = f"""<p class="sub"><b>Leadership. Learning. Character.</b> A learning and leadership platform designed to support
JROTC instructors and Cadets. Version <b>{esc(__version__)}</b> · built {time.strftime('%Y-%m-%d %H:%M')} · commit <span class="mono">{esc(commit or 'local')}</span></p>

<div class="card"><h2>What it is</h2>
<p>Vanguard runs on the <b>instructor's laptop</b>. Cadets use it in a browser on school computers, tablets or phones on the
classroom network — no cloud, no outside accounts, no advertising, no tracking. The instructor stays in control.</p>
<ul>
<li><b>🏠 Home</b> — what's due, the Daily 10, a live question from the instructor, and progress at a glance.</li>
<li><b>📘 Learn</b> — every branch of service (Army, Navy, Air Force, Marine Corps, Space Force) plus shared subjects; study cards from official sources (every card names its source), quizzes Cadets type and Vanguard grades, timed exams, ASVAB practice, and a jobs explorer for every service.</li>
<li><b>🧭 Lead</b> — leadership scenarios, a leadership log, the classroom vote and the live pop quiz.</li>
<li><b>💪 Train</b> — fitness measured against yourself. <b>🤝 Serve</b> — service hours your instructor verifies.</li>
<li><b>📈 Progress</b> — growth over time and a printable portfolio.</li>
<li><b>🎓 Instructor</b> — classes and units, lessons, a dashboard, class reports, a quiz editor and pilot tools.</li>
</ul></div>

<div class="card"><h2>Download</h2>
{download}
<p class="faint">Zip SHA-256: <span class="mono" style="word-break:break-all">{esc(sha)}</span><br>Check on Windows: <code>certutil -hashfile FILE SHA256</code></p></div>

<div class="card"><h2>Set up the instructor's laptop</h2><ol>
<li>Download and open <b>Vanguard-Setup</b>. If Windows says <i>"Windows protected your PC"</i> (the installer isn't code-signed yet), click <b>More info → Run anyway</b>.</li>
<li>Click through the installer — no admin rights needed. It puts a <b>Vanguard</b> icon on the desktop and in the Start menu.</li>
<li>Open Vanguard and choose <b>I'm the instructor — set up this class</b>: pick your program, a <b>Class PIN</b>, your name and your own PIN.</li>
<li>In <b>🎓 Instructor → Class</b>, add your classes or platoons. Each gets a <b>join code</b> that places Cadets in it.</li>
<li>For the classroom, open <b>Vanguard Classroom</b> (or <code>start-classroom</code>). It shows a Join screen with a QR code; Cadets scan it and pick a name and a PIN.</li>
</ol><p class="faint">Updating: run the newer installer — profiles and class records are kept. Data lives in <code>%USERPROFILE%\\.vanguard</code>.<br>
Zip instead: unzip, double-click <code>install-vanguard.bat</code>. Linux / Raspberry Pi: <code>sh install-vanguard.sh</code>, then <code>sh start-vanguard.sh</code>.</p></div>

<div class="card"><h2>Roadmap</h2><ul class="road">{road}</ul></div>

<div class="card"><h2>Build history</h2><ul>{rows or '<li class="faint">No commits yet.</li>'}</ul></div>"""
    return shell("Vanguard", "home", body)


def pilot_page() -> str:
    body = """<div class="card"><h2>Run a pilot</h2>
<p>A pilot shows whether Vanguard helps <i>your</i> program — measured from real class records, not guesses.</p><ol>
<li><b>Set it up</b> (🎓 Instructor → Pilot): school, instructor, start and end dates, how many Cadets, and which results to measure — engagement, lesson completion, academics, leadership scenarios, fitness, service, instructor workload, feedback.</li>
<li><b>Take a baseline snapshot</b> on day one, then about once a week. The report shows the change over the pilot.</li>
<li><b>Teach as usual</b> — assign lessons, run scenarios and live questions, record fitness and service.</li>
<li><b>Open the Cadet survey</b> near the end: five short questions. It is anonymous — answers are stored without any name or ID.</li>
<li><b>Add your own feedback</b>: satisfaction, minutes saved each week, and whether you'd use it next semester.</li>
<li><b>Print the pilot report.</b> Every number comes from real records, and what Vanguard can't measure is said plainly.</li>
</ol></div>
<div class="card"><h2>What a school needs</h2><ul>
<li>One Windows laptop (or Linux / Raspberry Pi) for the instructor. No server, no cloud account, no subscription.</li>
<li>Cadets' devices on the same classroom network, with a web browser.</li>
<li>Optional: the offline AI (about 2 GB) for explanations. Everything else works without it.</li>
</ul></div>
<div class="card"><h2>Interested?</h2><p>Contact Winklers LLC to talk about a pilot.</p></div>"""
    return shell("Vanguard — Pilot", "pilot", body)


def security_page() -> str:
    body = """<div class="card"><h2>Privacy and security, in plain words</h2><ul>
<li><b>Everything stays on the instructor's laptop.</b> No cloud, no outside accounts, no tracking, no advertising.</li>
<li><b>Each profile has its own PIN, and its files are encrypted</b> (AES-256-GCM, with the key locked by the PIN).</li>
<li><b>The instructor sees class records only</b> — lessons, quizzes, exams, leadership scenarios, fitness and service. A Cadet's private check-ins, chats, notes and letters are sealed with that Cadet's own key; the instructor can't open them.</li>
<li><b>Two factors for class records:</b> the instructor's own profile PIN and the Instructor PIN.</li>
<li><b>Cadets can never see another Cadet's work</b> or anything in the instructor's tools. No public leaderboards.</li>
<li><b>Anonymous surveys:</b> pilot survey answers are stored without any name or ID.</li>
<li><b>Quizzes can't be faked:</b> Cadets type answers and Vanguard grades them; the answer is never sent to the screen early.</li>
<li><b>Minimal data about minors:</b> no rank, body data or sex in Cadet profiles.</li>
<li><b>Classroom network only:</b> network mode refuses to start unless every profile has a PIN; requests from other websites are refused.</li>
<li><b>Signed updates:</b> a device installs an update only if it's signed with the publisher's key and newer than what's installed.</li>
<li><b>Forgotten PIN:</b> each Cadet gets a one-time recovery code. There is no master key for private files.</li>
</ul></div>
<div class="card"><h2>For school IT</h2><p>Turn on full-disk encryption (BitLocker on Windows), keep the operating system updated, and use a standard account for daily use. The full technical details — threats, protections and the automated attack tests — are in <code>SECURITY.md</code> with the code.</p></div>"""
    return shell("Vanguard — Security", "security", body)


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    for old in DIST.glob("*"):
        old.unlink()
    if not (ROOT / "faith" / "catalog.json").exists():
        print("Note: faith library not installed — run python tools/fetch_faith.py first to include it.")
    zip_name = f"Vanguard-{__version__}.zip"
    size = make_zip(DIST / zip_name)
    commit = git("rev-parse", "--short", "HEAD")
    history = []
    for line in git("log", "-15", "--pretty=format:%h|%ad|%s", "--date=short").splitlines():
        h, d, s = (line.split("|", 2) + ["", ""])[:3]
        history.append((h, d, s))
    sha = hashlib.sha256((DIST / zip_name).read_bytes()).hexdigest()
    setup_name, setup = f"Vanguard-Setup-{__version__}.exe", None
    if make_installer(DIST / zip_name, DIST / setup_name):
        data = (DIST / setup_name).read_bytes()
        setup = (setup_name, len(data), hashlib.sha256(data).hexdigest())
        print(f"Installer: {setup_name} ({len(data) / 2**20:.1f} MB)")
    for name in [zip_name] + ([setup_name] if setup else []):
        if (DIST / name).stat().st_size > 25 * 2**20:
            print(f"Warning: {name} is over 25 MB — Cloudflare won't host files that big.")
    shutil.copy(ROOT / "web" / "icon.svg", DIST / "icon.svg")
    (DIST / "index.html").write_text(page(zip_name, size, commit, history, sha, setup), encoding="utf-8")
    (DIST / "pilot.html").write_text(pilot_page(), encoding="utf-8")
    (DIST / "security.html").write_text(security_page(), encoding="utf-8")
    (DIST / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    print(f"Built {DIST}: index.html + {zip_name} ({size / 2**20:.1f} MB)")
    key = Path.home() / ".vanguard-release" / "release_key.pem"     # tools/sign.py keygen puts it here
    if key.exists():
        sys.path.insert(0, str(ROOT / "tools"))
        import sign
        print("Signed:", sign.sign_file(DIST / zip_name, sign.load_key(key)).name,
              "— copy it next to the zip on the USB stick for Me → Install an update")
    else:
        print("Not signed (no release key). Devices only install signed updates — see tools/sign.py.")
    if "--release" in sys.argv:                 # like Vanguard: the installer as a plain GitHub release download
        setup_exe = DIST / f"Vanguard-Setup-{__version__}.exe"
        if setup_exe.exists():                    # a fixed name, so the page's button always gets the newest one
            shutil.copy(setup_exe, DIST / LATEST)
        files = [str(p) for p in sorted(DIST.glob("Vanguard*")) if p.suffix in (".exe", ".zip", ".sig")]
        tag = f"v{__version__}"
        notes = "Windows: download Vanguard-Setup and run it (More info -> Run anyway). Linux: the zip."
        r = subprocess.run(["gh", "release", "create", tag, *files, "--title", f"Vanguard {__version__}",
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
