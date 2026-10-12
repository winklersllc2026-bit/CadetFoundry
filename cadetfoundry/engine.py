"""
The AI engine: offline first.

  1. Local model through Ollama (default) -- works with no internet at all.
     Picks the best installed small model (qwen2.5 3B is the target for a handheld).
  2. If it isn't there, a clear message plus the library passages, so the Cadet still gets the official text.

Nothing online, ever (owner, 2026-10-12): the online providers (Groq, Gemini) that an operator could once switch on in
config.json are gone. Cadets are minors; the only AI is the one on this computer, and the only address this file
talks to is Ollama on 127.0.0.1.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Generator

from cadetfoundry import store

OLLAMA = "http://127.0.0.1:11434"
PREFERRED = ("qwen2.5:3b", "llama3.2:3b", "qwen2.5:1.5b", "llama3.2:1b", "llama3.1:8b", "llama3.1")


def _get(url: str, timeout: float = 3):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post(url: str, body: dict, headers: dict | None = None, timeout: float = 60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "CadetFoundry/1",
                                          **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def local_models() -> list[str] | None:
    """Installed Ollama models, or None if Ollama isn't running."""
    try:
        return [m["name"] for m in _get(f"{OLLAMA}/api/tags").get("models", [])]
    except Exception:
        return None


def pick_model() -> str | None:
    tags = local_models()
    if not tags:
        return None
    want = store.config().get("model")
    if want and want in tags:
        return want
    names = set(tags) | {t.split(":")[0] for t in tags}
    for p in PREFERRED:
        if p in names:
            return next((t for t in tags if t == p or t.startswith(p + ":") or t == p + ":latest"), p)
    return next((t for t in tags if "embed" not in t.lower()), None)


def status() -> dict:
    tags = local_models()
    return {
        "ollama": tags is not None,
        "model": pick_model() if tags else None,
        "models": tags or [],
    }


# ── providers ───────────────────────────────────────────────────────────────

def _ollama(messages: list[dict], max_tokens: int) -> Generator[str, None, None]:
    model = pick_model()
    if not model:
        raise RuntimeError("no local model")
    body = {"model": model, "messages": messages, "stream": True, "keep_alive": "30m",
            "options": {"num_predict": min(max_tokens, 700), "num_ctx": 8192, "temperature": 0.3,
                        "repeat_penalty": 1.15}}   # small local models: stay close to the text without looping
    with _post(f"{OLLAMA}/api/chat", body, timeout=600) as r:
        for line in r:
            if not line.strip():
                continue
            chunk = json.loads(line.decode())
            text = chunk.get("message", {}).get("content", "")
            if text:
                yield text
            if chunk.get("done"):
                break




def warm_up() -> bool:
    """Load the offline model into memory now (Ollama keeps it for 30 minutes), so the Soldier's first
    question doesn't wait for it. Safe to call in the background; does nothing if Ollama isn't running."""
    try:
        model = pick_model()
        if not model:
            return False
        with _post(f"{OLLAMA}/api/generate", {"model": model, "prompt": "", "keep_alive": "30m", "stream": False,
                    "options": {"num_ctx": 8192}},          # same context size as answers, or Ollama reloads
                   timeout=300) as r:
            r.read()
        return True
    except Exception:
        return False


def stream(messages: list[dict], max_tokens: int = 1200) -> Generator[str, None, None]:
    """Answer with the AI on this computer (Ollama). There is no other engine."""
    try:
        yielded = False
        for chunk in _ollama(messages, max_tokens):
            yielded = True
            yield chunk
        if yielded:
            return
    except Exception:
        pass
    raise RuntimeError("no AI engine is available")


def quick(messages: list[dict], max_tokens: int = 300) -> str:
    """Small jobs (learning memories, grading). Empty string if no AI is available."""
    try:
        return "".join(stream(messages, max_tokens)).strip()
    except Exception:
        return ""
