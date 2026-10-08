"""
Download Recruit's free books into books/ (run once on a computer with internet, like fetch_library.py).

    python tools/fetch_books.py

  * Classics and the Federalist Papers: public-domain texts from Project Gutenberg, saved whole -- the
    Project Gutenberg license stays in each file; Recruit only hides it when showing the book.
  * The Declaration, Constitution and Bill of Rights: the National Archives transcriptions (archives.gov).
  * American Military History, Volumes I and II (U.S. Army Center of Military History): history.army.mil
    blocks scripted downloads, so save the two PDFs into books/ from a browser (links printed below) and
    run this again -- they're converted to text once.

Each book's SHA-256 goes into books/catalog.json, next to where it came from.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from recruit.books import BOOKS_DIR, CATALOG  # noqa: E402
import fetch_library  # noqa: E402  (shared download + PDF/HTML conversion helpers)


def _gutenberg(book: dict) -> str:
    raw = fetch_library._get(f"https://www.gutenberg.org/cache/epub/{book['pg']}/pg{book['pg']}.txt", 120)
    text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
    if "*** START OF" not in text or f"#{book['pg']}" not in text[:3000]:
        raise RuntimeError("that wasn't the expected Project Gutenberg text")
    return text


def _archives(book: dict) -> str:
    md = fetch_library._html_to_markdown(fetch_library._decode(fetch_library._get(book["url"], 60)))
    lines = md.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip().startswith("Note: The following text is a transcription")), None)
    end = next((i for i, l in enumerate(lines) if l.strip().startswith("Back to Main")), None)
    if start is None or end is None or end <= start:
        raise RuntimeError("the transcript wasn't where expected on the page")
    body = "\n".join(lines[start:end]).strip()
    return f"{book['title']}\n\nSource: National Archives, {book['url']}\n\n{body}\n"


def _pdf(book: dict) -> str | None:
    pdf = BOOKS_DIR / book["file"]
    if not pdf.exists():
        return None
    import cmh_convert                                     # the Army history PDFs have their own converter
    text = cmh_convert.convert(pdf, book["title"], cmh_convert.dictionary(BOOKS_DIR))
    return text.replace(f"{book['title']}\n\n", f"{book['title']}\n\nSource: {book['url']}\n\n", 1)


def main() -> int:
    BOOKS_DIR.mkdir(exist_ok=True)
    catalog_path = BOOKS_DIR / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        catalog = {}
    got, waiting, failed = [], [], []
    for book in CATALOG:
        out = BOOKS_DIR / f"{book['id']}.txt"
        try:
            if book["kind"] == "pdf":
                if out.exists() and out.stat().st_mtime >= (BOOKS_DIR / book["file"]).stat().st_mtime \
                        if (BOOKS_DIR / book["file"]).exists() else out.exists():
                    print(f"  ✓ {book['title']} (already converted)")
                    continue
                text = _pdf(book)
                if text is None:
                    waiting.append(book)
                    continue
            elif out.exists():
                print(f"  ✓ {book['title']} (already here)")
                continue
            else:
                text = _gutenberg(book) if book["kind"] == "gutenberg" else _archives(book)
                time.sleep(1)                                   # be polite to the sites
            out.write_text(text, encoding="utf-8")
            catalog[book["id"]] = {"title": book["title"], "source": book["url"], "license": book.get("license", ""),
                                   "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                                   "fetched": time.strftime("%Y-%m-%d")}
            got.append(book["title"])
            print(f"  ✓ {book['title']} ({len(text) // 1000} KB)")
        except Exception as e:
            failed.append(f"{book['title']}: {e}")
            print(f"  ✗ {book['title']}: {e}")
    catalog_path.write_text(json.dumps(catalog, indent=1), encoding="utf-8")
    if waiting:
        print("\nTo add the Army's history books, open each page in a browser, click Download PDF, and save the file")
        print(f"into {BOOKS_DIR} with the name shown. Then run this again.")
        for b in waiting:
            print(f"  {b['file']:<10} {b['title']}\n             {b['page']}")
    print(f"\n{len(got)} added, {len(waiting)} waiting for a PDF, {len(failed)} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
