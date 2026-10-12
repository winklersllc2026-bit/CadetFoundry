"""
The official-video pack for installed copies (owner, 2026-10-12): the DVIDS videos saved in videos/ go to Cloudflare R2,
and an instructor's copy downloads them from Me -> Add-ons -> Official videos with their access code.

    python tools/video_pack.py make       split the videos into pieces + write the signed list (site/dist-videos/)
    python tools/video_pack.py upload     make, then upload to R2 whatever isn't there yet (needs wrangler login)

Each video is cut into pieces of at most 64 MB (wrangler uploads one file up to about 300 MB; pieces also let a broken
download pick up where it stopped). manifest.json lists every video, piece and SHA-256, plus DVIDS's status (videos
DVIDS removed are deleted on devices too -- its API caching terms). The list is signed with the release key, so a
device only accepts videos this project published. Run tools/fetch_videos.py first to bring videos/ up to date.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site"))
sys.path.insert(0, str(ROOT / "tools"))
from cadetfoundry import videos  # noqa: E402

OUT = ROOT / "site" / "dist-videos"
PIECE = 64 * 2**20
KEY = Path.home() / ".vanguard-release" / "release_key.pem"           # tools/sign.py keygen puts it here
UPLOADED = Path.home() / ".cadetfoundry-site" / "video_pack_uploaded.json"   # pieces already in R2 (by SHA-256)


def make(src: Path = videos.VIDEOS, out: Path = OUT, key=None) -> dict:
    """Split every catalog video saved in src into out/, write out/manifest.json (+ .sig when there's a key)."""
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("dvids-*"):
        old.unlink()
    entries, status = [], videos.status()
    for v in videos.catalog():
        f = src / f"{v['id']}.mp4"
        if v.get("kind") != "dvids" or not f.is_file() or (status.get(v["id"]) or {}).get("removed"):
            continue
        whole, pieces = hashlib.sha256(), []
        with open(f, "rb") as fh:
            n = 0
            while chunk := fh.read(PIECE):
                name = f"{v['id']}.mp4.{n}"
                (out / name).write_bytes(chunk)
                whole.update(chunk)
                pieces.append({"name": name, "bytes": len(chunk), "sha256": hashlib.sha256(chunk).hexdigest()})
                n += 1
        entries.append({"id": v["id"], "bytes": f.stat().st_size, "sha256": whole.hexdigest(), "pieces": pieces})
    manifest = {"made": time.strftime("%Y-%m-%d"), "videos": entries, "status": status}
    data = json.dumps(manifest, indent=1, sort_keys=True).encode("utf-8")
    (out / "manifest.json").write_bytes(data)
    if key is not None:
        import base64
        (out / "manifest.json.sig").write_text(base64.b64encode(key.sign(data)).decode() + "\n")
    return manifest


def _put(name: str, ctype: str) -> bool:
    import build
    r = subprocess.run(f'npx --yes wrangler@{build.WRANGLER} r2 object put "{build.BUCKET}/videos/{name}" '
                       f'--file "{OUT / name}" --content-type {ctype} --remote', cwd=ROOT / "site", shell=True)
    return r.returncode == 0


def upload() -> int:
    if not KEY.exists():
        print("The release key isn't on this computer, so the video list can't be signed (devices would refuse it).")
        return 1
    import sign
    manifest = make(key=sign.load_key(KEY))
    if not manifest["videos"]:                    # never replace the list online with an empty one
        print(f"No videos found in {videos.VIDEOS}. Run python tools/fetch_videos.py first. Nothing was uploaded.")
        return 1
    total = sum(v["bytes"] for v in manifest["videos"])
    print(f"{len(manifest['videos'])} videos, {total / 2**30:.2f} GB, in {sum(len(v['pieces']) for v in manifest['videos'])} pieces")
    try:
        done = set(json.loads(UPLOADED.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        done = set()
    for v in manifest["videos"]:
        for p in v["pieces"]:
            tag = f"{p['name']}:{p['sha256']}"
            if tag in done:
                continue
            print(f"uploading {p['name']} ({p['bytes'] / 2**20:.0f} MB)")
            if not _put(p["name"], "application/octet-stream"):
                print("Upload stopped. Run the same command again to carry on.")
                return 1
            done.add(tag)
            UPLOADED.parent.mkdir(parents=True, exist_ok=True)
            UPLOADED.write_text(json.dumps(sorted(done)), encoding="utf-8")
    # the list goes last, so a device never sees a video whose pieces aren't all there yet
    for name in ("manifest.json.sig", "manifest.json"):
        if not _put(name, "application/json" if name.endswith(".json") else "text/plain"):
            return 1
    print("Done. Instructors get the videos from Me -> Add-ons -> Official videos, with their access code.")
    return 0


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    if argv[:1] == ["make"]:
        m = make()
        print(f"Wrote {OUT}: {len(m['videos'])} videos (not signed -- 'upload' signs it)")
        return 0
    if argv[:1] == ["upload"]:
        return upload()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
