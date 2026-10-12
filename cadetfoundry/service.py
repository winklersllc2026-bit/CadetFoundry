"""
Serve (Phase 7): service learning -- projects, hours, roles, reflections, and the instructor's verification.

  * A Cadet's entries live in their class records (service.jsonl, store.CLASS_FILES): the Cadet and the instructor can
    read them, nobody else.
  * The instructor can post program service projects (program/service_projects.json) for Cadets to pick.
  * Each entry is pending until the instructor verifies it or returns it with a note. A verified entry is locked:
    the Cadet can no longer edit or delete it (the instructor can un-verify it if something was wrong).
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

from cadetfoundry import store

LOG = "service.jsonl"
DEFAULT_REFLECTION = "What did I learn from this, and about working with my team?"
_lock = threading.Lock()


# ── program projects (the instructor's list) ────────────────────────────────
def _projects_path():
    return store.DATA / "program" / "service_projects.json"


def projects() -> list[dict]:
    try:
        return json.loads(_projects_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_projects(rows: list[dict]) -> None:
    path = _projects_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows), encoding="utf-8")
    tmp.replace(path)


def add_project(title, organization="", date="", hours="", description="") -> dict:
    title = " ".join(str(title or "").split())[:80]
    if not title:
        raise ValueError("Name the project.")
    if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
        raise ValueError("Date as YYYY-MM-DD.")
    with _lock:
        rows = projects()
        if len(rows) >= 200:
            raise ValueError("Up to 200 projects.")
        pr = {"id": uuid.uuid4().hex[:8], "title": title, "organization": " ".join(str(organization or "").split())[:80],
              "date": str(date or ""), "hours": _hours(hours) if str(hours or "").strip() else None,
              "description": str(description or "").strip()[:500]}
        _save_projects(rows + [pr])
    return pr


def remove_project(pid: str) -> None:
    """Removes it from the pick list; Cadets' entries keep the project's name."""
    with _lock:
        _save_projects([p for p in projects() if p["id"] != pid])


# ── values ──────────────────────────────────────────────────────────────────
def _hours(raw) -> float:
    try:
        h = float(str(raw).strip())
    except ValueError:
        raise ValueError("Hours as a number, like 4 or 2.5.") from None
    if not 0.25 <= h <= 24:
        raise ValueError("Hours for one day of service: between 0.25 and 24.")
    return round(h * 4) / 4                          # quarter hours


def _date(raw) -> str:
    d = str(raw or "").strip() or time.strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        raise ValueError("Date as YYYY-MM-DD.")
    if d > time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400)):
        raise ValueError("Log service after you've done it — that date is in the future.")
    return d


def _clean(data: dict, existing: dict | None = None) -> dict:
    pid = str(data.get("project_id") or "")[:8]
    pr = next((p for p in projects() if p["id"] == pid), None) if pid else None
    title = pr["title"] if pr else " ".join(str(data.get("project") or "").split())[:80]
    if not title:
        raise ValueError("Name the project, or pick one your instructor posted.")
    reflection = str(data.get("reflection") or "").strip()[:2000]
    if not reflection:
        raise ValueError("Write your reflection: " + DEFAULT_REFLECTION)
    org = " ".join(str(data.get("organization") or (pr or {}).get("organization") or "").split())[:80]
    return {"project": title, "project_id": pr["id"] if pr else "", "organization": org,
            "date": _date(data.get("date") or (pr or {}).get("date")), "hours": _hours(data.get("hours")),
            "role": " ".join(str(data.get("role") or "").split())[:60], "reflection": reflection}


# ── the active Cadet's log (inside their session, or with their class key) ──
def entries() -> list[dict]:
    return store.read_lines(LOG)


def add(data: dict) -> dict:
    row = {"id": uuid.uuid4().hex[:10], **_clean(data), "status": "pending", "logged": time.strftime("%Y-%m-%d")}
    with _lock:
        rows = store.read_lines(LOG)
        if len(rows) >= 1000:
            raise ValueError("That's a lot of service! The log holds 1,000 entries.")
        store.write_lines(LOG, rows + [row])
    return row


def edit(eid: str, data: dict) -> dict:
    with _lock:
        rows = store.read_lines(LOG)
        row = next((r for r in rows if r["id"] == eid), None)
        if not row:
            raise LookupError("No such entry.")
        if row["status"] == "verified":
            raise ValueError("Your instructor verified this entry, so it's locked.")
        row.update(_clean(data, row))
        row.update({"status": "pending", "note": ""})   # an edited entry goes back for review
        store.write_lines(LOG, rows)
    return row


def delete(eid: str) -> None:
    with _lock:
        rows = store.read_lines(LOG)
        row = next((r for r in rows if r["id"] == eid), None)
        if not row:
            raise LookupError("No such entry.")
        if row["status"] == "verified":
            raise ValueError("Your instructor verified this entry, so it's locked.")
        store.write_lines(LOG, [r for r in rows if r["id"] != eid])


def review(eid: str, action: str, note: str = "") -> dict:
    """The instructor's decision on one entry (call with that Cadet's class key in context)."""
    if action not in ("verify", "return", "unverify"):
        raise ValueError("Choose verify, return or unverify.")
    note = str(note or "").strip()[:500]
    if action == "return" and not note:
        raise ValueError("Say what to fix when you return an entry.")
    with _lock:
        rows = store.read_lines(LOG)
        row = next((r for r in rows if r["id"] == eid), None)
        if not row:
            raise LookupError("No such entry.")
        row["status"] = {"verify": "verified", "return": "returned", "unverify": "pending"}[action]
        row["note"] = note
        row["reviewed"] = time.strftime("%Y-%m-%d")
        store.write_lines(LOG, rows)
    return row


def totals(rows: list[dict]) -> dict:
    v = [r for r in rows if r.get("status") == "verified"]
    p = [r for r in rows if r.get("status") == "pending"]
    return {"verified_hours": sum(r["hours"] for r in v), "pending_hours": sum(r["hours"] for r in p),
            "entries": len(rows), "projects": len({r["project"].lower() for r in v}),
            "returned": sum(1 for r in rows if r.get("status") == "returned")}


def mine() -> dict:
    rows = sorted(entries(), key=lambda r: (r["date"], r["id"]), reverse=True)
    return {"entries": rows, "totals": totals(rows), "projects": projects(), "prompt": DEFAULT_REFLECTION}
