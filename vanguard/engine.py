"""
The AI engine: offline first.

  1. Local model through Ollama (default) -- works with no internet at all.
     Picks the best installed small model (qwen2.5 3B is the target for a handheld).
  2. Optional free online keys (Groq, Gemini) when the device has internet and
     the Soldier/admin turned "online" on -- much faster, same library and rules.
  3. If nothing is available, a clear message plus the library passages, so the
     Soldier still gets the official text.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Generator

from vanguard import store

OLLAMA = "http://127.0.0.1:11434"
PREFERRED = ("qwen2.5:3b", "llama3.2:3b", "qwen2.5:1.5b", "llama3.2:1b", "llama3.1:8b", "llama3.1")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = ("qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
GEMINI_MODELS = ("gemini-3.5-flash", "gemini-flash-latest", "gemini-3.1-flash-lite")


def _get(url: str, timeout: float = 3):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
        return json.loads(r.read().decode())


def _post(url: str, body: dict, headers: dict | None = None, timeout: float = 60):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Vanguard/1",
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
    c = store.config()
    tags = local_models()
    return {
        "ollama": tags is not None,
        "model": pick_model() if tags else None,
        "models": tags or [],
        "online_enabled": bool(c.get("online")) and not c.get("pilot_mode"),
        "online_keys": [k for k in ("groq_key", "gemini_key") if c.get(k)],
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


def _groq(messages: list[dict], key: str, max_tokens: int) -> str:
    last = ""
    for model in GROQ_MODELS:
        try:
            with _post(GROQ_URL, {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.4},
                       {"Authorization": f"Bearer {key}"}, 60) as r:
                text = json.loads(r.read().decode())["choices"][0]["message"].get("content") or ""
            if text.strip():
                return text
        except urllib.error.HTTPError as e:
            last = f"{e.code}"
            if e.code in (401, 403):
                break
        except Exception as e:
            last = str(e)
    raise RuntimeError(f"Groq: {last}")


def _gemini(messages: list[dict], key: str, max_tokens: int) -> str:
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages if m["role"] != "system"]
    body = {"contents": contents, "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4}}
    last = ""
    for model in GEMINI_MODELS:
        try:
            with _post(GEMINI_URL.format(m=model), body, {"x-goog-api-key": key}, 25) as r:
                d = json.loads(r.read().decode())
            text = "".join(p.get("text", "") for p in d["candidates"][0]["content"].get("parts", []))
            if text.strip():
                return text
        except urllib.error.HTTPError as e:
            last = f"{e.code}"
            if e.code in (401, 403):
                break
        except Exception as e:
            last = str(e)
    raise RuntimeError(f"Gemini: {last}")


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


def online_ready() -> bool:
    """An instructor/IT operator turned online AI on and gave a provider key (config.json)."""
    c = store.config()
    if c.get("pilot_mode"):                       # Pilot mode keeps every question on this device
        return False
    return bool(c.get("online")) and any(c.get(k) for k in ("groq_key", "gemini_key"))


def stream(messages: list[dict], max_tokens: int = 1200, online: bool = False) -> Generator[str, None, None]:
    """Answer with the first engine that works. On this device (Ollama) unless the CALLER passes online=True and
    online AI is enabled in settings (security review, 2026-10-11): only Ask's ordinary answers opt in, with no
    personal context. Crisis replies, grading (which carries answer keys), memories and letters never go online."""
    c = store.config()
    if online and c.get("online"):
        for key_name, fn in (("groq_key", _groq), ("gemini_key", _gemini)):
            if c.get(key_name):
                try:
                    yield fn(messages, c[key_name], max_tokens)
                    return
                except Exception:
                    continue
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
    """Small jobs (learning memories, grading). On this device only -- never online. Empty string if nothing is
    available."""
    try:
        return "".join(stream(messages, max_tokens, online=False)).strip()
    except Exception:
        return ""
