"""
Screenshots of the real Cadet Foundry for the website: a demo class with made-up names, run in classroom mode, captured
in Microsoft Edge (headless). Run it again after a UI change and the site's pictures are current.

    python site/shots.py            writes site/shots/*.png (then python site/build.py puts them on the page)

Needs Microsoft Edge (every Windows 11 computer has it). Standard library only. Nothing here touches real data:
the demo class lives in a temporary folder that is deleted at the end.
"""
from __future__ import annotations

import base64
import http.client
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "shots"
PORT, DEBUG_PORT = 8811, 9333
EDGE = [Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Microsoft/Edge/Application/msedge.exe"]

CLASS_PIN, INSTRUCTOR_PIN = "905172", "736281"
CADETS = [("Cadet Jordan Ellis", "C/SGT", "Squad Leader"), ("Cadet Maya Chen", "C/CPL", "Team Leader"),
          ("Cadet Sam Ortiz", "C/PFC", ""), ("Cadet Avery Brooks", "C/PFC", ""), ("Cadet Noah Patel", "C/PVT", "")]
CADET_PINS = ["481936", "592047", "603158", "714269", "825370"]


# ── the demo class, made through Cadet Foundry's own API ─────────────────────────────────────────────────────────

class Session:
    def __init__(self):
        self.cookie = ""

    def call(self, method: str, path: str, body: dict | None = None):
        c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
        headers = {"Host": f"localhost:{PORT}", "Content-Type": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        c.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
        r = c.getresponse()
        data = r.read()
        if r.getheader("Set-Cookie"):
            self.cookie = r.getheader("Set-Cookie").split(";")[0]
        c.close()
        try:
            return json.loads(data or b"{}")
        except ValueError:
            return {}


def seed() -> dict:
    inst = Session()
    r = inst.call("POST", "/api/profiles/create", {"name": "Ms. Rivera", "kind": "instructor", "pin": INSTRUCTOR_PIN,
                                                   "admin": CLASS_PIN})
    assert r.get("ok"), r
    inst.call("POST", "/api/terms/accept", {})          # as the instructor does on first run (the "I agree" box)
    inst.call("POST", "/api/instructor/program", {"program": "army"})
    unit = inst.call("POST", "/api/instructor/unit", {"action": "add", "name": "LET 1 · 3rd Period", "kind": "class"})
    cadets = []
    for (name, rank, billet), pin in zip(CADETS, CADET_PINS):
        s = Session()
        r = s.call("POST", "/api/profiles/create", {"name": name, "kind": "cadet", "pin": pin, "join": unit["code"]})
        assert r.get("ok"), r
        cadets.append((s, r["profile"]["id"], name))
    inst.call("GET", "/api/instructor/overview")                     # files the join requests into the roster
    for (s, pid, name), (_, rank, billet) in zip(cadets, CADETS):
        inst.call("POST", "/api/instructor/assign", {"cadet": pid, "let": 1, "rank": rank, "billet": billet})
    inst.call("POST", "/api/instructor/lesson", {
        "title": "Customs and Courtesies", "let_level": "1", "competency": "Leadership",
        "objective": "Render the hand salute correctly and explain when it is given.",
        "source": "AR 600-25, Salutes, Honors, and Courtesies", "content": "## The hand salute\nThe salute is a greeting "
        "between members of the military. The junior member salutes first and holds it until it is returned.",
        "questions": "Q: Who salutes first?\n* The junior member\n- The senior member\n\nQ: How long do you hold the salute?\n"
                     "* Until it is returned\n- For two seconds",
        "vocabulary": "Hand salute: the military greeting\nColors: the national flag carried by a unit",
        "reflection": "Why do you think the salute is still used today?"})
    lesson = inst.call("GET", "/api/instructor/lessons")["lessons"][0]
    due = time.strftime("%Y-%m-%d", time.localtime(time.time() + 2 * 86400))
    inst.call("POST", "/api/instructor/assign-lesson", {"lesson": lesson["id"], "everyone": False, "units": [unit["id"]],
                                                        "cadets": [], "due": due})
    for s, _, _ in cadets[:3]:                                         # a few finished it already
        a = s.call("GET", "/api/lessons")["assignments"][0]
        s.call("POST", "/api/lesson/submit", {"a": a["id"], "answers": {"0": 0, "1": 0},
                                              "reflection": "It shows respect both ways."})
    return {"inst": inst, "cadets": cadets, "unit": unit, "lesson": lesson}


# ── a tiny client for Edge's DevTools protocol (a WebSocket) ────────────────────────────────────────────────

class DevTools:
    def __init__(self, ws_url: str):
        host_port, path = ws_url.split("//", 1)[1].split("/", 1)
        host, port = host_port.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET /{path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        self.extra, self.n = buf.split(b"\r\n\r\n", 1)[1], 0

    def _recv_exact(self, n: int) -> bytes:
        while len(self.extra) < n:
            self.extra += self.sock.recv(1 << 16)
        out, self.extra = self.extra[:n], self.extra[n:]
        return out

    def _send(self, text: str) -> None:
        data, mask = text.encode(), os.urandom(4)
        head = bytes([0x81])
        n = len(data)
        head += bytes([0x80 | n]) if n < 126 else (bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536
                                                   else bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _recv(self) -> dict:
        msg = b""
        while True:
            b1, b2 = self._recv_exact(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            msg += self._recv_exact(n)
            if b1 & 0x80:
                return json.loads(msg)

    def call(self, method: str, **params):
        self.n += 1
        self._send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = self._recv()
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})


def start_edge(profile: Path) -> subprocess.Popen:
    exe = next((p for p in EDGE if p.exists()), None)
    if not exe:
        raise SystemExit("Microsoft Edge wasn't found.")
    return subprocess.Popen([str(exe), "--headless=new", f"--remote-debugging-port={DEBUG_PORT}", f"--user-data-dir={profile}",
                             "--no-first-run", "--hide-scrollbars", "--mute-audio", "--autoplay-policy=no-user-gesture-required",
                             "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def new_tab() -> DevTools:
    for _ in range(50):
        try:
            c = http.client.HTTPConnection("127.0.0.1", DEBUG_PORT, timeout=5)
            c.request("PUT", "/json/new?about:blank")
            info = json.loads(c.getresponse().read())
            return DevTools(info["webSocketDebuggerUrl"])
        except (OSError, ValueError, KeyError):
            time.sleep(0.3)
    raise SystemExit("Edge didn't start.")


class Shooter:
    def __init__(self, tab: DevTools):
        self.tab = tab
        tab.call("Page.enable")
        tab.call("Network.enable")

    def as_(self, session: Session | None) -> None:
        self.tab.call("Network.clearBrowserCookies")
        if session and session.cookie:
            name, value = session.cookie.split("=", 1)
            self.tab.call("Network.setCookie", name=name, value=value, url=f"http://localhost:{PORT}/", httpOnly=True)

    def size(self, w: int, h: int, phone: bool = False) -> None:
        self.tab.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=2 if phone else 1.5,
                      mobile=phone)

    def skip_tour(self, pid: str) -> None:
        """The first-time tour (a popup) would cover a phone screenshot: mark it seen for this profile."""
        self.go("/join", 1)
        self.js(f"localStorage.setItem('tour:{pid}', '1'); return 1;", 0.2)

    def go(self, path: str, wait: float = 3.0) -> None:
        self.tab.call("Page.navigate", url=f"http://localhost:{PORT}{path}")
        time.sleep(wait)

    def js(self, code: str, wait: float = 2.0):
        r = self.tab.call("Runtime.evaluate", expression=f"(async () => {{ {code} }})()", awaitPromise=True,
                          returnByValue=True)
        time.sleep(wait)
        return (r.get("result") or {}).get("value")

    def shot(self, name: str, photo: bool = False) -> None:
        """PNG for screens (crisp text); JPEG for a video frame (a photo -- a tenth of the size)."""
        fmt = {"format": "jpeg", "quality": 82} if photo else {"format": "png"}
        data = self.tab.call("Page.captureScreenshot", **fmt)["data"]
        OUT.mkdir(parents=True, exist_ok=True)
        for old in OUT.glob(f"{name}.*"):
            old.unlink()
        (OUT / f"{name}.{'jpg' if photo else 'png'}").write_bytes(base64.b64decode(data))
        print("  ", name)


def main() -> int:
    data = Path(tempfile.mkdtemp(prefix="cadetfoundry-shots-"))
    env = dict(os.environ, CADETFOUNDRY_DATA=str(data), CADETFOUNDRY_NO_WARMUP="1", PYTHONIOENCODING="utf-8")
    server = subprocess.Popen([sys.executable, "run.py", "--lan", "--port", str(PORT), "--no-browser"], cwd=ROOT, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    edge_profile = Path(tempfile.mkdtemp(prefix="cadetfoundry-edge-"))
    edge = None
    try:
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", PORT), timeout=1).close()
                break
            except OSError:
                time.sleep(0.5)
        print("Making the demo class …")
        demo = seed()
        inst, cadets = demo["inst"], demo["cadets"]
        edge = start_edge(edge_profile)
        s = Shooter(new_tab())
        print("Screenshots:")

        # the instructor's Home, ready for class
        s.as_(inst); s.size(1280, 860)
        s.go("/", 4)
        s.shot("instructor-home")

        # Start class: today's plan
        s.js("""const ov = await api('/api/instructor/overview');
          const sc = (await api('/api/instructor/scenarios')).scenarios;
          const card = (await api('/api/instructor/quiz')).cards.find(c => /Customs, Courtesies/.test(c.title));
          const qs = (await api('/api/instructor/quiz?card=' + encodeURIComponent(card.id))).questions.slice(0, 2);
          const vid = (await api('/api/videos')).videos.find(v => v.local) || (await api('/api/videos')).videos[0];
          const ls = (await api('/api/instructor/lessons')).lessons[0];
          const items = [{type:'lesson', id: ls.id, title: ls.title, sub: 'Assign it; Cadets find it on their Home screen', done: true, note: 'assigned, due today'},
            {type:'scenario', id: sc[0].id, title: sc[0].title, sub: sc[0].competency, done: true},
            {type:'scenario', id: sc[3].id, title: sc[3].title, sub: sc[3].competency},
            ...qs.map(q => ({type:'question', id: q.id, title: q.q, sub: card.title})),
            {type:'video', id: vid.id, title: vid.title, sub: vid.length}];
          localStorage.setItem('cadetfoundry-classday', JSON.stringify({date: new Date().toISOString().slice(0,10), unit: ov.units[0].id, items}));
          return 'ok';""", 0.5)
        s.go("/", 4)
        s.js("window.scrollTo(0, document.getElementById('cdMain').offsetTop - 70);", 0.8)
        s.shot("run-sheet")

        # presentation mode: a study card as a slide, and a check-on-learning question after the reveal
        s.size(1280, 800)
        s.js("""const card = (await api('/api/instructor/quiz')).cards.find(c => /Customs, Courtesies/.test(c.title));
          const plan = JSON.parse(localStorage.getItem('cadetfoundry-classday'));
          plan.items.unshift({type: 'card', id: card.id, title: card.title, sub: 'Study card · slides on the projector'});
          localStorage.setItem('cadetfoundry-classday', JSON.stringify(plan));
          const slides = await buildDeck(plan);
          presentDeck(plan, slides.findIndex(x => x.item.type === 'card' && / 1 of /.test(x.label)));
          return 1;""", 3)
        s.shot("projector-slide")
        s.js("""const plan = cdLoad(); const slides = await buildDeck(plan);
          await endDeck(false);
          presentDeck(plan, slides.findIndex(x => x.item.type === 'lesson' && /Check on learning/.test(x.label)));
          await new Promise(r => setTimeout(r, 2500));
          document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
          return 1;""", 2)
        s.shot("projector-check")
        s.js("await endDeck(false); return 1;", 1)

        # the Join screen on the projector (Cadet phones, optional)
        s.size(1280, 760)
        s.go("/join", 3)
        s.js("""const code = (document.querySelector('.code') || {}).textContent || '';
          const addr = 'http://192.168.1.20:8780';
          document.querySelector('.addr').textContent = addr;
          document.getElementById('qr').innerHTML = QR.svg(addr + '/' + (code ? '?join=' + code : ''), 360);
          document.querySelectorAll('p.faint').forEach(p => { if (/Other addresses/.test(p.textContent))
            p.textContent = p.textContent.replace(/Other addresses.*$/s, ''); });
          return 1;""", 0.5)
        s.shot("join-screen")

        # a leadership scenario on the projector, the class voting
        s.size(1280, 860)
        s.go("/", 3)
        s.js("presentScenarios([(await api('/api/instructor/scenarios')).scenarios[3].id]); return 1;", 2)
        for (cs, _, _), choice in zip(cadets, (1, 1, 0, 1, 2)):
            cs.call("POST", "/api/live/vote", {"choice": choice})
        time.sleep(3.5)
        s.shot("projector-vote")

        # a Cadet's phone during the vote
        s.as_(cadets[4][0]); s.size(390, 844, phone=True)
        s.skip_tour(cadets[4][1])
        s.go("/", 3)
        s.js("openView('lead'); return 1;", 2.5)
        s.shot("phone-vote")
        inst.call("POST", "/api/instructor/live", {"action": "stop"})

        # a live question with the answer revealed
        s.as_(inst); s.size(1280, 860)
        s.go("/", 3)
        s.js("""const card = (await api('/api/instructor/quiz')).cards.find(c => /Customs, Courtesies/.test(c.title));
          const qs = (await api('/api/instructor/quiz?card=' + encodeURIComponent(card.id))).questions;
          const q = qs.find(x => /salutes first/i.test(x.q)) || qs[0];
          await api('/api/instructor/live-quiz', {action: 'start', id: q.id, mode: 'mc'}); liveQuizMode(); return 1;""", 2)
        lq = inst.call("GET", "/api/instructor/live-quiz")
        wrong = [c for c in lq.get("choices", []) if c != lq.get("a")]
        for i, (cs, _, _) in enumerate(cadets):
            cs.call("POST", "/api/live/quiz/answer", {"choice": wrong[0] if i == 3 and wrong else lq.get("a")})
        inst.call("POST", "/api/instructor/live-quiz", {"action": "reveal", "on": True})
        time.sleep(3.5)
        s.shot("projector-question")
        inst.call("POST", "/api/instructor/live-quiz", {"action": "stop"})

        # the Cadet's phone: Home and Learn
        s.as_(cadets[1][0]); s.size(390, 844, phone=True)
        s.skip_tour(cadets[1][1])
        s.go("/", 4)
        s.shot("phone-home")
        s.js("openView('study'); return 1;", 2.5)
        s.shot("phone-learn")

        # a video on the projector
        s.as_(inst); s.size(1280, 860)
        s.go("/", 3)
        s.js("""const v = (await api('/api/videos')).videos.find(x => x.local); if (!v) return 0;
          projectorVideo(v); await new Promise(r => setTimeout(r, 2500)); const el = document.querySelector('video');
          if (el) { el.pause(); el.currentTime = 30; } return 1;""", 2)
        s.shot("projector-video", photo=True)
        print(f"Saved to {OUT}")
        return 0
    finally:
        if edge:
            edge.terminate()
        server.terminate()
        time.sleep(1)
        shutil.rmtree(data, ignore_errors=True)
        shutil.rmtree(edge_profile, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
