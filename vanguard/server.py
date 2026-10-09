"""
Vanguard's local web server (Python standard library only -- runs anywhere,
including a Raspberry Pi with no internet).

Listens only on this device (127.0.0.1) by default. `--lan` lets other devices on
the same Wi-Fi reach it, and is only allowed when a PIN is set.

Every request goes through security checks (vanguard/security.py): the Host must
be Vanguard's own address, cross-site requests are refused, commands must be JSON,
and when a PIN is set everything except the lock screen needs an unlocked session.
"""
from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from vanguard import (addons, backup, board, books, careers, daily, engine, exam, fitness, instructor, integrity,
                      lessons, letters, pay, profiles, scenarios, security, store, train, voice)
from vanguard.brain import Brain
from vanguard.faith import Faith
from vanguard.knowledge import Library

WEB = (Path(__file__).parent.parent / "web").resolve()
mimetypes.add_type("application/manifest+json", ".webmanifest")
PUBLIC_GET = {"/", "/index.html", "/icon.svg", "/api/lock",       # the app shell: installable before sign-in
              "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png"}       # reachable while locked (plus the page's scripts in /js/)
PUBLIC_POST = {"/api/unlock", "/api/profiles/create", "/api/recover"}


class App:
    def __init__(self, port: int, lan: bool):
        self.library = Library(cache_dir=store.DATA)
        self.faith = Faith()
        self.brain = Brain(self.library, self.faith)
        self.lock = threading.Lock()
        self.integrity = integrity.check_library(self.library.library_dir)   # tamper check at startup
        self.port = port
        self.lan = lan


class Handler(BaseHTTPRequestHandler):
    app: App = None  # set in serve()
    server_version = "Vanguard"
    sys_version = ""

    def log_message(self, fmt, *args):      # quiet console
        pass

    # ── responses ───────────────────────────────────────────────────────────
    def _headers(self, status: int, ctype: str, length: int, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        for k, v in security.SECURITY_HEADERS.items():
            self.send_header(k, v)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _json(self, value, status: int = 200, extra: dict | None = None) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body), extra)
        self.wfile.write(body)

    def _deny(self, status: int, msg: str) -> None:
        # Read (and throw away) an unread request body first: answering before it's read makes some
        # systems (Windows) reset the connection, so the refusal wouldn't arrive cleanly.
        if not self._body_read:
            self._body_read = True
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if 0 < n <= 25_000_000:
                    self.rfile.read(n)
            except (ValueError, OSError):
                pass
        self.close_connection = True
        self._json({"error": msg}, status)

    # ── request parsing ─────────────────────────────────────────────────────
    def _body(self) -> dict:
        self._body_read = True
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if n <= 0 or n > 25_000_000:
            return {}
        try:
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _query(self) -> dict:
        return {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}

    def _route(self) -> str:
        return urllib.parse.urlparse(self.path).path

    def _token(self) -> str | None:
        return security.token_from_cookie(self.headers.get("Cookie"))

    _ctx = None
    _kctx = None
    _cctx = None
    _pid = None
    _body_read = False

    def _checks(self, method: str, route: str) -> bool:
        """Common security checks. Sends the refusal itself and returns False when a request is refused.
        On success, the request runs with the session's profile as the only reachable data folder."""
        self._ctx, self._kctx, self._cctx, self._pid, self._body_read = None, None, None, None, False
        host = self.headers.get("Host")
        if not security.host_ok(host, self.app.port, self.app.lan):
            self._deny(421, "Wrong host.")                  # DNS-rebinding protection
            return False
        if not security.origin_ok(self.headers.get("Origin"), host):
            self._deny(403, "Cross-site request refused.")  # other websites can't command Vanguard
            return False
        if method == "POST" and not (self.headers.get("Content-Type") or "").startswith("application/json"):
            self._deny(415, "Requests must be JSON.")       # forces browsers to preflight, which Vanguard refuses
            return False
        pid = security.session_profile(self._token())
        public = PUBLIC_GET if method == "GET" else PUBLIC_POST
        if route not in public and not pid and not (method == "GET" and route.startswith("/js/") and route.endswith(".js")):
            self._deny(401, "Locked.")
            return False
        if pid:
            self._pid = pid
            self._ctx = store.use_profile(profiles.folder(pid))
            self._kctx = store.use_key(security.session_key(self._token()))   # decrypts this profile only
            self._cctx = store.use_class_key(security.session_class_key(self._token()))
        return True

    def _done(self) -> None:
        if self._cctx is not None:
            store.reset_class_key(self._cctx)
            self._cctx = None
        if self._kctx is not None:
            store.reset_key(self._kctx)
            self._kctx = None
        if self._ctx is not None:
            store.reset_profile(self._ctx)
            self._ctx = None

    # ── methods ─────────────────────────────────────────────────────────────
    def do_OPTIONS(self):                       # no CORS: cross-site preflights always fail
        self._deny(405, "Not allowed.")

    def do_PUT(self):
        self._deny(405, "Not allowed.")

    do_DELETE = do_PATCH = do_PUT

    def do_GET(self):
        r = self._route()
        if not self._checks("GET", r):
            return
        try:
            self._get(r)
        finally:
            self._done()

    def _program_key(self) -> bytes | None:
        """The program private key -- only in an instructor profile's session after the Instructor PIN."""
        if (profiles.get(self._pid or "") or {}).get("kind") != "instructor":
            return None
        return security.session_program_key(self._token())

    def _get(self, r: str):
        q, app = self._query(), self.app
        if r.startswith("/api/instructor/"):            # instructor only: profile role + Instructor PIN this session
            priv = self._program_key()
            if not priv:
                return self._json({"error": "Instructor only. Open Instructor and enter the Instructor PIN."}, 403)
            if r == "/api/instructor/overview":
                return self._json(instructor.overview(priv))
            if r == "/api/instructor/scenarios":
                cadets = [p for p in profiles.all_profiles() if p["kind"] == "cadet"]
                logs = {p["id"]: instructor.read_class_file(priv, p["id"], "scenarios.jsonl", []) for p in cadets}
                return self._json({"scenarios": [{**scenarios.summary(s), "text": scenarios.to_text(s),
                                                  "done": sum(1 for L in logs.values() for e in (L or []) if e.get("scenario") == s["id"])}
                                                 for s in scenarios.all_scenarios()],
                                   "cadets": [{"id": p["id"], "name": p["name"], "count": len(logs[p["id"]] or []),
                                               "shared": logs[p["id"]] is not None} for p in cadets]})
            if r == "/api/instructor/leadership-log":
                pid = str(q.get("id", ""))[:12]
                if (profiles.get(pid) or {}).get("kind") != "cadet":
                    return self._json({"error": "No such Cadet."}, 404)
                log = instructor.read_class_file(priv, pid, "scenarios.jsonl", [])
                return self._json({"shared": log is not None, "entries": list(reversed(log or []))})
            if r == "/api/instructor/train":
                out = []
                for p in profiles.all_profiles():
                    if p["kind"] != "cadet":
                        continue
                    rows = instructor.read_class_file(priv, p["id"], "fitness.jsonl", [])
                    goals = instructor.read_class_file(priv, p["id"], "goals.json", {}) or {}
                    out.append({"id": p["id"], "name": p["name"], "shared": rows is not None,
                                "events": [train.stats(e, rows or [], goals.get(e["id"])) for e in train.events()]})
                return self._json({"events": train.events(), "units": train.UNITS, "cadets": out})
            if r == "/api/instructor/live":
                return self._json(scenarios.live_for_instructor())
            if r == "/api/instructor/lessons":
                return self._json(lessons.for_instructor(priv))
            if r == "/api/instructor/assignment":
                try:
                    return self._json(lessons.details(priv, str(q.get("id", ""))[:12]))
                except ValueError as e:
                    return self._json({"error": str(e)}, 404)
            if r == "/api/instructor/cadet":
                pid = str(q.get("id", ""))[:12]
                if (profiles.get(pid) or {}).get("kind") != "cadet":
                    return self._json({"error": "No such Cadet."}, 404)
                return self._json(instructor.records(priv, pid))
        if r == "/api/train":
            if (profiles.get(self._pid or "") or {}).get("kind") != "cadet":
                return self._json({"events": [], "units": train.UNITS, "not_cadet": True})
            return self._json(train.my_train())
        if r == "/api/scenarios":
            done = {}
            if (profiles.get(self._pid or "") or {}).get("kind") == "cadet":
                for e in scenarios.my_log():
                    done[e["scenario"]] = done.get(e["scenario"], 0) + 1
            return self._json({"scenarios": [{**scenarios.summary(s), "done": done.get(s["id"], 0)}
                                             for s in scenarios.all_scenarios()]})
        if r == "/api/scenario":
            try:
                return self._json(scenarios.for_cadet(scenarios.get(str(q.get("id", ""))[:40])))
            except LookupError as e:
                return self._json({"error": str(e)}, 404)
        if r == "/api/leadership-log":
            return self._json({"entries": scenarios.my_log()})
        if r == "/api/live":
            return self._json(scenarios.live_for_cadet(self._pid or ""))
        if r == "/api/lessons":                          # the signed-in Cadet's own assignments
            if (profiles.get(self._pid or "") or {}).get("kind") != "cadet":
                return self._json({"assignments": []})
            return self._json({"assignments": lessons.my_assignments(self._pid)})
        if r == "/api/lesson":
            try:
                return self._json(lessons.open_lesson(self._pid or "", str(q.get("a", ""))[:12]))
            except LookupError as e:
                return self._json({"error": str(e)}, 404)
        if r == "/api/lock":
            out = {"profiles": [{"id": p["id"], "name": p["name"], "kind": p["kind"],
                                 "has_pin": security.has_pin(p["id"]),
                                 "lockout": security.lockout_remaining(p["id"])} for p in profiles.all_profiles()],
                   "unlocked": bool(self._pid)}
            if self._pid:
                cur = profiles.get(self._pid)
                out.update({"current": {"id": cur["id"], "name": cur["name"]}, "pin_set": security.pin_set(),
                            "idle_minutes": security.idle_minutes(),
                            "encrypted": security.session_key(self._token()) is not None,
                            "has_recovery": security.has_recovery(), "admin_set": security.admin_set()})
            return self._json(out)
        if r == "/api/status":
            return self._json({"engine": engine.status(), "library": app.library.stats(),
                               "profile": store.profile(), "stages": store.STAGES, "log_kinds": store.LOG_KINDS,
                               "lan": app.lan, "voice": voice.available(),
                               "ai_mode": store.ai_mode(), "library_only": store.ai_mode() == "off",
                               "kind": (profiles.get(self._pid) or {}).get("kind", "cadet")})
        if r == "/api/topics":
            prog = app.brain.progress()
            return self._json([{"topic": t, "cards": [{"id": c.id, "title": c.title, "questions": len(c.quiz)} for c in cs],
                                "progress": prog.get(t, {"known": 0, "total": 0})}
                               for t, cs in app.library.topics().items()])
        if r == "/api/card":
            c = app.library.card(q.get("id", ""))
            return self._json({"id": c.id, "title": c.title, "topic": c.topic, "source": c.source, "body": c.body,
                               "verified": c.verified,
                               "quiz": [{"q": a, "a": b} for a, b in c.quiz]} if c else {"error": "not found"},
                              200 if c else 404)
        if r == "/api/quiz":
            try:
                n = max(1, min(50, int(q.get("n", "10") or 10)))
            except ValueError:
                n = 10
            return self._json(app.brain.quiz(q.get("topic", ""), n))
        if r == "/api/log":
            return self._json(store.log_entries())
        if r == "/api/memory":
            return self._json(store.memories())
        if r == "/api/addons":
            return self._json(addons.status())
        if r == "/api/history":
            return self._json(store.history())
        if r == "/api/chats":
            return self._json(store.chat_list())
        if r == "/api/letters":
            return self._json({"contacts": letters.contacts(), "letters": letters.letters()})
        if r == "/api/daily":
            return self._json({"status": daily.daily_status(), "questions": daily.daily_questions(app.brain)})
        if r == "/api/checkin":
            return self._json({"rows": daily.checkins()[:30], "concern": daily.concern(), "sleep": daily.sleep_summary(),
                               "support": daily.support(), "roles": daily.SUPPORT_ROLES})
        if r == "/api/support":
            return self._json(daily.support())
        if r == "/api/pcs":
            return self._json(daily.pcs())
        if r == "/api/bct":
            return self._json(daily.bct())
        if r == "/api/integrity":
            return self._json({**app.integrity, "version": integrity.current_version(),
                               "update_key": integrity.PUBLIC_KEY.exists()})
        if r == "/api/packet":                          # everything for a printed board / counseling packet
            rows = store.log_entries()
            return self._json({"profile": store.profile(), "log": rows, "aft": fitness.history(rows),
                               "exams": exam.history(), "made": time.strftime("%Y-%m-%d")})
        if r == "/api/exam/history":
            return self._json(exam.history())
        if r == "/api/leave":
            return self._json(daily.leave_summary())
        if r == "/api/budget":
            return self._json(daily.budget())
        if r == "/api/pay":
            t = pay.tables()
            return self._json({"grades": pay.grades(), "effective": sorted(set(t.get("effective", {}).values())),
                               "bas_effective": (t.get("bas") or {}).get("effective", "")})
        if r == "/api/les":
            return self._json(pay.les_fields())
        if r == "/api/aft/plan":
            return self._json(fitness.plan(store.log_entries()))
        if r == "/api/aft":
            return self._json({"events": [{"id": e, "help": fitness.EVENT_HELP[e]} for e in fitness.EVENT_ORDER],
                               "note": fitness.STANDARD_NOTE, "source": fitness.score_test({}, 17, "M")["source"]})
        if r == "/api/faith/plans":
            return self._json(daily.plans(app.faith))
        if r == "/api/faith/plan":
            day = q.get("day")
            preferred = [x for x in (store.profile().get("faith_texts") or "").split(",") if x]
            return self._json(daily.plan_day(app.faith, q.get("id", ""), int(day) if day and day.isdigit() else None, preferred))
        if r == "/api/jobs":
            return self._json(careers.search(app.library.library_dir, q.get("q", "")[:100], q.get("area", "")[:60]))
        if r == "/api/books":                            # free, public-domain books on this device
            return self._json(books.shelf())
        if r == "/api/books/read":
            try:
                return self._json(books.read(q.get("id", "")[:40], int(q.get("ch", "0") or 0)))
            except ValueError as e:
                return self._json({"error": str(e)}, 404)
        if r == "/api/books/search":
            return self._json({"hits": books.search(q.get("q", "")[:120])})
        if r == "/api/faith/catalog":
            return self._json({"installed": app.faith.catalog})
        if r == "/api/faith/lookup":
            ids = [x for x in q.get("ids", "").split(",") if x]
            return self._json(app.faith.lookup(q.get("ref", "")[:200], ids, compare=q.get("compare") == "1"))
        if r == "/api/faith/search":
            ids = [x for x in q.get("ids", "").split(",") if x]
            return self._json(app.faith.search(q.get("q", "")[:200], ids))
        if r == "/api/search":
            try:
                k = max(1, min(25, int(q.get("k", "8") or 8)))
            except ValueError:
                k = 8
            hits = app.library.search(q.get("q", "")[:500], k=k)
            touched = set(app.integrity.get("changed", []))
            return self._json([{"source": p.source, "where": p.where, "text": p.text, "score": round(s, 2),
                                 "edition": app.library.edition(p.source),
                                 "changed": any(p.source.endswith(f"({n})") for n in touched)} for s, p in hits])
        return self._static(r)

    def _static(self, r: str):
        name = "index.html" if r in ("/", "") else r.lstrip("/")
        path = (WEB / name).resolve()
        if not path.is_relative_to(WEB) or not path.is_file():   # no path traversal
            return self._deny(404, "Not found.")
        data = path.read_bytes()
        ctype = (mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        if path.suffix in (".html", ".js", ".css"):
            ctype += "; charset=utf-8"
        self._headers(200, ctype, len(data))
        self.wfile.write(data)

    def do_POST(self):
        r = self._route()
        if not self._checks("POST", r):
            return
        try:
            self._post(r)
        finally:
            self._done()

    def _post(self, r: str):
        app, b = self.app, self._body()
        if r == "/api/unlock":
            token, msg = security.unlock(str(b.get("profile", ""))[:12], str(b.get("pin", ""))[:32])
            if not token:
                return self._json({"ok": False, "error": msg}, 401)
            return self._json({"ok": True}, extra={"Set-Cookie": security.cookie_header(token)})
        if r == "/api/profiles/create":
            try:
                kind = profiles.role_of(str(b.get("kind", "cadet")))
                if kind == "instructor":                 # only the Instructor PIN can make an instructor
                    err = security.check_admin(str(b.get("admin", ""))[:32])
                    if err:
                        return self._json({"ok": False, "error": err}, 403)
                    err = security.valid_new_pin(str(b.get("pin", "")))
                    if err:
                        return self._json({"ok": False, "error": "An instructor profile needs its own PIN. " + err}, 400)
                p = profiles.create(str(b.get("name", "")), kind)
            except ValueError as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            pin, code = str(b.get("pin", "")), None
            if pin:
                with security.as_profile(p["id"]):
                    err = security.set_pin(pin)
                    code = None if err else security.make_recovery_code(pin)
                if err:
                    profiles.delete(p["id"])
                    return self._json({"ok": False, "error": err}, 400)
            token, _ = security.unlock(p["id"], pin)
            return self._json({"ok": True, "profile": p, "recovery": code},
                              extra={"Set-Cookie": security.cookie_header(token)})
        if r == "/api/recover":
            token, msg, code = security.recover(str(b.get("profile", ""))[:12], str(b.get("code", ""))[:40],
                                                str(b.get("pin", ""))[:32])
            if not token:
                return self._json({"ok": False, "error": msg}, 401)
            return self._json({"ok": True, "recovery": code}, extra={"Set-Cookie": security.cookie_header(token)})
        if r == "/api/lock":
            security.lock(self._token())
            return self._json({"ok": True})
        if r == "/api/profiles/rename":
            try:
                profiles.rename(self._pid, str(b.get("name", "")))
            except ValueError as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            return self._json({"ok": True})
        if r == "/api/profiles/delete":
            if not security.verify_current(str(b.get("pin", ""))):
                return self._json({"ok": False, "error": "Wrong PIN."}, 401)
            pid = self._pid
            self._done()
            security.end_sessions(pid)
            profiles.delete(pid)
            return self._json({"ok": True})
        if r == "/api/pin/set":
            err = security.set_pin(str(b.get("new", "")), str(b.get("current", "")))
            if err:
                return self._json({"ok": False, "error": err}, 400)
            code = None if security.has_recovery() else security.make_recovery_code(str(b.get("new", "")))
            security.end_sessions(self._pid)                         # sign out other sessions of this profile
            token, _ = security.unlock(self._pid, str(b.get("new", "")))   # stay signed in here
            return self._json({"ok": True, "recovery": code},
                              extra={"Set-Cookie": security.cookie_header(token)} if token else None)
        if r == "/api/pin/recovery":                     # a new recovery code (replaces the old one)
            code = security.make_recovery_code(str(b.get("pin", ""))[:32])
            return self._json({"recovery": code} if code else {"error": "Wrong PIN."}, 200 if code else 401)
        if r == "/api/pin/remove":
            err = security.remove_pin(str(b.get("current", "")))
            return self._json({"ok": not err, "error": err}, 400 if err else 200)
        if r == "/api/pin/idle":
            return self._json({"idle_minutes": security.set_idle_minutes(b.get("minutes", 15))})
        if r == "/api/chat":
            return self._chat(str(b.get("message", "")))
        if r == "/api/simplify":
            return self._stream(self.app.brain.simplify(str(b.get("text", ""))))
        if r == "/api/voice":
            try:
                rate = int(b.get("rate", 16000))
                if rate not in (8000, 16000):
                    return self._json({"error": "Unsupported audio rate."}, 400)
                if b.get("mode") == "radio":            # 9-line drill: radio words only
                    return self._json(voice.transcribe_radio(str(b.get("audio", "")), rate))
                return self._json({"text": voice.transcribe(str(b.get("audio", "")), rate)})
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 400)
        if r == "/api/quiz/result":
            return self._json(store.record_answer(str(b.get("id", ""))[:80], bool(b.get("correct"))))
        if r == "/api/log":
            if not (b.get("text") or "").strip():
                return self._json({"error": "empty entry"}, 400)
            return self._json(store.add_log(str(b.get("kind", "Note")), str(b.get("text", "")),
                                            str(b.get("date", ""))[:10], str(b.get("score", ""))))
        if r == "/api/log/delete":
            return self._json({"ok": store.delete_log(str(b.get("id", "")))})
        if r == "/api/profile":
            try:
                return self._json(store.save_profile(b))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if r == "/api/memory":
            return self._json({"ok": store.remember(str(b.get("text", "")))})
        if r == "/api/memory/forget":
            return self._json({"ok": store.forget(str(b.get("id", "")))})
        if r == "/api/contacts":
            return self._json(letters.save_contact(b))
        if r == "/api/contacts/delete":
            return self._json({"ok": letters.delete_contact(str(b.get("id", "")))})
        if r == "/api/letters":
            return self._json(letters.save_letter(b))
        if r == "/api/letters/delete":
            return self._json({"ok": letters.delete_letter(str(b.get("id", "")))})
        if r == "/api/letters/check":
            return self._json(letters.opsec_check(str(b.get("text", ""))[:20000]))
        if r == "/api/letters/draft":
            with app.lock:
                text = letters.draft(str(b.get("to", ""))[:80], str(b.get("relation", ""))[:40], str(b.get("notes", ""))[:3000])
            return self._json({"text": text, "flags": letters.opsec_check(text)} if text else
                              {"error": "No AI model is available to draft — you can still write the letter yourself."})
        if r == "/api/backup":                           # always encrypted with the Soldier's backup password
            try:
                sealed = backup.export_sealed((profiles.get(self._pid) or {}).get("kind", "cadet"),
                                              str(b.get("password", ""))[:200])
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            return self._json({"file": sealed, "name": f"vanguard-backup-{time.strftime('%Y-%m-%d')}.json"})
        if r == "/api/restore":
            try:
                out = backup.restore(backup.open_any(b.get("file", b), str(b.get("password", ""))[:200]))
                # a backup can make a profile a cadet or guardian again -- never an instructor
                if out.get("kind") in ("cadet", "guardian") and profiles.get(self._pid)["kind"] != "instructor":
                    profiles.set_kind(self._pid, out["kind"])
                return self._json(out)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if r == "/api/daily/done":
            return self._json(daily.daily_done(int(b.get("right", 0)), int(b.get("total", 10))))
        if r == "/api/checkin":
            try:
                return self._json(daily.add_checkin(b.get("mood", 3), b.get("stress", 3), b.get("sleep", 7), str(b.get("note", ""))))
            except (TypeError, ValueError):
                return self._json({"error": "Check the numbers."}, 400)
        if r == "/api/leave":
            try:
                return self._json(daily.save_leave(b))
            except (TypeError, ValueError):
                return self._json({"error": "Check the dates and numbers."}, 400)
        if r == "/api/budget":
            try:
                return self._json(daily.save_budget(b))
            except (TypeError, ValueError):
                return self._json({"error": "Amounts must be numbers."}, 400)
        if r == "/api/pay":
            try:
                months = int(b.get("months") or 0) + 12 * int(b.get("years") or 0)
                return self._json(pay.estimate(str(b.get("grade", "")), months / 12, months, float(b.get("bah") or 0)))
            except (TypeError, ValueError) as e:
                return self._json({"error": str(e) or "Check the numbers."}, 400)
        if r == "/api/aft/score":
            try:
                return self._json(fitness.score_test(b["raw"] if isinstance(b.get("raw"), dict) else {}, int(b.get("age", 0)), str(b.get("sex", "M")),
                                                     str(b.get("standard", "general"))))
            except (TypeError, ValueError) as e:
                return self._json({"error": str(e) or "Check the numbers."}, 400)
        if r == "/api/drill/time":
            try:
                secs = float(b.get("seconds", 0))
                if not 0 < secs < 3600:
                    raise ValueError
                return self._json(daily.drill_time(str(b.get("drill", "")), secs, bool(b.get("perfect"))))
            except (TypeError, ValueError):
                return self._json({"error": "Bad time."}, 400)
        if r == "/api/pcs":
            return self._json(daily.save_pcs(b))
        if r == "/api/integrity/check":
            app.integrity = integrity.check_library(app.library.library_dir)
            return self._json(app.integrity)
        if r == "/api/books/place":                       # where this Soldier is in a book (per profile)
            try:
                return self._json(books.save_place(str(b.get("id", ""))[:40], int(b.get("ch", 0) or 0)))
            except (ValueError, TypeError) as e:
                return self._json({"error": str(e)}, 400)
        if r in ("/api/train/add", "/api/train/delete", "/api/train/goal"):
            if (profiles.get(self._pid or "") or {}).get("kind") != "cadet":
                return self._json({"error": "Train is for Cadets."}, 403)
            try:
                eid = str(b.get("event", ""))[:12]
                if r == "/api/train/add":
                    train.add_result(eid, b.get("value"), str(b.get("date", ""))[:10], str(b.get("note", "")))
                elif r == "/api/train/delete":
                    train.delete_result(str(b.get("id", ""))[:12])
                else:
                    train.set_goal(eid, b.get("target"), str(b.get("by", ""))[:10])
                return self._json(train.my_train())
            except LookupError as e:
                return self._json({"error": str(e)}, 404)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if r in ("/api/scenario/choose", "/api/scenario/log"):
            try:
                sc = scenarios.get(str(b.get("id", ""))[:40])
                choice = b.get("choice") if isinstance(b.get("choice"), int) else -1
                if r == "/api/scenario/choose":
                    return self._json(scenarios.explain(sc, choice))
                if (profiles.get(self._pid or "") or {}).get("kind") != "cadet":
                    return self._json({"error": "Only Cadets keep a leadership log."}, 403)
                entry = scenarios.log_entry(sc, choice, str(b.get("reasoning", "")), str(b.get("reflection", "")),
                                            str(b.get("learned", "")))
                return self._json({"entry": entry, "all_outcomes": scenarios.all_outcomes(sc)})
            except LookupError as e:
                return self._json({"error": str(e)}, 404)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if r == "/api/live/vote":
            if (profiles.get(self._pid or "") or {}).get("kind") != "cadet":
                return self._json({"error": "Only Cadets vote."}, 403)
            try:
                scenarios.live_vote(self._pid, b.get("choice") if isinstance(b.get("choice"), int) else -1)
                return self._json({"ok": True})
            except LookupError as e:
                return self._json({"error": str(e)}, 404)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if r == "/api/lesson/submit":
            ans = b.get("answers") if isinstance(b.get("answers"), dict) else {}
            try:
                return self._json(lessons.submit(self._pid or "", str(b.get("a", ""))[:12], ans,
                                                 str(b.get("reflection", ""))[:4000]))
            except LookupError as e:
                return self._json({"error": str(e)}, 404)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if r == "/api/instructor/unlock":               # instructor profile + Instructor PIN -> class records
            err = security.unlock_program(self._token(), str(b.get("admin", ""))[:32])
            return self._json({"ok": False, "error": err} if err else {"ok": True}, 403 if err else 200)
        if r.startswith("/api/instructor/"):
            priv = self._program_key()
            if not priv:
                return self._json({"error": "Instructor only. Open Instructor and enter the Instructor PIN."}, 403)
            try:
                if r == "/api/instructor/unit":
                    act = str(b.get("action", ""))
                    if act == "add":
                        return self._json(instructor.add_unit(priv, b.get("name"), str(b.get("kind", "")), str(b.get("parent", ""))[:10]))
                    if act == "rename":
                        instructor.rename_unit(priv, str(b.get("id", ""))[:10], b.get("name"))
                        return self._json({"ok": True})
                    if act == "delete":
                        instructor.delete_unit(priv, str(b.get("id", ""))[:10])
                        return self._json({"ok": True})
                    return self._json({"error": "Choose add, rename or delete."}, 400)
                if r == "/api/instructor/train/event":
                    if b.get("action") == "remove":
                        train.remove_event(str(b.get("id", ""))[:12])
                        return self._json({"ok": True})
                    return self._json(train.add_event(b.get("name"), str(b.get("unit", "")), str(b.get("better", "")),
                                                      b.get("description", "")))
                if r == "/api/instructor/train/record":
                    # test day: the instructor records results for several Cadets into their class records
                    ev = train.event(str(b.get("event", ""))[:12])
                    results = b.get("results") if isinstance(b.get("results"), dict) else {}
                    saved, skipped, errors = [], [], {}
                    for pid, raw in list(results.items())[:200]:
                        pid = str(pid)[:12]
                        if str(raw).strip() == "":
                            continue
                        if (profiles.get(pid) or {}).get("kind") != "cadet":
                            errors[pid] = "Not a Cadet."
                            continue
                        ck, status = instructor.class_key(priv, pid)
                        if status == "waiting":
                            skipped.append(pid)
                            continue
                        try:
                            with security.as_profile(pid, None, ck):
                                train.add_result(ev["id"], raw, str(b.get("date", ""))[:10], "", by="instructor")
                            saved.append(pid)
                        except ValueError as e:
                            errors[pid] = str(e)
                    return self._json({"saved": saved, "skipped": skipped, "errors": errors})
                if r == "/api/instructor/scenario":
                    sid = str(b.get("id", ""))[:40]
                    if b.get("action") == "delete":
                        if not sid.startswith("i-"):
                            return self._json({"error": "Practice scenarios can't be deleted."}, 400)
                        scenarios.delete_custom(sid)
                        return self._json({"ok": True})
                    if sid and not sid.startswith("i-"):
                        sid = ""                          # editing a practice scenario saves your own copy
                    return self._json(scenarios.save_custom(sid, str(b.get("text", ""))[:20000]))
                if r == "/api/instructor/live":
                    act = str(b.get("action", ""))
                    if act == "start":
                        scenarios.live_start(str(b.get("scenario", ""))[:40])
                    elif act == "reveal":
                        scenarios.live_reveal(bool(b.get("on", True)))
                    elif act == "stop":
                        scenarios.live_stop()
                    else:
                        return self._json({"error": "Choose start, reveal or stop."}, 400)
                    return self._json(scenarios.live_for_instructor())
                if r == "/api/instructor/lesson":
                    if b.get("action") == "delete":
                        lessons.delete_lesson(priv, str(b.get("id", ""))[:12])
                        return self._json({"ok": True})
                    return self._json(lessons.save_lesson(priv, b))
                if r == "/api/instructor/assign-lesson":
                    as_list = lambda v: [str(x)[:12] for x in v][:200] if isinstance(v, list) else []
                    return self._json(lessons.assign(priv, str(b.get("lesson", ""))[:12], bool(b.get("everyone")),
                                                     as_list(b.get("units")), as_list(b.get("cadets")),
                                                     str(b.get("due", ""))[:10]))
                if r == "/api/instructor/assignment":
                    if b.get("action") == "delete":
                        lessons.delete_assignment(str(b.get("id", ""))[:12])
                        return self._json({"ok": True})
                    return self._json({"error": "Unknown action."}, 400)
                if r == "/api/instructor/assign":
                    let, pid = b.get("let"), str(b.get("cadet", ""))[:12]
                    out = instructor.assign(priv, pid, None if b.get("unit") is None else str(b.get("unit"))[:10],
                                            None if let in (None, "") else int(let))
                    if b.get("unit"):                    # joining a unit brings that unit's assignments, to this Cadet only
                        out = {**out, "new_assignments": lessons.sync_cadet(priv, pid)}
                    return self._json(out)
            except (ValueError, TypeError) as e:
                return self._json({"error": str(e)}, 400)
            return self._json({"error": "Unknown instructor action."}, 404)
        if r == "/api/admin/ai-mode":                    # device-wide AI setting -> Instructor PIN
            err = security.check_admin(str(b.get("admin", ""))[:32])
            if err:
                return self._json({"error": err}, 403)
            mode = str(b.get("mode", ""))
            if mode not in store.AI_MODES:
                return self._json({"error": "Choose off, library or ai."}, 400)
            store.save_config({"ai_mode": mode})
            return self._json({"ok": True, "ai_mode": mode})
        if r == "/api/admin/pin":
            err = security.set_admin_pin(str(b.get("new", "")), str(b.get("current", "")))
            return self._json({"ok": False, "error": err} if err else {"ok": True}, 400 if err else 200)
        if r == "/api/update":
            err = security.check_admin(str(b.get("admin", "")))
            if err:
                return self._json({"error": err}, 403)
            if not integrity.PUBLIC_KEY.exists():
                return self._json({"error": "This copy of Vanguard has no release key, so it can't verify updates. "
                                            "The publisher sets one up with tools/sign.py keygen."}, 400)
            try:
                raw = base64.b64decode(str(b.get("zip", "")), validate=True)
                with app.lock:
                    return self._json(integrity.install_update(raw, str(b.get("sig", ""))[:500]))
            except (ValueError, binascii.Error) as e:
                return self._json({"error": str(e)}, 400)
        if r == "/api/exam/start":
            try:
                return self._json(exam.start(app.library, str(b.get("topic", ""))[:80], int(b.get("n") or 10)))
            except (TypeError, ValueError) as e:
                return self._json({"error": str(e) or "Couldn't start the exam."}, 400)
        if r == "/api/exam/submit":
            try:
                return self._json(exam.submit(str(b.get("id", "")), b.get("answers") if isinstance(b.get("answers"), dict) else {}))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if r == "/api/bct":
            return self._json(daily.save_bct(str(b.get("start", ""))))
        if r == "/api/support":
            return self._json(daily.save_support(b.get("contacts") if isinstance(b.get("contacts"), list) else []))
        if r == "/api/board/grade":
            with app.lock:                               # may use the AI model
                return self._json(board.grade(str(b.get("q", ""))[:500], str(b.get("a", ""))[:800], str(b.get("answer", ""))))
        if r == "/api/board/recite":
            return self._json(board.recite(str(b.get("text", ""))[:5000]))
        if r == "/api/faith/plan/done":
            return self._json(daily.plan_mark(str(b.get("id", ""))[:40], int(b.get("day", 0))))
        if r == "/api/chats/new":
            return self._json({"id": store.new_chat()["id"]})
        if r == "/api/chats/open":
            try:
                return self._json({"messages": store.open_chat(str(b.get("id", "")))})
            except KeyError:
                return self._json({"error": "No such conversation."}, 404)
        if r == "/api/chats/rename":
            return self._json({"ok": store.rename_chat(str(b.get("id", "")), str(b.get("title", ""))[:80])})
        if r == "/api/chats/delete":
            return self._json({"ok": store.delete_chat(str(b.get("id", "")))})
        if r == "/api/addons/install":                   # offline AI / voice: changes the device -> Instructor PIN
            err = security.admin_set() and security.check_admin(str(b.get("admin", "")))
            if err:
                return self._json({"error": err}, 403)
            try:
                return self._json(addons.install(str(b.get("name", ""))))
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
        if r == "/api/quit":                             # Me -> Quit Vanguard (there's no console window to close)
            self._json({"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return None
        if r == "/api/history/clear":
            store.clear_history()
            return self._json({"ok": True})
        if r == "/api/library/reload":
            err = security.admin_set() and security.check_admin(str(b.get("admin", "")))
            if err:
                return self._json({"error": err}, 403)
            app.library.load()
            app.faith.reload()
            return self._json(app.library.stats())
        self._deny(404, "Not found.")

    def _chat(self, message: str):
        family = (profiles.get(self._pid) or {}).get("kind") == "guardian"
        return self._stream(self.app.brain.chat(message[:4000], family))

    def _stream(self, events):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        for k, v in security.SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            with self.app.lock:              # one answer at a time on small hardware
                for event in events:
                    self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def serve(host: str = "127.0.0.1", port: int = 8765, lan: bool = False) -> ThreadingHTTPServer:
    profiles.migrate_legacy()
    if lan and not security.all_have_pins():
        raise SystemExit("LAN mode needs every profile to have a PIN. Set them in Me → Security, then use --lan.")
    Handler.app = App(port, lan)
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    if not os.environ.get("VANGUARD_NO_WARMUP"):          # load the AI while the Soldier picks a profile
        threading.Thread(target=lambda: (addons.start_ollama(), engine.warm_up()), daemon=True).start()
    return httpd
