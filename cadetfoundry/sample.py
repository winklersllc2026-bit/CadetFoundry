"""
The sample class: a finished classroom with made-up Cadets, for an instructor who wants to see what Cadet Foundry does
before setting anything up.

It is a SEPARATE copy of Cadet Foundry: its own throwaway data folder (next to the real one, named "...-sample") and its
own port on this computer only. Real profiles, class records and settings are never opened, copied or changed, and
"Leave sample" simply closes it. The folder is rebuilt from scratch every time the sample starts.

    real Cadet Foundry  --/api/sample/start-->  python run.py (CADETFOUNDRY_SAMPLE=1, CADETFOUNDRY_DATA=<...-sample>)
                                            builds the class through its own API, then signs the visitor in
"""
from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from cadetfoundry import store

ACTIVE = os.environ.get("CADETFOUNDRY_SAMPLE") == "1"     # this process IS the sample class
BACK = os.environ.get("CADETFOUNDRY_SAMPLE_BACK", "")     # where "Leave sample" goes (the real Cadet Foundry)
MARKER = "SAMPLE_DATA.txt"                            # only a folder with this file is ever deleted
IDLE_LIMIT = 45 * 60                                  # an abandoned sample closes itself

# Made-up people. The PINs only open this throwaway folder; the visitor never types them.
CLASS_PIN = "271828"
INSTRUCTOR = ("Sgt. Sample", "161803")
CADETS = [  # name, squad (0 = Alpha, 1 = Bravo), year, cadet rank, billet, how much work they've done (0-3)
    ("Avery Sample", 0, 2, "Cadet Sergeant", "Squad leader", 3),
    ("Blake Sample", 0, 1, "Cadet Private", "", 3),
    ("Casey Sample", 0, 1, "Cadet Private", "", 2),
    ("Drew Sample", 0, 1, "", "", 1),
    ("Emerson Sample", 1, 2, "Cadet Corporal", "Squad leader", 3),
    ("Finley Sample", 1, 1, "Cadet Private", "", 2),
    ("Gray Sample", 1, 1, "", "", 0),
    ("Harper Sample", 1, 1, "Cadet Private", "Color guard", 2),
]
CADET_PIN = "482915"

# Two short lessons built only from facts already in Cadet Foundry's cited study cards.
LESSONS = [
    {"title": "The three branches of government", "let_level": 1, "competency": "Citizenship",
     "objective": "Name the three branches and what each one does.",
     "source": "U.S. Constitution, Articles I–III",
     "content": "The Constitution divides the federal government into three branches. Congress (the legislative "
                "branch) makes laws. The President (the executive branch) carries them out. The courts (the judicial "
                "branch) decide what the laws mean. Each branch can check the other two.",
     "questions": "Q: How many branches does the federal government have?\n* Three\n- Two\n- Four\n"
                  "Q: Which branch makes the laws?\n* The legislative branch (Congress)\n- The judicial branch\n"
                  "- The executive branch",
     "reflection": "Give one example of a branch checking another branch."},
    {"title": "Chain of command", "let_level": 1, "competency": "Leadership",
     "objective": "Know who leads whom, and why the chain matters.",
     "source": "Cadet Foundry study card: Chain of command",
     "content": "The chain of command runs from the President, the Commander in Chief, down to the newest member. "
                "In the cadet corps it runs from the cadet commander down through platoon and squad leaders.",
     "questions": "Q: Who is at the top of the military chain of command?\n* The President\n- The first sergeant\n"
                  "- The squad leader",
     "reflection": "Who is in your chain of command in the cadet corps?"},
]
RIGHT = {"Three", "The legislative branch (Congress)", "The President"}

_state = {"ready": False, "error": "", "step": "Starting"}
_last_seen = time.time()
_child: dict = {}                                     # in the real Cadet Foundry: the sample process we started


# ── the real Cadet Foundry's side: start (or reuse) the sample ───────────────────

def folder() -> Path:
    real = store.DATA.resolve()
    return real.with_name(real.name + "-sample")


def _prepare(path: Path) -> None:
    """A fresh, empty sample folder. Refuses any existing folder that isn't marked as sample data."""
    if path.exists():
        if not (path / MARKER).exists():
            raise RuntimeError(f"{path} exists and isn't a sample folder, so it wasn't touched.")
        shutil.rmtree(path)
    path.mkdir(parents=True)
    (path / MARKER).write_text("Cadet Foundry's sample class: made-up people only. Safe to delete.\n", encoding="utf-8")
    index = store.DATA / "library_index.json"         # the study library's search index (public content only):
    if index.is_file():                               # reused, so the sample starts in seconds instead of rebuilding it
        shutil.copyfile(index, path / index.name)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ask(port: int, path: str, timeout: float = 2.0) -> dict | None:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        c.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
        r = c.getresponse()
        return json.loads(r.read() or b"{}") if r.status == 200 else None
    except (OSError, ValueError):
        return None
    finally:
        c.close()


def start(back_url: str, wait: float = 60.0) -> str:
    """Start the sample (or reuse a running one); returns its address as soon as it answers. Its own page then shows
    the class being built."""
    proc = _child.get("proc")
    if proc and proc.poll() is None:
        st = _ask(_child["port"], "/api/sample/status")
        if st and not st.get("error"):
            return _child["url"]
        proc.terminate()                              # stuck or half-built: start over
        proc.wait(timeout=10)
    path = folder()
    _prepare(path)
    port = _free_port()
    env = {**os.environ, "CADETFOUNDRY_SAMPLE": "1", "CADETFOUNDRY_DATA": str(path), "CADETFOUNDRY_SAMPLE_BACK": back_url,
           "CADETFOUNDRY_NO_WARMUP": "1"}
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        exe = exe.with_name("python.exe")            # no window either way (CREATE_NO_WINDOW below)
    run = Path(__file__).resolve().parent.parent / "run.py"
    proc = subprocess.Popen([str(exe), str(run), "--port", str(port), "--no-browser"], env=env,
                            cwd=str(run.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _child.update(proc=proc, port=port, url=f"http://127.0.0.1:{port}/")
    end = time.time() + wait
    while time.time() < end:
        if proc.poll() is not None:
            raise RuntimeError("The sample class stopped while starting.")
        if _ask(port, "/api/sample/status"):
            return _child["url"]
        time.sleep(0.3)
    proc.terminate()
    raise RuntimeError("The sample class took too long to start.")


def stop_child() -> None:
    proc = _child.get("proc")
    if proc and proc.poll() is None:
        proc.terminate()


# ── the sample's side ───────────────────────────────────────────────────────

def status() -> dict:
    return {"sample": ACTIVE, "ready": _state["ready"], "error": _state["error"], "step": _state["step"]}


def touch() -> None:
    global _last_seen
    _last_seen = time.time()


def _parent_port() -> int | None:
    from urllib.parse import urlsplit
    try:
        u = urlsplit(BACK)
        return u.port if u.hostname in ("127.0.0.1", "localhost") else None
    except ValueError:
        return None


def watch_idle(httpd, every: float = 60) -> None:
    """Close an abandoned sample: the visitor closed the tab without leaving (45 idle minutes), or the Cadet Foundry that
    opened it is gone (it didn't answer twice in a row) -- a sample never outlives its Cadet Foundry for long."""
    port = _parent_port()

    def loop():
        missed = 0
        while True:
            time.sleep(every)
            missed = missed + 1 if port and _ask(port, "/api/sample/status") is None else 0
            if time.time() - _last_seen > IDLE_LIMIT or missed >= 2:
                httpd.shutdown()
                return
    threading.Thread(target=loop, daemon=True).start()


def enter() -> str | None:
    """A session for the sample's instructor with the class records open; None until the class is built."""
    from cadetfoundry import profiles, security
    if not (ACTIVE and _state["ready"]):
        return None
    inst = next((p for p in profiles.all_profiles() if p["kind"] == "instructor"), None)
    if not inst:
        return None
    token, _ = security.unlock(inst["id"], INSTRUCTOR[1])
    if token and security.unlock_program(token, CLASS_PIN):
        security.lock(token)
        return None
    return token


class _Client:
    """The sample is built through Cadet Foundry's own API, exactly as people would do it."""

    def __init__(self, port: int):
        self.port = port

    def call(self, method: str, path: str, body=None, cookie: str = ""):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        h = {"Host": f"127.0.0.1:{self.port}", "Cookie": cookie}
        if body is not None:
            h["Content-Type"] = "application/json"
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=h)
        r = c.getresponse()
        data = r.read()
        ck = (r.getheader("Set-Cookie") or "").split(";")[0]
        c.close()
        out = json.loads(data or b"{}") if "json" in (r.getheader("Content-Type") or "") else {}
        if r.status != 200:
            raise RuntimeError(f"{path}: {out.get('error') or r.status}")
        return out, ck


def build(port: int, app) -> None:
    """Fill the sample folder with a class mid-way through a pilot. Runs once, in the sample process."""
    try:
        _build(_Client(port), app)
        _state.update(ready=True, step="Ready")
    except Exception as e:                            # shown to the visitor instead of a half-built class
        _state.update(error=f"The sample class couldn't be built ({e}).", step="Failed")


def _build(api: _Client, app) -> None:
    from cadetfoundry import pilot, reports, security
    today = time.strftime("%Y-%m-%d")
    day = lambda n: time.strftime("%Y-%m-%d", time.localtime(time.time() + n * 86400))  # noqa: E731

    _state["step"] = "Setting up the instructor"
    out, S = api.call("POST", "/api/profiles/create", {"name": INSTRUCTOR[0], "kind": "instructor",
                                                        "pin": INSTRUCTOR[1], "admin": CLASS_PIN})
    api.call("POST", "/api/instructor/program", {"program": "army"}, S)
    period = api.call("POST", "/api/instructor/unit", {"action": "add", "name": "1st Period", "kind": "class"}, S)[0]
    squads = [api.call("POST", "/api/instructor/unit", {"action": "add", "name": n, "kind": "squad",
                                                         "parent": period["id"]}, S)[0]
              for n in ("Alpha Squad", "Bravo Squad")]
    lesson_ids = [api.call("POST", "/api/instructor/lesson", ls, S)[0]["id"] for ls in LESSONS]
    api.call("POST", "/api/instructor/assign-lesson", {"lesson": lesson_ids[0], "units": [period["id"]], "due": day(-1)}, S)
    api.call("POST", "/api/instructor/assign-lesson", {"lesson": lesson_ids[1], "units": [period["id"]], "due": day(5)}, S)

    _state["step"] = "Adding Cadets"
    cadets = []
    for name, squad, year, rank, billet, effort in CADETS:
        out, ck = api.call("POST", "/api/profiles/create", {"name": name, "kind": "cadet", "pin": CADET_PIN,
                                                             "join": squads[squad]["code"]})
        cadets.append((out["profile"]["id"], ck, year, rank, billet, effort))
    api.call("GET", "/api/instructor/overview", cookie=S)            # files the join requests
    for pid, _ck, year, rank, billet, _e in cadets:
        api.call("POST", "/api/instructor/assign", {"cadet": pid, "let": year, "rank": rank, "billet": billet}, S)

    _state["step"] = "Doing some class work"
    scen = sorted(p.stem for p in Path(__file__).parent.joinpath("scenarios").glob("*.md"))
    for n, (pid, ck, _y, _r, _b, effort) in enumerate(cadets):
        mine = api.call("GET", "/api/lessons", cookie=ck)[0]["assignments"]
        for k, a in enumerate(mine[:effort if effort < 3 else 2]):
            lz = api.call("GET", f"/api/lesson?a={a['id']}", cookie=ck)[0]
            qs = lz["lesson"]["questions"] if "lesson" in lz else lz["questions"]
            miss = (n + k) % 3 == 0                                    # some answers wrong, so scores differ
            answers = {str(i): next((j for j, c in enumerate(q["choices"]) if (c in RIGHT) != (miss and i == 0)), 0)
                       for i, q in enumerate(qs)}
            api.call("POST", "/api/lesson/submit", {"a": a["id"], "answers": answers,
                                                    "reflection": "I'd ask my squad leader first."}, ck)
        for s in scen[n % 4: n % 4 + effort]:
            api.call("POST", "/api/scenario/log", {"id": s, "choice": 1, "reflection": "Listen first, then decide."}, ck)
        if effort:
            for i, item in enumerate(api.call("GET", "/api/quiz?n=6", cookie=ck)[0][:2 + 2 * effort]):
                right = app.brain.quiz_item(item["id"])["a"]
                api.call("POST", "/api/quiz/answer", {"id": item["id"], "choice": right if i % 4 else "-"}, ck)
            api.call("POST", "/api/train/add", {"event": "pushups", "value": str(15 + n), "date": day(-28)}, ck)
            api.call("POST", "/api/train/add", {"event": "pushups", "value": str(17 + n + 3 * effort), "date": day(-1)}, ck)
        if effort >= 2:
            entry = api.call("POST", "/api/service/add", {"project": "Food drive", "hours": str(2 + effort), "date": day(-6),
                                                          "reflection": "We sorted cans for the food bank."}, ck)[0]
            if n % 2 == 0:
                api.call("POST", "/api/instructor/service/review",
                         {"cadet": pid, "id": entry["entries"][0]["id"], "action": "verify"}, S)

    _state["step"] = "Starting the pilot"
    api.call("POST", "/api/instructor/pilot", {"school": "Sample High School", "program": "Army JROTC",
                                               "instructor": INSTRUCTOR[0], "start": day(-28), "end": day(30),
                                               "cadets_planned": "8"}, S)
    priv = security.session_program_key(security.token_from_cookie(S))
    first = {**pilot.take_snapshot(priv, reports.dashboard(priv, app.library), force=True)}
    first.update(date=day(-28), cadets=len(cadets), active=0, lesson_completion_pct=0, avg_lesson_score_pct=None,
                 service_hours=0, scenarios=0, cards_mastered=0, avg_fitness_improvement_pct=None)
    pilot._write(priv, "pilot_snapshots.json", [first] + [s for s in pilot.snapshots(priv) if s.get("date") != day(-28)])
    api.call("POST", "/api/instructor/pilot/feedback", {"satisfaction": 4, "minutes_saved": 20, "use_again": "yes",
                                                        "comment": "Made-up feedback for the sample class."}, S)
    for useful, worked in ((4, "Made-up: the live questions got quiet Cadets answering."),
                           (5, "Made-up: the scenario vote started a real discussion.")):
        api.call("POST", "/api/instructor/pilot/daily", {"useful": useful, "again": "yes", "worked": worked}, S)
    for _pid, ck, *_ in cadets:
        api.call("POST", "/api/lock", {}, ck)
    api.call("POST", "/api/lock", {}, S)
    _state["step"] = today
