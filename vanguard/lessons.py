"""
Lessons and assignments (Phase 4).

  * Lessons are written by the instructor. The lesson text, questions and vocabulary are kept in
    program/lessons.json so a Cadet's session can show them; the app never sends a Cadet the answer key or the
    instructor's notes. Notes are sealed with the program key (instructor only).
  * Assignments (program/assignments.json) name the Cadets who get a lesson. Units are resolved to Cadets when the
    instructor assigns, because Cadets can't read the sealed roster.
  * A Cadet's work -- started, answers, score, reflection -- is saved in their own class records
    (assignments.json, a store.CLASS_FILES file), which the instructor can read and nothing else can.

Questions are typed in a plain format that works on a phone:

    Q: Who salutes first?
    * The junior person
    - The senior person
    - Whoever sees the other first

Vocabulary is one "term: definition" per line.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

from vanguard import instructor, profiles, store, vault

MAX_LESSONS, MAX_QUESTIONS, MAX_VOCAB = 300, 25, 30
_lock = threading.Lock()


# ── program files ───────────────────────────────────────────────────────────
def _path(name: str):
    return store.DATA / "program" / name


def _read(name: str, default):
    try:
        return json.loads(_path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(name: str, data) -> None:
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def _notes(priv: bytes) -> dict:
    try:
        raw = _path("lesson_notes.json").read_bytes()
        return json.loads(vault.open_sealed(vault.program_data_key(priv), raw, "lesson_notes.json").decode("utf-8"))
    except (OSError, vault.VaultError, ValueError):
        return {}


def _save_notes(priv: bytes, notes: dict) -> None:
    path = _path("lesson_notes.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(vault.seal(vault.program_data_key(priv), json.dumps(notes).encode("utf-8"), "lesson_notes.json"))
    tmp.replace(path)


def all_lessons() -> list[dict]:
    return _read("lessons.json", [])


def all_assignments() -> list[dict]:
    return _read("assignments.json", [])


# ── parsing what the instructor typed ───────────────────────────────────────
def parse_questions(text: str) -> list[dict]:
    """'Q: ...' then choices: '* right' and '- wrong'. Raises ValueError with a plain message."""
    qs, cur = [], None
    for n, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(?:Q\s*[:.)]|\d+[.)])\s*(.+)$", line, re.I)
        if m:
            cur = {"q": m.group(1).strip()[:300], "choices": [], "answer": None}
            qs.append(cur)
        elif line[0] in "*-•" and cur is not None:
            choice = line[1:].strip()[:200]
            if not choice:
                raise ValueError(f"Line {n}: the choice is empty.")
            if line[0] == "*":
                if cur["answer"] is not None:
                    raise ValueError(f"Question {len(qs)} has more than one correct choice (*).")
                cur["answer"] = len(cur["choices"])
            cur["choices"].append(choice)
        else:
            raise ValueError(f"Line {n}: start a question with 'Q:', the right choice with '*' and others with '-'.")
    for i, q in enumerate(qs, 1):
        if not 2 <= len(q["choices"]) <= 6:
            raise ValueError(f"Question {i} needs 2 to 6 choices.")
        if q["answer"] is None:
            raise ValueError(f"Question {i} needs one correct choice marked with '*'.")
    if len(qs) > MAX_QUESTIONS:
        raise ValueError(f"A lesson can have up to {MAX_QUESTIONS} questions.")
    return qs


def parse_vocab(text: str) -> list[dict]:
    out = []
    for n, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip().lstrip("-*• ").strip()
        if not line:
            continue
        term, sep, definition = line.partition(":")
        if not sep or not term.strip() or not definition.strip():
            raise ValueError(f"Vocabulary line {n}: write it as 'term: definition'.")
        out.append({"term": term.strip()[:80], "definition": definition.strip()[:300]})
    if len(out) > MAX_VOCAB:
        raise ValueError(f"A lesson can have up to {MAX_VOCAB} vocabulary terms.")
    return out


def questions_text(qs: list[dict]) -> str:
    return "\n\n".join("Q: " + q["q"] + "".join(f"\n{'*' if i == q['answer'] else '-'} {c}" for i, c in enumerate(q["choices"]))
                       for q in qs)


def vocab_text(vs: list[dict]) -> str:
    return "\n".join(f"{v['term']}: {v['definition']}" for v in vs)


# ── instructor: lessons ─────────────────────────────────────────────────────
def save_lesson(priv: bytes, data: dict) -> dict:
    title = " ".join(str(data.get("title") or "").split())[:100]
    if not title:
        raise ValueError("Give the lesson a title.")
    let = data.get("let_level")
    let = int(let) if str(let or "").isdigit() else None
    if let is not None and let not in instructor.LET_LEVELS:
        raise ValueError("LET level is 1 to 4.")
    lesson = {
        "title": title, "let_level": let,
        "competency": " ".join(str(data.get("competency") or "").split())[:80],
        "objective": str(data.get("objective") or "").strip()[:500],
        "source": str(data.get("source") or "").strip()[:200],
        "content": str(data.get("content") or "").strip()[:20000],
        "questions": parse_questions(str(data.get("questions") or "")),
        "vocabulary": parse_vocab(str(data.get("vocabulary") or "")),
        "reflection": str(data.get("reflection") or "").strip()[:500],
        "updated": time.strftime("%Y-%m-%d"),
    }
    if not (lesson["content"] or lesson["questions"]):
        raise ValueError("Add some lesson content or at least one question.")
    with _lock:
        ls = all_lessons()
        lid = str(data.get("id") or "")[:12]
        old = next((x for x in ls if x["id"] == lid), None) if lid else None
        if old:
            old.update(lesson)
            lesson = old
        else:
            if len(ls) >= MAX_LESSONS:
                raise ValueError(f"Up to {MAX_LESSONS} lessons.")
            lesson = {"id": uuid.uuid4().hex[:12], "created": time.strftime("%Y-%m-%d"), **lesson}
            ls.append(lesson)
        _write("lessons.json", ls)
        notes = _notes(priv)
        notes[lesson["id"]] = str(data.get("notes") or "").strip()[:5000]
        _save_notes(priv, notes)
    return lesson


def delete_lesson(priv: bytes, lid: str) -> None:
    with _lock:
        if any(a["lesson"] == lid for a in all_assignments()):
            raise ValueError("This lesson is assigned. Remove its assignments first.")
        _write("lessons.json", [x for x in all_lessons() if x["id"] != lid])
        notes = _notes(priv)
        notes.pop(lid, None)
        _save_notes(priv, notes)


def for_instructor(priv: bytes) -> dict:
    notes = _notes(priv)
    ls = [{**x, "notes": notes.get(x["id"], ""), "questions_text": questions_text(x["questions"]),
           "vocabulary_text": vocab_text(x["vocabulary"])} for x in all_lessons()]
    return {"lessons": ls, "assignments": [{**a, **progress(priv, a)} for a in all_assignments()]}


# ── instructor: assignments ─────────────────────────────────────────────────
def assign(priv: bytes, lid: str, everyone: bool = False, units: list | None = None, cadets: list | None = None,
           due: str = "") -> dict:
    lesson = next((x for x in all_lessons() if x["id"] == lid), None)
    if not lesson:
        raise ValueError("No such lesson.")
    if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
        raise ValueError("Due date as YYYY-MM-DD.")
    r = instructor.roster(priv)
    all_cadets = [p["id"] for p in profiles.all_profiles() if p["kind"] == "cadet"]
    units = [u for u in (units or []) if any(x["id"] == u for x in r["units"])]
    # a unit includes its sub-units (a platoon's squads)
    wanted, frontier = set(units), list(units)
    while frontier:
        parent = frontier.pop()
        for u in r["units"]:
            if u["parent"] == parent and u["id"] not in wanted:
                wanted.add(u["id"])
                frontier.append(u["id"])
    chosen = set(all_cadets) if everyone else set()
    chosen |= {pid for pid, meta in r["cadets"].items() if meta.get("unit") in wanted and pid in all_cadets}
    chosen |= {c for c in (cadets or []) if c in all_cadets}
    if not chosen and not everyone and not wanted:
        raise ValueError("Choose who gets this lesson: everyone, a unit, or individual Cadets.")
    names = [u["name"] for u in r["units"] if u["id"] in units]
    with _lock:
        rows = all_assignments()
        # Never the same lesson twice on one Cadet's list: anyone who already has it is left out of the new one.
        have = {pid for x in rows if x["lesson"] == lid for pid in recipients(x)}
        if everyone and any(x["lesson"] == lid and x.get("everyone") for x in rows):
            raise ValueError("Everyone already has this lesson.")
        new = chosen - have
        covered = {u for x in rows if x["lesson"] == lid for u in x.get("units", [])}
        if not new and not everyone and set(wanted) <= covered:
            raise ValueError("Everyone you chose already has this lesson. Cadets who join a unit later get it automatically.")
        a = {"id": uuid.uuid4().hex[:12], "lesson": lid, "title": lesson["title"], "cadets": sorted(new), "due": due,
             "everyone": bool(everyone), "units": sorted(wanted),
             "to": "Everyone" if everyone else ", ".join(names + ([f"{len(cadets or [])} Cadet(s)"] if cadets else [])),
             "created": time.strftime("%Y-%m-%d")}
        rows.append(a)
        _write("assignments.json", rows)
    return a


def recipients(a: dict) -> list[str]:
    """Who has this assignment now. 'Everyone' means every current Cadet, including ones added later."""
    if a.get("everyone"):
        return [p["id"] for p in profiles.all_profiles() if p["kind"] == "cadet"]
    return a["cadets"]


def sync_cadet(priv: bytes, pid: str) -> list[str]:
    """A Cadet just joined a unit: give them that unit's existing assignments -- once, and only them. Other Cadets'
    lists don't change. A lesson they already have from another assignment isn't added again."""
    unit = (instructor.roster(priv)["cadets"].get(pid) or {}).get("unit")
    if not unit:
        return []
    added = []
    with _lock:
        rows = all_assignments()
        have = {x["lesson"] for x in rows if pid in recipients(x)}
        for a in rows:
            if unit in a.get("units", []) and a["lesson"] not in have:
                a["cadets"] = sorted(set(a["cadets"]) | {pid})
                have.add(a["lesson"])
                added.append(a["id"])
        if added:
            _write("assignments.json", rows)
    return added


def delete_assignment(aid: str) -> None:
    with _lock:
        _write("assignments.json", [a for a in all_assignments() if a["id"] != aid])


def _work(priv: bytes, pid: str) -> dict | None:
    """One Cadet's saved lesson work, through their class key (None if not readable yet)."""
    ck, status = instructor.class_key(priv, pid)
    if status == "waiting":
        return None
    from vanguard import security
    with security.as_profile(pid, None, ck):
        return store.read_json("assignments.json", {})


def progress(priv: bytes, a: dict) -> dict:
    who = recipients(a)
    counts = {"assigned": len(who), "complete": 0, "in_progress": 0, "not_started": 0, "unknown": 0}
    for pid in who:
        w = _work(priv, pid)
        if w is None:
            counts["unknown"] += 1
            continue
        st = (w.get(a["id"]) or {}).get("state", "not_started")
        counts[st if st in counts else "not_started"] += 1
    return counts


def details(priv: bytes, aid: str) -> dict:
    a = next((x for x in all_assignments() if x["id"] == aid), None)
    if not a:
        raise ValueError("No such assignment.")
    rows = []
    for pid in recipients(a):
        p = profiles.get(pid)
        if not p:
            continue
        w = _work(priv, pid)
        mine = (w or {}).get(aid) or {}
        rows.append({"id": pid, "name": p["name"], "state": "unknown" if w is None else mine.get("state", "not_started"),
                     "score": mine.get("score"), "total": mine.get("total"), "completed": mine.get("completed", ""),
                     "reflection": mine.get("reflection", "")})
    return {"assignment": a, "cadets": rows}


# ── Cadet ───────────────────────────────────────────────────────────────────
def _mine(pid: str, aid: str) -> tuple[dict, dict]:
    a = next((x for x in all_assignments() if x["id"] == aid and pid in recipients(x)), None)
    lesson = a and next((x for x in all_lessons() if x["id"] == a["lesson"]), None)
    if not a or not lesson:
        raise LookupError("No such assignment.")       # also when it's someone else's: never confirm it exists
    return a, lesson


def my_assignments(pid: str) -> list[dict]:
    """The active Cadet's assignments (call inside their session: their class records are read)."""
    work = store.read_json("assignments.json", {})
    out = []
    for a in all_assignments():
        if pid not in recipients(a):
            continue
        w = work.get(a["id"]) or {}
        out.append({"id": a["id"], "title": a["title"], "due": a["due"], "state": w.get("state", "not_started"),
                    "score": w.get("score"), "total": w.get("total")})
    out.sort(key=lambda x: (x["state"] == "complete", x["due"] or "9999"))
    return out


def open_lesson(pid: str, aid: str) -> dict:
    """The lesson as a Cadet sees it -- no answer key, no instructor notes. Marks it started."""
    a, lesson = _mine(pid, aid)
    with _lock:
        work = store.read_json("assignments.json", {})
        w = work.setdefault(aid, {"state": "not_started"})
        if w["state"] == "not_started":
            w.update({"state": "in_progress", "started": time.strftime("%Y-%m-%d")})
            store.write_json("assignments.json", work)
    shown = {k: lesson[k] for k in ("title", "let_level", "competency", "objective", "source", "content", "vocabulary",
                                    "reflection")}
    shown["questions"] = [{"q": q["q"], "choices": q["choices"]} for q in lesson["questions"]]
    out = {"assignment": {"id": aid, "due": a["due"]}, "lesson": shown, "work": w}
    if w.get("state") == "complete":                   # after submitting, the Cadet may see what was right
        out["answers"] = [q["answer"] for q in lesson["questions"]]
    return out


def submit(pid: str, aid: str, answers: dict, reflection: str) -> dict:
    a, lesson = _mine(pid, aid)
    if lesson["reflection"] and not (reflection or "").strip():
        raise ValueError("Write your reflection before you submit.")
    chosen, right = [], 0
    for i, q in enumerate(lesson["questions"]):
        try:
            c = int(answers.get(str(i)))
        except (TypeError, ValueError):
            c = None
        if c is None or not 0 <= c < len(q["choices"]):
            raise ValueError(f"Answer question {i + 1}.")
        chosen.append(c)
        right += c == q["answer"]
    with _lock:
        work = store.read_json("assignments.json", {})
        w = work.setdefault(aid, {})
        if w.get("state") == "complete":
            raise ValueError("You've already submitted this lesson.")
        w.update({"state": "complete", "completed": time.strftime("%Y-%m-%d"), "answers": chosen, "score": right,
                  "total": len(lesson["questions"]), "reflection": (reflection or "").strip()[:4000],
                  "started": w.get("started") or time.strftime("%Y-%m-%d")})
        store.write_json("assignments.json", work)
    return {"score": right, "total": len(lesson["questions"]), "answers": [q["answer"] for q in lesson["questions"]],
            "chosen": chosen}
