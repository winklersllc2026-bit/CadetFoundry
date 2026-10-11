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
UA = {"User-Agent": "Mozilla/5.0 (Cadet Foundry library installer)"}


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
    running Cadet Foundry never need a PDF reader. Each page becomes its own section."""
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
        # the file name becomes the source Cadet Foundry cites, e.g. "AR 670-1 Wear and Appearance ..."
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


# ── Jobs in every service (0.2): read from each service's official recruiting site, the same way as Army jobs ──
# Each page's own words are kept (title, summary, enlisted/officer, job code, and -- where the page lists them --
# the minimum ASVAB line scores). Nothing is written by hand or guessed.
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/130.0 Safari/537.36"}        # the services' recruiting sites refuse unknown clients


def _get_page(url: str) -> str:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=BROWSER), timeout=60) as r:
                return _decode(r.read())
        except (OSError, urllib.error.URLError):
            if attempt == 2:
                raise
            time.sleep(4 * (attempt + 1))


def _text(raw_html: str) -> str:
    """The page's visible words on one line (scripts and styles dropped)."""
    t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw_html)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", t))).strip()


def _meta(raw_html: str, name: str) -> str:
    m = re.search(rf'(?is)<meta[^>]+(?:name|property)="{name}"[^>]+content="([^"]*)"', raw_html)
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else ""


def _h1(raw_html: str) -> str:
    m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", raw_html)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", m.group(1)))).strip() if m else ""


def _sitemap(url: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", _get_page(url))


def _area(slug: str) -> str:
    return slug.replace("-", " ").title().replace(" And ", " and ")


ASVAB_AREAS = {"M": "Mechanical", "A": "Administrative", "G": "General", "E": "Electronics"}


def _af_job(url: str) -> dict | None:
    raw = _get_page(url)
    if 'name="template" content="career-page"' not in raw:
        return None                                   # an overview or FAQ page, not one job
    t = _text(raw)
    title = re.sub(r"\s*-\s*U\.S\. Air Force\s*$", "", re.search(r"(?is)<title>(.*?)</title>", raw).group(1)).strip()
    title = html.unescape(re.sub(r"\s+", " ", title))
    rank = re.search(r"Rank:\s*(Enlisted|Officer)", t)
    code = re.search(r"\bAFSC:\s*([0-9A-Z]{3,6}[0-9A-Z]?)", t)
    # The summary: after the page's title line and its capitals tagline, up to the first APPLY NOW.
    m = re.search(re.escape(f"{rank.group(1) if rank else ''} {title}".strip()) + r"\s+(.*?)\s+APPLY NOW", t)
    summary = m.group(1) if m else ""
    summary = re.sub(r"^(?:[A-Z0-9’'&,.\-]+\s+){2,}(?=[A-Z][a-z])", "", summary).strip()   # drop the CAPS tagline
    req = re.search(r"(?i:ASVAB(?: SCORE)? REQUIREMENTS)\s+(.*?)\s+(?:Qualifications|CAREER FINDER|Training)", t)
    # "62 General (G)"; the letter is the Air Force's area code, so "65 Electrical (E)" is the Electronics area.
    # Some pages leave the letter off ("70 Electronics"); a page with only a word ("General") gives no number.
    scores = [{"area": ASVAB_AREAS[a] if a else ("Electronics" if n == "Electrical" else n), "min": int(v)}
              for v, n, a in re.findall(r"(\d{2,3})\s+(Mechanical|Administrative|General|Electronics|Electrical)"
                                        r"(?:\s*\(([MAGE])\))?", req.group(1) if req else "")]
    parts = url.split("airforce.com/careers/")[-1].strip("/").split("/")
    return {"service": "air_force", "code": code.group(1) if code else "", "title": title,
            "kind": (rank.group(1).lower() if rank else ""), "area": _area(parts[0]), "group": "",
            "summary": summary or _meta(raw, "description"), "url": url,
            "asvab": scores, "asvab_text": re.sub(r"\s+", " ", req.group(1)).strip() if req else "",
            # "or" between two requirements means either one qualifies
            "asvab_any": bool(req and re.search(r"\bor\b", req.group(1), re.I))}


def airforce_jobs() -> str:
    urls = [u for u in _sitemap("https://www.airforce.com/sitemap.xml")
            if re.match(r"https://www\.airforce\.com/careers/[^/]+/[^/]+(/[^/]+)?/?$", u)
            and not re.search(r"frequently-asked|career-finder|specialty-careers", u)]
    return _save_jobs("air_force", "airforce.com", urls, _af_job, minimum=60)


def _navy_job(url: str) -> dict | None:
    raw = _get_page(url)
    title = _h1(raw)
    if not title:
        return None
    t = _text(raw)
    kind = re.search(r"Apply Now\s+(Enlisted|Officer)\b", t)
    code = re.search(r"\bAs an? ([A-Z]{2,4}) applicant", t)
    parts = url.split("/careers-benefits/careers/")[-1].strip("/").split("/")
    return {"service": "navy", "code": code.group(1) if code else "", "title": title,
            "kind": kind.group(1).lower() if kind else "", "area": _area(parts[0]), "group": "",
            "summary": _meta(raw, "description"), "url": url, "asvab": [], "asvab_text": "", "asvab_any": False}


def navy_jobs() -> str:
    urls = [u for u in _sitemap("https://www.navy.com/sitemap.xml")
            if re.match(r"https://www\.navy\.com/careers-benefits/careers/[^/]+/[^/]+/?$", u)]
    return _save_jobs("navy", "navy.com", urls, _navy_job, minimum=60)


def _sf_job(url: str) -> dict | None:
    raw = _get_page(url)
    title = _h1(raw)
    if not title:
        return None
    kind = "officer" if "/officer-careers/" in url else "enlisted"
    return {"service": "space_force", "code": "", "title": title, "kind": kind, "area": "Space Force",
            "group": "", "summary": _meta(raw, "description"), "url": url, "asvab": [], "asvab_text": "",
            "asvab_any": False}


def spaceforce_jobs() -> str:
    urls = []
    for sm in _sitemap("https://www.spaceforce.com/sitemap.xml"):
        if sm.endswith(".xml"):
            urls += [u for u in _sitemap(sm) if re.search(r"spaceforce\.com/(officer|enlisted)-careers/[^/]+/?$", u)]
    return _save_jobs("space_force", "spaceforce.com", urls, _sf_job, minimum=10)


def _usmc_field(url: str) -> dict | None:
    raw = _get_page(url)
    title = _h1(raw)
    if not title:
        return None
    return {"service": "marine_corps", "code": "", "title": title, "kind": "career field", "area": "Career Fields",
            "group": "", "summary": _meta(raw, "description"), "url": url, "asvab": [], "asvab_text": "",
            "asvab_any": False}


def marines_jobs() -> str:
    """marines.com lists career fields (infantry, aviation, law enforcement ...), not every MOS."""
    urls = [u for u in _sitemap("https://www.marines.com/sitemap.xml")
            if re.match(r"https://www\.marines\.com/mission/roles/[^/]+\.html$", u)]
    return _save_jobs("marine_corps", "marines.com", urls, _usmc_field, minimum=4)


def _save_jobs(service: str, site: str, urls: list[str], read, minimum: int) -> str:
    jobs = []
    for u in dict.fromkeys(urls):
        try:
            j = read(u)
        except Exception:
            j = None
        if j and j["title"] and j["summary"]:
            jobs.append(j)
        time.sleep(0.5)
    if len(jobs) < minimum:
        raise RuntimeError(f"{site}: only {len(jobs)} job pages read")
    jobs.sort(key=lambda j: (j["area"], j["title"]))
    (LIB / f"_jobs_{service}.json").write_text(json.dumps({"source": site, "fetched": time.strftime("%Y-%m-%d"),
                                                           "service": service, "jobs": jobs}, indent=1,
                                                          ensure_ascii=False), encoding="utf-8")
    return f"{site} jobs: {len(jobs)}"


# ── Reference pages for Ask, every service (0.2) ────────────────────────────────────────────────────────────────
# Official recruiting and testing sites (the .mil sites refuse scripted downloads; these allow them). Pages that
# explain -- history, values, ranks, training, ways to join, education, pay -- not ads or news.
SERVICE_PAGES = {
    "AirForce_com_Air_Force.md": ("U.S. Air Force — mission, joining, training and life (airforce.com)", "https://www.airforce.com", [
        "/mission", "/vision", "/education", "/education/college", "/how-to-join", "/how-to-join/join-the-air-force",
        "/how-to-join/join-the-air-national-guard", "/how-to-join/join-the-air-force-reserve",
        "/frequently-asked-questions/paths-processes/how-things-work", "/frequently-asked-questions/paths-processes/enlisted-path",
        "/frequently-asked-questions/paths-processes/officer-path", "/frequently-asked-questions/requirements-eligibility/physical",
        "/frequently-asked-questions/requirements-eligibility/academic", "/frequently-asked-questions/requirements-eligibility/character",
        "/frequently-asked-questions/education-training/high-school", "/frequently-asked-questions/education-training/military-training",
        "/frequently-asked-questions/education-training/college", "/frequently-asked-questions/education-training/technical-training",
        "/frequently-asked-questions/ways-to-serve/air-force-active-duty", "/frequently-asked-questions/ways-to-serve/air-force-reserve",
        "/frequently-asked-questions/ways-to-serve/air-national-guard", "/frequently-asked-questions/careers-benefits/pay",
        "/frequently-asked-questions/careers-benefits/education-benefits", "/frequently-asked-questions/lifestyle-locations/whats-it-like",
        "/frequently-asked-questions/information-for-families/support"]),
    "Navy_com_Navy.md": ("U.S. Navy — Navy life, ranks, joining and education (navy.com)", "https://www.navy.com", [
        "/navy-life/who-we-are", "/navy-life/boot-camp", "/navy-life/ship", "/navy-life/base", "/navy-life/what-families-can-expect",
        "/careers-benefits/navy-ranks", "/careers-benefits/pay", "/careers-benefits/education", "/careers-benefits/education/nrotc",
        "/careers-benefits/education/naval-academy", "/careers-benefits/education/college-scholarships", "/joining/requirements",
        "/joining/ways-to-join/enlisted", "/joining/ways-to-join/officer", "/joining/ways-to-join/reserve", "/joining/prepare-to-join"]),
    "Marines_com_Marine_Corps.md": ("U.S. Marine Corps — ethos, history, ranks and becoming a Marine (marines.com)", "https://www.marines.com", [
        "/ethos.html", "/ethos/values.html", "/ethos/history.html", "/ethos/mottos.html", "/ethos/uniforms.html", "/ethos/ranks.html",
        "/ethos/articles/eagle-globe-anchor.html", "/ethos/articles/blood-stripe.html", "/ethos/articles/mameluke-sword.html",
        "/mission.html", "/mission/air-ground-task-force.html", "/become/requirements.html", "/become/recruit-training.html",
        "/become/marine-officer.html", "/become/marine-officer/officer-candidate-school.html",
        "/become/marine-officer/the-basic-school.html", "/become/marine-corps-reserve.html", "/become/benefits/education.html",
        "/faq-for-parents.html"]),
    "SpaceForce_com_Space_Force.md": ("U.S. Space Force — about, history, training and joining (spaceforce.com)", "https://www.spaceforce.com", [
        "/about", "/history", "/capabilities", "/training", "/fitness", "/life-as-a-guardian", "/how-to-join/enlisted-guardians",
        "/how-to-join/officer", "/education/enlisted", "/education/officer"]),
    "OfficialASVAB_com.md": ("The ASVAB — official information (officialasvab.com)", "https://www.officialasvab.com", [
        "/applicants/what-to-expect/", "/applicants/scores/", "/applicants/prepare/", "/applicants/cat-asvab/", "/applicants/faqs/",
        "/applicants/asvab-test-preparation-disclaimer/", "/counselors-educators/asvab-career-exploration-program/",
        "/counselors-educators/asvab-subtests/"]),
}


def service_pages() -> str:
    from collections import Counter
    done = []
    for fname, (heading, site, paths) in SERVICE_PAGES.items():
        parts, failed = [], []
        for path in paths:
            url = site + path
            try:
                title, desc, body = _page_to_markdown(_get_page(url))
                if len(body) < 300:                       # a page that only draws itself with scripts
                    raise ValueError("no readable text")
                parts.append(f"# {title or path}\n\nSource: {url}\n\n{desc}\n\n{body}")
            except Exception:
                failed.append(path)
            time.sleep(0.5)
        if not parts:
            continue
        counts = Counter(l for p in parts for l in set(p.splitlines()) if l.strip() and not l.startswith("#"))
        limit = max(3, len(parts) // 3)                   # menus and footers repeat on every page
        parts = ["\n".join(l for l in p.splitlines() if l.startswith(("#", "Source:")) or counts[l] < limit) for p in parts]
        (LIB / fname).write_text(f"# {heading}\n\nOfficial public information.\n\n" + "\n\n".join(parts), encoding="utf-8")
        done.append(f"{fname} {len(parts)}" + (f" (failed {len(failed)})" if failed else ""))
    if not done:
        raise RuntimeError("no service pages could be read")
    return "service pages: " + "; ".join(done)


JOBS = [ucmj, tsp_summary, army_publications, goarmy_pages, va_gi_bill, goarmy_jobs, airforce_jobs, navy_jobs,
        spaceforce_jobs, marines_jobs, service_pages, convert_local_pdfs]


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
    try:                                         # fingerprints for the tamper check (vanguard/integrity.py)
        sys.path.insert(0, str(ROOT))
        from vanguard import integrity
        print("✓ fingerprints recorded:", integrity.write_manifest(LIB).name)
    except Exception as e:
        print("✗ couldn't record fingerprints:", e)
    print(f"\n{len(ok)} added to {LIB}." + (" Not downloaded (add by hand, see LIBRARY.md): " + "; ".join(failed)
                                            if failed else ""))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
