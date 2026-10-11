"""
Build the public page for vanguard.winklers-llc.com.

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

REPO = "https://github.com/winklersllc2026-bit/Vanguard"                    # the code: private
RELEASES_REPO = "winklersllc2026-bit/Vanguard-releases"                     # downloads only: public, no source code
RELEASES = f"https://github.com/{RELEASES_REPO}"
LATEST = "Vanguard-Setup-latest.exe"            # uploaded with every release (python site/build.py --release)
LATEST_URL = f"{RELEASES}/releases/latest/download/{LATEST}"

INCLUDE_DIRS = ["vanguard", "web", "tools", "tests", "faith", "library", "books"]
INCLUDE_FILES = ["run.py", "start-vanguard.bat", "start-vanguard.sh", "start-classroom.bat", "start-classroom.sh", "install-vanguard.bat", "install-vanguard.sh", "README.md", "LIBRARY.md", "SECURITY.md"]

ROADMAP = [
    (True, "0.2: every branch — Army, Navy, Air Force, Marine Corps and Space Force sections in Learn; your program's labels"),
    (True, "0.2: simple setup — first-run wizard, Join screen with a QR code, join codes per class or platoon, 30-second sign-up"),
    (True, "0.2: Home screen and a 4-tab bar (Home, Learn, Lead, Me); an instructor menu (Today, Class, Lessons, Present, Reports, Settings)"),
    (True, "0.2: military jobs in every service from official sites; ASVAB practice with exact scoring"),
    (True, "0.2.1: deeper Navy, Air Force, Space Force and Marine Corps cards; official military videos (offline once saved)"),
    (True, "0.2.2: Class day — the instructor's Home walks through setup, then Start class runs today's lesson, scenarios, live questions and videos from one run sheet"),
    (True, "0.2.3: security review — classroom network locked to this computer's address, program data sealed, safer restores and updates, pinned dependencies, honest privacy notes"),
    (True, "Roles: Cadet, guardian and instructor profiles; Class PIN; class records only for the instructor"),
    (True, "Classes, platoons and squads; lessons assigned to everyone, units or Cadets (late joiners get them once)"),
    (True, "Learn: 200+ study cards from official U.S. government and military sources, each citing its source"),
    (True, "Quizzes typed and graded by Vanguard — Practice (multiple choice) and Challenge (typed); never self-reported"),
    (True, "Leadership scenarios (20) with a leadership log; classroom vote on the projector"),
    (True, "Live in-class pop quiz: one question on the projector, Cadets answer on their devices, counts only"),
    (True, "Train: fitness events and goals measured against yourself"),
    (True, "Serve: service hours with instructor verification; Explore Military Service (opt-in, information only)"),
    (True, "Progress: growth over time, achievements, recognition, printable portfolio"),
    (True, "Instructor dashboard, class report CSV, program backup and restore, quiz editor, assigned pop quizzes"),
    (True, "Pilot tools: setup, weekly snapshots, anonymous Cadet survey, instructor feedback, pilot report"),
    (True, "Installable app on phones and computers; works offline on the classroom network"),
    (True, "Release signing: updates are signed with the publisher's own key (2026-10-11)"),
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
                    if d in ("books", "library") and p.suffix.lower() == ".pdf":
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
# (3.12 stopped getting Windows builds at 3.12.10, so later security fixes never reached the installer.)
PYTHON_EMBED = ("https://www.python.org/ftp/python/3.14.8/python-3.14.8-embed-amd64.zip",
                "a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310")
PYTHON_TAG = "3.14"
# cryptography (profile encryption in vault.py, update signatures) and its two dependencies, pinned by version + hash.
PYTHON_REQUIREMENTS = SITE / "bundle-requirements.txt"
WRANGLER = "4.141.0"                             # Cloudflare's deploy tool, a fixed version (not "latest")
PYTHON_UNUSED = ("sqlite3.dll", "_sqlite3.pyd", "_elementtree.pyd", "_lzma.pyd", "_bz2.pyd", "_decimal.pyd", "python.cat")


def bundle_python(app: Path) -> bool:
    """Put Python (embeddable) + the cryptography package in app/python. Vanguard then runs as
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
                        "--python-version", PYTHON_TAG, "--implementation", "cp",
                        "--require-hashes", "-r", str(PYTHON_REQUIREMENTS)],
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
:root { --bg:#0f120e; --bg2:#141a12; --card:#1a2017; --line:rgba(220,210,180,.13); --text:#ece6d6; --muted:#a9a28e;
  --tan:#cdb57c; --tan2:#e2cc94; }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; background:var(--bg); color:var(--text); font:18px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }
a { color:var(--tan2); }
.wrap { max-width:1120px; margin:0 auto; padding:0 20px; }
header.top { position:sticky; top:0; z-index:5; background:rgba(15,18,14,.92); backdrop-filter:blur(8px); border-bottom:1px solid var(--line); }
header.top .wrap { display:flex; align-items:center; justify-content:space-between; gap:12px; height:64px; }
.brand { font-weight:800; letter-spacing:.12em; color:var(--text); text-decoration:none; font-size:18px; }
.brand span { color:var(--tan); }
header nav { display:flex; gap:18px; align-items:center; } header nav a { color:var(--muted); text-decoration:none; font-size:16px; }
header nav a:hover { color:var(--text); }
@media (max-width:720px) { header nav a.hide-sm { display:none; } }
.btn { display:inline-flex; align-items:center; gap:8px; background:var(--tan); color:#1b1608; font-weight:800; text-decoration:none;
  padding:14px 22px; border-radius:12px; font-size:18px; border:0; }
.btn:hover { background:var(--tan2); }
.btn.ghost { background:transparent; color:var(--text); border:1px solid var(--line); font-weight:600; }
.btn.small { padding:9px 14px; font-size:15px; }
section { padding:72px 0; border-bottom:1px solid var(--line); }
section.alt { background:var(--bg2); }
h1 { font-size:clamp(36px,6vw,64px); line-height:1.05; margin:0 0 18px; letter-spacing:-.01em; }
h2 { font-size:clamp(28px,4vw,42px); line-height:1.15; margin:0 0 14px; }
h3 { font-size:22px; margin:0 0 8px; }
.lead { font-size:clamp(19px,2.2vw,23px); color:var(--muted); max-width:760px; margin:0 0 28px; }
.kicker { color:var(--tan); font-weight:700; letter-spacing:.14em; text-transform:uppercase; font-size:14px; margin:0 0 10px; }
.hero { padding:64px 0 40px; }
.hero .row { display:flex; gap:12px; flex-wrap:wrap; margin:0 0 14px; }
.hero small { color:var(--muted); font-size:15px; }
.shot { display:block; width:100%; height:auto; border-radius:14px; border:1px solid var(--line);
  box-shadow:0 24px 60px rgba(0,0,0,.45); background:#0b0d0a; }
.phone { max-width:300px; border-radius:28px; border:6px solid #262d22; }
.duo { display:grid; grid-template-columns:minmax(0,3fr) minmax(0,1fr); gap:28px; align-items:end; margin-top:40px; }
@media (max-width:820px) { .duo { grid-template-columns:1fr; } .duo .phone { max-width:260px; margin:0 auto; } }
.steps { display:grid; gap:56px; margin-top:36px; }
.step { display:grid; grid-template-columns:minmax(0,2fr) minmax(0,3fr); gap:36px; align-items:center; }
.step:nth-child(even) .text { order:2; }
@media (max-width:820px) { .step { grid-template-columns:1fr; } .step:nth-child(even) .text { order:0; } }
.num { display:inline-grid; place-items:center; width:44px; height:44px; border-radius:50%; background:var(--tan); color:#1b1608;
  font-weight:900; font-size:22px; margin-bottom:12px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:18px; margin-top:30px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:22px; }
.card p { margin:0; color:var(--muted); font-size:17px; }
.card .ic { font-size:30px; display:block; margin-bottom:8px; }
.gallery { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:24px; margin-top:32px; align-items:start; }
.gallery figure { margin:0; } .gallery figcaption { color:var(--muted); font-size:16px; margin-top:10px; }
.phones { display:flex; gap:24px; flex-wrap:wrap; justify-content:center; margin-top:32px; }
.phones figure { margin:0; text-align:center; } .phones figcaption { color:var(--muted); font-size:16px; margin-top:10px; }
.setup { counter-reset:s; list-style:none; padding:0; margin:30px 0 0; display:grid; gap:16px; }
.setup li { counter-increment:s; background:var(--card); border:1px solid var(--line); border-radius:16px; padding:22px 22px 22px 84px; position:relative; }
.setup li::before { content:counter(s); position:absolute; left:22px; top:20px; width:44px; height:44px; border-radius:50%;
  background:var(--tan); color:#1b1608; font-weight:900; font-size:22px; display:grid; place-items:center; }
.setup b { font-size:20px; } .setup p { margin:6px 0 0; color:var(--muted); }
.tip { border-left:4px solid var(--tan); background:var(--card); padding:16px 20px; border-radius:0 12px 12px 0; margin-top:24px; color:var(--muted); }
.tip b { color:var(--text); }
.checks { list-style:none; padding:0; margin:20px 0 0; display:grid; gap:12px; }
.checks li { padding-left:36px; position:relative; } .checks li::before { content:"✓"; position:absolute; left:0; top:0; color:var(--tan); font-weight:900; font-size:22px; line-height:1.3; }
details { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 20px; margin:12px 0; }
summary { cursor:pointer; font-weight:700; font-size:19px; } details p { color:var(--muted); margin:10px 0 0; }
.dl { text-align:center; } .dl .lead { margin-left:auto; margin-right:auto; }
.fine { color:var(--muted); font-size:14px; word-break:break-all; }
footer { padding:36px 0 60px; color:var(--muted); font-size:15px; } footer a { color:var(--muted); }
.mono { font-family:ui-monospace,Consolas,monospace; }
"""

DISCLAIMER = ("Vanguard is designed to support JROTC instruction. It is not an official JROTC, Army, Navy, Air Force, "
              "Marine Corps, Space Force or school product, does not replace your instructor or your program's "
              "curriculum, and makes no claim of endorsement.")


def shell(title: str, here: str, body: str, description: str = "") -> str:
    desc = description or ("Vanguard runs your JROTC class from one laptop. Cadets join from their phones with a QR "
                           "code. Lessons, leadership scenarios, live questions and videos — private, no internet needed, free during the pilot.")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">
<link rel="icon" href="/icon.svg" type="image/svg+xml"><style>{STYLE}</style></head><body>
<header class="top"><div class="wrap"><a class="brand" href="/"><span>✦</span> VANGUARD</a>
<nav><a href="/#class-day" class="hide-sm">How it works</a><a href="/#setup" class="hide-sm">Set up</a>
<a href="/security">Privacy</a><a class="btn small" href="/#download">Download</a></nav></div></header>
{body}
<footer><div class="wrap"><p>{html.escape(DISCLAIMER)}</p>
<p>Built by Winklers LLC · <a href="/security">Privacy and security</a> · <a href="/pilot">Run a pilot</a> · Version {html.escape(__version__)}</p></div></footer>
</body></html>"""


def page(zip_name: str, size: int, commit: str, history, sha: str = "", setup=None) -> str:
    esc = html.escape
    if setup:
        setup_link = f"{RELEASES}/releases/latest/download/{LATEST}"
        download = f"""<a class="btn" href="{esc(setup_link)}">⬇ Download Vanguard for Windows</a>
          <p class="fine" style="margin-top:14px">Free during the pilot · version {esc(__version__)} · {setup[1] / 2**20:.0f} MB ·
          <a href="{esc(RELEASES)}/releases/latest">other downloads (zip for a USB drive, Linux, Raspberry Pi)</a></p>
          <p class="fine">SHA-256 of the installer: <span class="mono">{esc(setup[2])}</span></p>"""
    else:
        download = f'<a class="btn" href="{esc(RELEASES)}/releases/latest">⬇ Download Vanguard</a>'
    body = f"""
<section class="hero"><div class="wrap">
  <p class="kicker">For JROTC instructors</p>
  <h1>Run your whole class<br>from one laptop.</h1>
  <p class="lead">Cadets join from their phones by scanning a QR code. You press <b>Start class</b> and teach — lessons,
  leadership votes, live questions and videos, all from one screen. No accounts. No internet. Free during the pilot.</p>
  <div class="row"><a class="btn" href="#download">⬇ Download</a><a class="btn ghost" href="#class-day">See a class day →</a></div>
  <small>Windows laptop · works with any phone, tablet or Chromebook · everything stays in your classroom</small>
  <div class="duo"><img class="shot" src="/shots/run-sheet.png" alt="The instructor's Today's class screen: a lesson, two scenarios, two live questions and a video, each with its own button">
    <img class="shot phone" src="/shots/phone-vote.png" alt="A Cadet voting on a leadership scenario on their phone"></div>
</div></section>

<section id="class-day"><div class="wrap">
  <p class="kicker">A class day</p>
  <h2>Three steps. That's the whole thing.</h2>
  <div class="steps">
    <div class="step"><div class="text"><span class="num">1</span><h3>Press Start class and pick today's plan</h3>
      <p class="lead" style="font-size:19px">Tick a lesson, a leadership scenario or two, a few live questions and a video. Vanguard turns it into
      a run sheet — one button for each thing, in order.</p></div>
      <img class="shot" src="/shots/instructor-home.png" alt="The instructor's Home screen with a big Start class button" loading="lazy"></div>
    <div class="step"><div class="text"><span class="num">2</span><h3>Cadets scan the code on the projector</h3>
      <p class="lead" style="font-size:19px">Put the Join screen up. Cadets point their phone camera at it, type their name and a PIN, and
      they're in — placed in your class automatically. About 30 seconds.</p></div>
      <img class="shot" src="/shots/join-screen.png" alt="The Join screen: a large QR code, the address to type, and the class join code" loading="lazy"></div>
    <div class="step"><div class="text"><span class="num">3</span><h3>Teach. Everyone answers.</h3>
      <p class="lead" style="font-size:19px">Put a leadership scenario on the projector and every Cadet votes from their seat — anonymously,
      so the quiet ones answer too. Reveal the discussion guidance when you're ready. Ask a live question and see who's
      got it in real time.</p></div>
      <img class="shot" src="/shots/projector-vote.png" alt="A leadership scenario on the projector with live vote counts" loading="lazy"></div>
  </div>
</div></section>

<section class="alt"><div class="wrap">
  <p class="kicker">Why instructors use it</p>
  <h2>Less prep. More of your Cadets talking.</h2>
  <div class="grid">
    <div class="card"><span class="ic">⏱️</span><h3>Plan class in two minutes</h3><p>Pick from ready-made lessons, scenarios, questions and videos — or write your own once and reuse it every year.</p></div>
    <div class="card"><span class="ic">🙋</span><h3>Every Cadet participates</h3><p>Anonymous votes and live questions on their own phones. You see the whole room's answer, not just the front row's.</p></div>
    <div class="card"><span class="ic">🔒</span><h3>Private by design</h3><p>Everything stays on your laptop. No cloud, no accounts, no ads, no tracking. Each Cadet's work is locked with their own PIN.</p></div>
    <div class="card"><span class="ic">📶</span><h3>No internet needed</h3><p>Works in a classroom with no internet at all. Cadets only need to be on the same Wi-Fi as your laptop.</p></div>
    <div class="card"><span class="ic">📘</span><h3>Every branch, official sources</h3><p>Army, Navy, Air Force, Marine Corps and Space Force study cards — each one names the official manual or page it comes from.</p></div>
    <div class="card"><span class="ic">💲</span><h3>Free during the pilot</h3><p>Nothing for your school to buy while we pilot Vanguard with JROTC programs. Your laptop is the whole system — no server, no subscription to manage.</p></div>
  </div>
</div></section>

<section><div class="wrap">
  <p class="kicker">What's inside</p>
  <h2>Everything a Cadet needs, on their phone.</h2>
  <p class="lead">Cadets get their own Home screen: what's due, a Daily 10 quiz, and anything you start in class. They study
  every branch of service, take quizzes Vanguard grades for them, and keep a leadership log.</p>
  <div class="phones">
    <figure><img class="shot phone" src="/shots/phone-home.png" alt="A Cadet's Home screen" loading="lazy"><figcaption>A Cadet's Home</figcaption></figure>
    <figure><img class="shot phone" src="/shots/phone-learn.png" alt="Learn: assignments and study sections for every branch" loading="lazy"><figcaption>Learn: every branch</figcaption></figure>
    <figure><img class="shot phone" src="/shots/phone-vote.png" alt="Voting on a scenario" loading="lazy"><figcaption>Class vote</figcaption></figure>
  </div>
  <div class="gallery">
    <figure><img class="shot" src="/shots/projector-question.png" alt="A live question with the answers revealed" loading="lazy"><figcaption>Live questions — results stay hidden until you reveal them.</figcaption></figure>
    <figure><img class="shot" src="/shots/projector-video.jpg" alt="An official military training video playing" loading="lazy"><figcaption>Official military videos that play with no internet.</figcaption></figure>
  </div>
  <div class="grid">
    <div class="card"><span class="ic">📋</span><h3>Lessons and assignments</h3><p>Write a lesson once, assign it to a class, see who finished.</p></div>
    <div class="card"><span class="ic">🧭</span><h3>Leadership scenarios</h3><p>Real situations a Cadet leader meets, with discussion guidance for you.</p></div>
    <div class="card"><span class="ic">🎯</span><h3>ASVAB practice and jobs</h3><p>Practice tests with exact scoring and a jobs explorer for every service.</p></div>
    <div class="card"><span class="ic">📈</span><h3>Progress and portfolio</h3><p>Growth over time, service hours you verify, and a portfolio a Cadet can print.</p></div>
  </div>
</div></section>

<section class="alt" id="setup"><div class="wrap">
  <p class="kicker">Set up</p>
  <h2>Ready in about five minutes.</h2>
  <p class="lead">No IT ticket. No admin password. Nothing for Cadets to install.</p>
  <ol class="setup">
    <li><b>Download Vanguard and double-click it.</b><p>Click Next until it's done. A Vanguard icon appears on your desktop.
      If Windows shows a blue box that says <i>"Windows protected your PC"</i>, click <b>More info</b>, then <b>Run anyway</b>.</p></li>
    <li><b>Open Vanguard and make your Class PIN.</b><p>Choose "I'm the instructor", pick your JROTC program, and make two PINs:
      a <b>Class PIN</b> that opens your class, and your own PIN. Write down the backup code it shows you.</p></li>
    <li><b>On class day, press "Open class to phones".</b><p>It's on your Home screen in Vanguard. The Join screen with the QR
      code is one tap away — put it on the projector, then press <b>▶ Start class</b>. Your Home screen walks you through anything left to do.</p></li>
  </ol>
  <div class="tip"><b>If Cadets' phones can't connect:</b> some school Wi-Fi blocks devices from talking to each other. Ask IT to
  allow it, or bring a small travel router (about $30 — it doesn't need internet) and have everyone join that instead. For a
  handful of Cadets, your laptop's own hotspot works too.</div>
</div></section>

<section><div class="wrap">
  <p class="kicker">Privacy, in plain words</p>
  <h2>Your Cadets' work never leaves your classroom.</h2>
  <ul class="checks">
    <li>Everything is stored on your laptop — not in the cloud, not on our servers. We never see it.</li>
    <li>Each Cadet has their own PIN, and their files are encrypted with it.</li>
    <li>You see class work — lessons, quizzes, scenarios, fitness, service. A Cadet's private notes and chats are locked to them alone.</li>
    <li>Votes are anonymous: you see the totals, never who picked what.</li>
    <li>Very little personal information: a name and a PIN. No email, no phone number, no photos.</li>
  </ul>
  <p style="margin-top:20px"><a href="/security">More about privacy and security →</a></p>
</div></section>

<section class="alt"><div class="wrap" style="max-width:860px">
  <p class="kicker">Questions</p>
  <h2>Good to know</h2>
  <details><summary>Does it cost anything?</summary><p>Not during the pilot. Vanguard is free to download and use while we pilot it with JROTC programs.</p></details>
  <details><summary>Does it need the internet?</summary><p>No. Your laptop runs everything. Cadets only need to join the same Wi-Fi as your laptop — that Wi-Fi doesn't need internet.</p></details>
  <details><summary>What do Cadets need?</summary><p>Any phone, tablet, Chromebook or school computer with a web browser. Nothing to install and no accounts to make — a name and a PIN.</p></details>
  <details><summary>What computer do I need?</summary><p>A Windows laptop. (It also runs on Linux and a Raspberry Pi.) No special hardware.</p></details>
  <details><summary>Can Cadets study at home?</summary><p>Yes. Vanguard can run from a USB flash drive with no installation, and each Cadet can have their own drive. Their work stays on the drive, locked with their PIN.</p></details>
  <details><summary>Is this an official JROTC product?</summary><p>No. Vanguard is designed to support JROTC instruction, but it isn't an official JROTC, military or school product, and it doesn't replace your program's curriculum. Study material comes from official public sources, and each card says which one.</p></details>
  <details><summary>What if a Cadet forgets their PIN?</summary><p>When they make their PIN, Vanguard shows a one-time backup code. With it they can choose a new PIN — their work stays protected the whole time.</p></details>
</div></section>

<section id="download" class="dl"><div class="wrap">
  <h2>Try it with your next class.</h2>
  <p class="lead">Download Vanguard, set your Class PIN, and press Start class. If it doesn't make your day easier, uninstall it — nothing to cancel.</p>
  {download}
</div></section>"""
    return shell("Vanguard — run your JROTC class from one laptop", "home", body)


def pilot_page() -> str:
    body = """<section class="hero"><div class="wrap" style="max-width:860px">
<p class="kicker">For programs and schools</p><h1 style="font-size:clamp(32px,5vw,52px)">Run a pilot</h1>
<p class="lead">A pilot shows whether Vanguard helps <i>your</i> program — measured from real class records, not guesses.</p>
<ol class="setup">
<li><b>Set it up</b><p>In Vanguard: Instructor → Pilot. School, dates, how many Cadets, and what to measure — engagement, lesson completion, academics, leadership scenarios, fitness, service, your workload, feedback.</p></li>
<li><b>Take a snapshot on day one</b><p>Then about once a week. The report shows the change over the pilot.</p></li>
<li><b>Teach as usual</b><p>Assign lessons, run scenarios and live questions, record fitness and service.</p></li>
<li><b>Open the Cadet survey near the end</b><p>Five short questions, stored with no name or ID.</p></li>
<li><b>Print the pilot report</b><p>Every number comes from real records, and what Vanguard can't measure is said plainly.</p></li>
</ol>
<div class="tip"><b>What a school needs:</b> one Windows laptop for the instructor and Cadets' devices on the same Wi-Fi. No server, no cloud account, no subscription.</div>
<p style="margin-top:24px">Interested? Contact Winklers LLC to talk about a pilot.</p>
</div></section>"""
    return shell("Vanguard — Run a pilot", "pilot", body)


def security_page() -> str:
    body = """<section class="hero"><div class="wrap" style="max-width:860px">
<p class="kicker">Privacy and security</p><h1 style="font-size:clamp(32px,5vw,52px)">Built for minors' data from the start</h1>
<ul class="checks">
<li><b>Everything is stored on the instructor's laptop</b> (or the USB drive Vanguard runs from). No cloud, no outside accounts, no tracking, no advertising.</li>
<li><b>Each profile has its own PIN, and its files are encrypted</b> (AES-256-GCM, with the key locked by the PIN).</li>
<li><b>The instructor sees class records only</b> — lessons, quizzes, exams, leadership scenarios, fitness and service. A Cadet's private check-ins, chats and notes are sealed with that Cadet's own key; the instructor can't open them.</li>
<li><b>Two keys for class records:</b> the instructor's own PIN and the Class PIN.</li>
<li><b>Cadets never see another Cadet's work</b>, and there are no public leaderboards. Class votes show totals only.</li>
<li><b>Assigned quizzes can't be faked:</b> Cadets type or pick answers and Vanguard grades them; the answer isn't sent to the screen early.</li>
<li><b>Minimal data about minors:</b> Vanguard asks for a name and a PIN — no email, phone number, photos or birth date. Whatever else a Cadet types stays in their own encrypted files.</li>
<li><b>The classroom network:</b> other devices on the Wi-Fi see shortened names before sign-in, and a profile without a PIN can only be opened on the instructor's own computer. Requests from other websites, and from addresses other than the laptop's own, are refused. Traffic on that network isn't encrypted (plain HTTP), so use a hotspot only your class joins.</li>
<li><b>No internet unless you choose it:</b> Vanguard never connects to the internet on its own. Optional online AI is off unless the device owner turns it on with their own key; then only ordinary Ask questions go to it, without names, notes or earlier chats.</li>
<li><b>Ask is private, not monitored:</b> a safety check shows help numbers (988, 911) when a message sounds unsafe. It notifies no one.</li>
<li><b>Forgotten PIN:</b> each person gets a one-time backup code. There is no master key for private files — not even for us.</li>
</ul>
<div class="tip"><b>For school IT:</b> turn on full-disk encryption (BitLocker) on the instructor's laptop, keep Windows updated, and use a standard (non-admin) account day to day. For the classroom, a dedicated hotspot or travel router that only the class joins is better than open or guest Wi-Fi. Full technical details — threats, protections and the automated attack tests — are in SECURITY.md with the code.</div>
</div></section>"""
    return shell("Vanguard — Privacy and security", "security", body)


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    for old in DIST.glob("*"):                    # a clean start: files and folders (shots/)
        shutil.rmtree(old) if old.is_dir() else old.unlink()
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
    shots = SITE / "shots"                        # python site/shots.py makes these from the real app
    if shots.is_dir():
        (DIST / "shots").mkdir(exist_ok=True)
        for f in shots.glob("*.*"):
            shutil.copy(f, DIST / "shots" / f.name)
    (DIST / "index.html").write_text(page(zip_name, size, commit, history, sha, setup), encoding="utf-8")
    (DIST / "pilot.html").write_text(pilot_page(), encoding="utf-8")
    (DIST / "security.html").write_text(security_page(), encoding="utf-8")
    (DIST / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")   # the page is public now
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
        # to the public releases repo: anyone can download, and the code repo stays private
        r = subprocess.run(["gh", "release", "create", tag, *files, "--repo", RELEASES_REPO,
                            "--title", f"Vanguard {__version__}", "--notes", notes], cwd=ROOT)
        if r.returncode != 0:                     # release already there: replace its files
            r = subprocess.run(["gh", "release", "upload", tag, *files, "--clobber", "--repo", RELEASES_REPO], cwd=ROOT)
        if r.returncode != 0:
            return r.returncode
        print(f"Released {tag}: {RELEASES}/releases/tag/{tag}\nThe page's download button: {LATEST_URL}")
    if "--deploy" in sys.argv:
        # downloads come from the public releases repo, not the site (Cloudflare's 25 MB limit): tell wrangler to skip
        # them -- they stay in site/dist, where tools/make_usb.py picks up the installer for the drive
        (DIST / ".assetsignore").write_text("Vanguard*\n*.sig\n", encoding="utf-8")
        return subprocess.run(f"npx --yes wrangler@{WRANGLER} deploy", cwd=SITE, shell=True).returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
