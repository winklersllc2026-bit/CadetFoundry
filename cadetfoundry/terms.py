"""
The Terms of use and Privacy notice (cadetfoundry/legal/*.md, inside the app folder so every updater accepts them).

Setting up Cadet Foundry needs a ticked "I agree" box; the acceptance (which version, and the date -- nothing about who) is
kept in this computer's config.json. A new VERSION asks again: on first-run setup, or on the instructor's Home.
"""
from __future__ import annotations

import time
from pathlib import Path

from cadetfoundry import store

VERSION = "2026-10-13"            # access codes, copyright and copying (2026-10-12: no online AI, Cadet drives)
DIR = Path(__file__).resolve().parent / "legal"
DOCS = {"terms": "TERMS.md", "privacy": "PRIVACY.md", "notice": "NOTICE.txt"}


def text(doc: str) -> str | None:
    name = DOCS.get(doc)
    if not name:
        return None
    try:
        return (DIR / name).read_text(encoding="utf-8")
    except OSError:
        return None


def accepted() -> bool:
    t = store.config().get("terms")
    return isinstance(t, dict) and t.get("version") == VERSION


def accept() -> dict:
    t = {"version": VERSION, "date": time.strftime("%Y-%m-%d")}
    store.save_config({"terms": t})
    return t
