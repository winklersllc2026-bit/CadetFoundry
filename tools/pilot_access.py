"""
Access codes for the Cadet Foundry download (owner, 2026-10-12): one code per instructor, so the installer reaches only
the people you approve, and you can see who downloaded and switch a shared code off.

    python tools/pilot_access.py setup                    once: make the R2 bucket and the D1 code list on Cloudflare
    python tools/pilot_access.py new "SFC Rivera, Lincoln High"    a code for one instructor (prints an email to send)
    python tools/pilot_access.py list                     every code: who, uses, last used
    python tools/pilot_access.py revoke <id>              switch a code off (its uses stay in the list)
    python tools/pilot_access.py restore <id>             switch it back on

Cloudflare stores each code only as a SHA-256 hash, with an id, its uses and dates -- never the code or the name.
The names and the codes themselves stay in a file on this computer: ~/.cadetfoundry-site/pilot_codes.json
(keep it private; it's what lets you resend a code or see who a code belongs to). Runs wrangler with npx, signed in
to your Cloudflare account (npx wrangler login).
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
sys.path.insert(0, str(SITE))
import build  # noqa: E402  (the same pinned wrangler version)

DB, BUCKET = "cadetfoundry-pilot", "cadetfoundry-downloads"
LOCAL = Path.home() / ".cadetfoundry-site" / "pilot_codes.json"
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"       # no I, L, O, 0 or 1: easy to read out and type


def norm(code: str) -> str:
    """The same as normCode in site/worker.js."""
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())[:40]


def code_hash(code: str) -> str:
    return hashlib.sha256(norm(code).encode("utf-8")).hexdigest()


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(10))      # 31^10: about 50 bits
    return f"{raw[:5]}-{raw[5:]}"


def wrangler(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = f"npx --yes wrangler@{build.WRANGLER} " + " ".join(args)
    return subprocess.run(cmd, cwd=SITE, shell=True, capture_output=capture, text=True)


def sql(command: str) -> list[dict]:
    r = wrangler("d1", "execute", DB, "--remote", "--json", "--command", json.dumps(command), capture=True)
    if r.returncode != 0:
        raise SystemExit(f"Cloudflare said:\n{r.stdout}\n{r.stderr}")
    out = json.loads(r.stdout[r.stdout.index("["):])
    return out[0].get("results", []) if out else []


def _local() -> dict:
    try:
        return json.loads(LOCAL.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_local(data: dict) -> None:
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    LOCAL.write_text(json.dumps(data, indent=1), encoding="utf-8")


def setup() -> int:
    r = wrangler("r2", "bucket", "create", BUCKET)
    print("R2 bucket:", "made" if r.returncode == 0 else "already there (or see the message above)")
    toml = SITE / "wrangler.toml"
    text = toml.read_text(encoding="utf-8")
    if "REPLACE_WITH_DATABASE_ID" in text:
        r = wrangler("d1", "create", DB, capture=True)
        m = re.search(r'"?database_id"?\s*[=:]\s*"([0-9a-f-]{36})"', r.stdout + r.stderr)
        if not m:
            print(r.stdout, r.stderr)
            print(f"Couldn't read the new database's id. Put it in {toml} in place of REPLACE_WITH_DATABASE_ID.")
            return 1
        toml.write_text(text.replace("REPLACE_WITH_DATABASE_ID", m.group(1)), encoding="utf-8")
        print(f"D1 database {DB}: made ({m.group(1)}), saved in site/wrangler.toml — commit that file.")
    r = wrangler("d1", "execute", DB, "--remote", "--file", "pilot_schema.sql")
    if r.returncode != 0:
        return r.returncode
    print("Ready. Next: python site/build.py --release --deploy, then make codes with:  python tools/pilot_access.py new \"Name\"")
    return 0


def new(label: str) -> int:
    label = " ".join(label.split())[:80]
    if not label:
        print('Give the code a name, e.g.  python tools/pilot_access.py new "SFC Rivera, Lincoln High"')
        return 1
    code, cid = new_code(), secrets.token_hex(3)
    sql(f"INSERT INTO codes (id, hash, created) VALUES ('{cid}', '{code_hash(code)}', '{time.strftime('%Y-%m-%d')}')")
    data = _local()
    data[cid] = {"label": label, "code": code, "created": time.strftime("%Y-%m-%d")}
    _save_local(data)
    print(f"\nAccess code for {label}:  {code}   (id {cid})\n")
    print("— an email you can send —\n")
    print(f"Thank you for joining the Cadet Foundry pilot!\n\n1. Go to https://cadetfoundry.org/download\n"
          f"2. Enter your access code: {code}\n3. Download Cadet Foundry for Windows and run it.\n\n"
          "This code is just for you and your program — please don't share it or the download. Other instructors can "
          "request their own at support@cadetfoundry.org.\n")
    return 0


def list_codes() -> int:
    rows = sql("SELECT id, active, created, uses, last_used FROM codes ORDER BY created")
    names = _local()
    if not rows:
        print("No codes yet. Make one:  python tools/pilot_access.py new \"Name\"")
        return 0
    print(f"{'id':<8}{'who':<34}{'on?':<5}{'made':<12}{'downloads':<11}last download")
    for r in rows:
        who = names.get(r["id"], {}).get("label", "(not on this computer)")
        print(f"{r['id']:<8}{who[:33]:<34}{'yes' if r['active'] else 'OFF':<5}{r['created']:<12}{r['uses']:<11}"
              f"{(r['last_used'] or '-')[:16].replace('T', ' ')}")
    return 0


def set_active(cid: str, on: bool) -> int:
    if not re.fullmatch(r"[0-9a-f]{6}", cid or ""):
        print("Give the code's id from the list (6 letters and numbers).")
        return 1
    sql(f"UPDATE codes SET active = {1 if on else 0} WHERE id = '{cid}'")
    print(f"Code {cid} is {'on' if on else 'off'}. {'' if on else 'It no longer downloads anything; its history stays in the list.'}")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("setup", "new", "list", "revoke", "restore"):
        print(__doc__)
        return 1
    if argv[0] == "setup":
        return setup()
    if argv[0] == "new":
        return new(" ".join(argv[1:]))
    if argv[0] == "list":
        return list_codes()
    return set_active(argv[1] if len(argv) > 1 else "", argv[0] == "restore")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
