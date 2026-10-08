"""
Download official PUBLIC documents into library/ (needs internet once).

    python tools/fetch_library.py           everything below
    python tools/fetch_library.py --list
    python tools/fetch_library.py --check   is a newer edition out? (downloads nothing)

Sources are official U.S. Government sites. Army publications come from the Army
Publishing Directorate when it can be reached; anything that can't be downloaded
automatically is listed at the end so it can be added by hand (see LIBRARY.md).
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "library"
UA = {"User-Agent": "Mozilla/5.0 (Cursiv Recruit library installer)"}


def _get(url: str, timeout: int = 120, tries: int = 3) -> bytes:
    for attempt in range(tries):        # big government PDFs sometimes drop mid-download
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except (OSError, urllib.error.URLError):
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))


def _html_to_markdown(raw: str) -> str:
    """Turn a GPO U.S. Code HTML page into Markdown with one heading per section,
    so each UCMJ article is its own searchable passage."""
    raw = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    raw = re.sub(r"(?is)<h3[^>]*class=\"section-head\"[^>]*>(.*?)</h3>", lambda m: "\n\n## " + m.group(1) + "\n\n", raw)
    raw = re.sub(r"(?is)<h[1-6][^>]*>(.*?)</h[1-6]>", lambda m: "\n\n### " + m.group(1) + "\n\n", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", "", raw))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    # Keep the law itself; drop the long editorial/amendment notes after each section
    parts = re.split(r"(?m)^(?=## )", text)
    keep = []
    for p in parts:
        p = re.split(r"(?m)^### (Editorial Notes|Statutory Notes|Amendments|Historical and Revision Notes)", p)[0]
        keep.append(p.strip())
    return "\n\n".join(k for k in keep if k)


def ucmj() -> str:
    last = None
    for year in (2024, 2023, 2022):
        try:
            raw = _get(f"https://www.govinfo.gov/content/pkg/USCODE-{year}-title10/html/"
                       f"USCODE-{year}-title10-subtitleA-partII-chap47.htm").decode("utf-8", "replace")
            md = _html_to_markdown(raw)
            if md.count("## §") < 100:
                raise RuntimeError("page didn't look like the full UCMJ")
            out = LIB / "UCMJ_10_USC_Chapter_47.md"
            out.write_text(f"# Uniform Code of Military Justice (10 U.S.C. chapter 47)\n\n"
                           f"Source: U.S. Code {year} edition, govinfo.gov (Government Publishing Office). "
                           f"Public domain.\n\n{md}\n", encoding="utf-8")
            return f"UCMJ ({year} U.S. Code): {md.count('## §')} sections"
        except Exception as e:
            last = e
    raise RuntimeError(f"couldn't download the UCMJ: {last}")


def pdf_to_markdown(raw: bytes, title: str, source: str) -> str:
    """Convert an official PDF to text ONCE, on the machine that downloads it, so devices
    running Recruit never need a PDF reader. Each page becomes its own section."""
    import io
    from pypdf import PdfReader          # needed only here, on the setup machine
    reader = PdfReader(io.BytesIO(raw))
    pages = []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        # table-of-contents lines ("Title . . . . . . 12") are noise for search
        lines = [l for l in text.splitlines() if not re.search(r"(\.\s?){6,}", l)]
        text = "\n".join(lines)
        text = re.sub(r"\b([A-Z]) ([a-z]{2,})", r"\1\2", text)      # "T raditional" -> "Traditional"
        text = re.sub(r"[ \t]+", " ", text).strip()
        if len(text) > 80:
            pages.append(f"## page {i}\n\n{text}")
    return f"# {title}\n\nSource: {source}. Official U.S. Government publication (public domain).\n\n" + "\n\n".join(pages)


def tsp_summary() -> str:
    url = "https://www.tsp.gov/publications/tspbk08.pdf"
    raw = _get(url)
    md = pdf_to_markdown(raw, "Summary of the Thrift Savings Plan (TSPBK08)", f"Thrift Savings Plan, {url}")
    if md.count("## page") < 5:
        raise RuntimeError("the TSP summary didn't convert properly")
    (LIB / "TSP_Summary_of_the_Thrift_Savings_Plan.md").write_text(md, encoding="utf-8")
    return f"TSP summary: {md.count('## page')} pages"


# Army publications from the Army Publishing Directorate. Only PUBLIC copies are taken:
# armypubs keeps those under /epubs/DR_pubs/DR_a/; restricted ones (DR_b, DR_c ...) need a CAC.
APD = "https://armypubs.army.mil"
ARMY_PUBS = [
    # (number as armypubs lists it, product-map page, title)
    ("TC 7-21.13", "TC", "The Soldier's Guide"),
    ("AR 670-1", "AR", "Wear and Appearance of Army Uniforms and Insignia"),
    ("PAM 670-1", "PAM", "Guide to the Wear and Appearance of Army Uniforms and Insignia"),
    ("AR 600-20", "AR", "Army Command Policy"),
    ("AR 600-25", "AR", "Salutes, Honors, and Courtesies"),
    ("TC 3-21.5", "TC", "Drill and Ceremonies"),
    ("FM 7-22", "FM", "Holistic Health and Fitness"),
    ("AR 530-1", "AR", "Operations Security"),
    ("ATP 4-02.2", "ATP", "Medical Evacuation"),
    ("TC 3-21.76", "TC", "Ranger Handbook"),
    ("AR 600-52", "AR", "Sexual Harassment Assault Response and Prevention Program"),
    ("FM 6-22", "FM", "Developing Leaders"),
    ("ATP 6-22.1", "ATP", "The Counseling Process"),
    ("ATP 4-25.12", "ATP", "Unit Field Sanitation Teams"),
    ("TC 3-22.9", "TC", "Rifle and Carbine"),
    ("TC 4-02.3", "TC", "Field Hygiene and Sanitation"),
    ("TC 3-21.75", "TC", "The Warrior Ethos and Soldier Combat Skills"),
    ("ATP 7-22.02", "ATP", "Holistic Health and Fitness Drills and Exercises"),
    ("AR 621-5", "AR", "Army Continuing Education System"),
    # Not automatic: TC 3-25.26 (Map Reading and Land Navigation) is CAC-restricted on armypubs now,
    # and TC 4-02.1 (First Aid) is no longer listed as active.
]


def _apd_pdf_url(number: str, page: str, maps: dict) -> tuple[str, str]:
    """Find the public PDF link and the date for one publication."""
    if page not in maps:
        maps[page] = _get(f"{APD}/ProductMaps/PubForm/{page}.aspx", 60).decode("utf-8", "replace")
    m = re.search(r'Details\.aspx\?PUB_ID=(\d+)"[^>]*>' + re.escape(number) + "<", maps[page])
    if not m:
        raise RuntimeError("not listed as active on armypubs")
    det = _get(f"{APD}/ProductMaps/PubForm/Details.aspx?PUB_ID={m.group(1)}", 60).decode("utf-8", "replace")
    pdf = re.search(r"""href=['"](?:\.\./\.\./)?/?(epubs/DR_pubs/DR_a/[^'"]+?\.pdf)['"]""", det)
    if not pdf:
        raise RuntimeError("no public PDF (restricted or e-book only) — add by hand if you can")
    date = re.search(r"Pub/Form Date</td><td>([^<]+)", det)
    return f"{APD}/{urllib.parse.quote(pdf.group(1))}", (date.group(1).strip() if date else "")


MANIFEST = LIB / "manifest.json"       # which edition of each publication is installed


def _manifest() -> dict:
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def check_editions() -> int:
    """Compare installed Army publications with armypubs (nothing is downloaded)."""
    have, maps, newer = _manifest(), {}, []
    if not have:
        print("No record of installed editions yet -- run python tools/fetch_library.py first.")
        return 1
    for number, page, _title in ARMY_PUBS:
        if number not in have:
            continue
        try:
            _url, date = _apd_pdf_url(number, page, maps)
        except Exception as e:
            print(f"  ? {number}: couldn't check ({e})")
            continue
        if date and date != have[number]["date"]:
            newer.append(number)
            print(f"  ↑ {number}: installed {have[number]['date']}, armypubs now has {date}")
        else:
            print(f"  ✓ {number}: current ({date})")
    print(f"\n{len(newer)} newer edition(s)." + (" Run python tools/fetch_library.py to update." if newer else ""))
    return 0


def army_publications() -> str:
    maps: dict = {}
    got, missed = [], []
    manifest = _manifest()
    for number, page, title in ARMY_PUBS:
        name = ("DA " + number) if number.startswith("PAM") else number
        # the file name becomes the source Recruit cites, e.g. "AR 670-1 Wear and Appearance ..."
        out = LIB / (re.sub(r"[^A-Za-z0-9.\-]+", "_", f"{name} {title}".replace("'", "")).strip("_") + ".md")
        try:
            url, date = _apd_pdf_url(number, page, maps)
            raw = _get(url, 600)
            if not raw.startswith(b"%PDF"):
                raise RuntimeError("download wasn't a PDF (armypubs may be down for maintenance)")
            md = pdf_to_markdown(raw, f"{name}, {title}" + (f" ({date})" if date else ""), f"Army Publishing Directorate, {url}")
            if md.count("## page") < 5:
                raise RuntimeError("the PDF didn't convert to text")
            out.write_text(md, encoding="utf-8")
            manifest[number] = {"date": date, "file": out.name, "url": url}
            got.append(number)
            print(f"  ✓ {number} — {md.count('## page')} pages")
        except Exception as e:
            missed.append(f"{number} ({e})")
            print(f"  ✗ {number}: {e}")
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    if not got:
        raise RuntimeError("no Army publications downloaded: " + "; ".join(missed))
    return f"Army publications: {len(got)} added" + (f"; not added: {'; '.join(missed)}" if missed else "")


def convert_local_pdfs() -> str:
    """Convert any official PDFs someone saved into library/ by hand (e.g. from armypubs or DFAS)."""
    done = []
    for pdf in sorted(LIB.glob("*.pdf")):
        out = pdf.with_suffix(".md")
        if out.exists() and out.stat().st_mtime >= pdf.stat().st_mtime:
            continue
        out.write_text(pdf_to_markdown(pdf.read_bytes(), pdf.stem.replace("_", " "), pdf.name), encoding="utf-8")
        done.append(pdf.name)
    return f"converted {len(done)} PDF(s) you added" + (f": {', '.join(done)}" if done else "")


def _decode(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    return raw.decode("cp1252", errors="replace") if "�" in text else text


def _page_to_markdown(raw_html: str) -> tuple[str, str, str]:
    """(title, description, body markdown) from an official web page's main content."""
    title = re.search(r"(?is)<title>\s*(.*?)\s*</title>", raw_html)
    desc = re.search(r'(?is)<meta name="description" content="([^"]*)"', raw_html)
    body = re.sub(r"(?is)<(script|style|nav|header|footer|svg|form|noscript)[^>]*>.*?</\1>", "", raw_html)
    m = re.search(r"(?is)<main[^>]*>(.*)</main>", body)
    body = m.group(1) if m else body
    body = re.sub(r"(?is)<h[1-4][^>]*>(.*?)</h[1-4]>", lambda x: "\n\n## " + x.group(1) + "\n\n", body)
    body = re.sub(r"(?is)<li[^>]*>", "\n- ", body)
    body = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", body)
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", body))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    lines, seen = [], set()
    junk = re.compile(r'data-component|"\}\}"|\\r\\n|\\"|^</?\w+[^ ]*>?$|^\{|^\}|Opens in new window')
    for line in (l.strip() for l in text.splitlines()):
        if not line or junk.search(line) or line in seen and not line.startswith("##"):   # page code / repeats
            continue
        seen.add(line)
        lines.append(line)
    clean = lambda s: html.unescape(re.sub(r"\s+", " ", s or "")).strip()
    t = clean(title.group(1) if title else "").replace(" | U.S. Army", "").strip()
    return t, clean(desc.group(1) if desc else ""), "\n".join(lines)


GOARMY_PAGES = [
    "army-life/basic-training", "army-life/intro-to-army-life/daily-routine", "how-to-join/after-you-join",
    "how-to-join/steps/asvab", "how-to-join/requirements", "how-to-join/requirements/appearance",
    "how-to-join/requirements/fitness", "careers-and-jobs/job-training/advanced-individual-training",
    "careers-and-jobs/job-training/leadership-schools", "careers-and-jobs/find-your-path/enlisted-soldiers",
    "careers-and-jobs/find-your-path/warrant-officers", "careers-and-jobs/find-your-path/army-officers/ocs",
    "careers-and-jobs/find-your-path/army-officers/green-to-gold", "benefits/while-you-serve/education-training",
    "benefits/while-you-serve/education-training/gi-bill",
    "benefits/while-you-serve/education-training/certifications-and-credentials",
    "benefits/while-you-serve/money-pay", "benefits/while-you-serve/health-care", "benefits/while-you-serve/home-loans",
    "explore-the-army/holistic-health-fitness",
]
VA_PAGES = ["https://www.va.gov/education/about-gi-bill-benefits/",
            "https://www.va.gov/education/about-gi-bill-benefits/post-9-11/",
            "https://www.va.gov/education/about-gi-bill-benefits/montgomery-active-duty/"]


def goarmy_pages() -> str:
    parts, failed = [], []
    for path in GOARMY_PAGES:
        url = f"https://www.goarmy.com/{path}"
        try:
            title, desc, body = _page_to_markdown(_decode(_get(url, 60)))
            parts.append(f"# {title or path}\n\nSource: {url}\n\n{desc}\n\n{body}")
        except Exception:
            failed.append(path)
        time.sleep(0.6)
    # drop site-wide boilerplate: lines that appear on 4+ different pages ("Not finding what you need?" …)
    from collections import Counter
    counts = Counter(l for p in parts for l in set(p.splitlines()) if l.strip() and not l.startswith("#"))
    parts = ["\n".join(l for l in p.splitlines() if l.startswith("#") or counts[l] < 4) for p in parts]
    (LIB / "GoArmy_Joining_Training_Benefits.md").write_text(
        "# U.S. Army — joining, training and benefits (goarmy.com)\n\nOfficial U.S. Army recruiting site; public information.\n\n"
        + "\n\n".join(parts), encoding="utf-8")
    return f"goarmy.com topic pages: {len(parts)}" + (f" (failed: {', '.join(failed)})" if failed else "")


def va_gi_bill() -> str:
    parts = []
    for url in VA_PAGES:
        try:
            title, desc, body = _page_to_markdown(_decode(_get(url, 60)))
            parts.append(f"# {title}\n\nSource: {url}\n\n{desc}\n\n{body}")
        except Exception:
            pass
        time.sleep(0.6)
    if not parts:
        raise RuntimeError("va.gov pages couldn't be downloaded")
    (LIB / "VA_GI_Bill.md").write_text("# GI Bill (U.S. Department of Veterans Affairs, va.gov)\n\n" + "\n\n".join(parts),
                                       encoding="utf-8")
    return f"va.gov GI Bill pages: {len(parts)}"


def goarmy_jobs() -> str:
    """Every Army job (MOS) page listed in goarmy.com's sitemap: code, title, career area, official summary."""
    sm = _decode(_get("https://www.goarmy.com/sitemap.xml", 60))
    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm) if "/es/" not in u]
    skip = ("find-your-path", "specialty-careers", "job-training", "career-match", "browse-jobs")
    jobs = []
    for u in urls:
        parts = u.split("goarmy.com/")[-1].strip("/").split("/")
        if len(parts) != 4 or parts[0] != "careers-and-jobs" or parts[1] in skip:
            continue
        m = re.match(r"^(\d{2}[a-z0-9]{1,2}|[a-z]{1,2}\d{1,3}[a-z]?)-(.*)$", parts[3])
        try:
            title, desc, _body = _page_to_markdown(_decode(_get(u, 60)))
        except Exception:
            continue
        jobs.append({"code": m.group(1).upper() if m else "", "title": title, "area": parts[1].replace("-", " ").title(),
                     "group": parts[2].replace("-", " ").title(), "summary": desc, "url": u})
        time.sleep(0.5)
    if len(jobs) < 100:
        raise RuntimeError(f"only {len(jobs)} job pages read")
    jobs.sort(key=lambda j: (j["code"] or "ZZZ", j["title"]))
    (LIB / "_jobs.json").write_text(json.dumps({"source": "goarmy.com", "fetched": time.strftime("%Y-%m-%d"),
                                                "jobs": jobs}, indent=1, ensure_ascii=False), encoding="utf-8")
    md = "\n\n".join(f"## {j['code']} {j['title']}\n\nCareer area: {j['area']} — {j['group']}\n\n{j['summary']}\n\nSource: {j['url']}"
                     for j in jobs)
    (LIB / "GoArmy_Army_Jobs_MOS.md").write_text("# Army jobs (MOS) — official summaries from goarmy.com\n\n" + md, encoding="utf-8")
    return f"Army jobs: {len(jobs)}"




JOBS = [ucmj, tsp_summary, army_publications, goarmy_pages, va_gi_bill, goarmy_jobs, convert_local_pdfs]


def main(argv: list[str]) -> int:
    LIB.mkdir(exist_ok=True)
    if "--check" in argv:
        return check_editions()
    ok, failed = [], []
    for job in JOBS:
        try:
            ok.append(job())
            print("✓", ok[-1])
        except Exception as e:
            failed.append(f"{job.__name__}: {e}")
            print("✗", failed[-1])
    try:                                         # fingerprints for the tamper check (recruit/integrity.py)
        sys.path.insert(0, str(ROOT))
        from recruit import integrity
        print("✓ fingerprints recorded:", integrity.write_manifest(LIB).name)
    except Exception as e:
        print("✗ couldn't record fingerprints:", e)
    print(f"\n{len(ok)} added to {LIB}." + (" Not downloaded (add by hand, see LIBRARY.md): " + "; ".join(failed)
                                            if failed else ""))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
