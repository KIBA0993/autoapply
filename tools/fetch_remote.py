#!/usr/bin/env python3
"""Remote-board discovery connector — the only CROSS-company, ToS-clean job feeds.

Every other adapter here is per-company (you must know the company first). These five
remote-first boards publish FREE, NO-AUTH, ToS-permitted JSON APIs that list roles across
many companies at once — so they're a discovery layer, not a per-company lookup:

    RemoteOK   https://remoteok.com/api                        (dev/eng-heavy; first row is a legal notice, skipped)
    Remotive   https://remotive.com/api/remote-jobs            (curated, broad categories)
    Arbeitnow  https://www.arbeitnow.com/api/job-board-api     (broad, European lean)
    Himalayas  https://himalayas.app/jobs/api                  (remote, salary data)
    Jobicy     https://jobicy.com/api/v2/remote-jobs           (curated remote)

CRITICAL — these are AGGREGATORS, not company ATS boards. The skill's rule stands: do NOT
apply through the middleman. Every board hides the real apply URL behind its own domain
(verified 2026-08-06: even Himalayas' applicationLink points back to himalayas.app), so the
feed cannot hand you a direct apply link. Instead this tool RESOLVES each discovered company
against sources/companies.json (the 15,870 Greenhouse/Ashby/Lever slugs): if a slug guess
matches, the row is annotated direct_ats/direct_slug so the APPLY routes to the company's own
board via the existing direct connector. Rows that don't resolve are discovery-only leads —
surface them, but re-verify liveness on the company's real board before applying (aggregator
listings go stale, same hazard as web-search leads).

Usage:
    python tools/fetch_remote.py --q "Product Manager|Program Manager" --days 3
    python tools/fetch_remote.py --sources arbeitnow,remotive --q "Product Manager" --limit 200

Emits one JSON object per matching posting (JSONL):
    source, company, title, location, posted_days, req_id, url, remote,
    direct_ats (null|greenhouse/ashby/lever), direct_slug (null)
Summary to stderr: per-source counts + how many resolved to a direct board.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_COMPANIES = os.path.join(HERE, "..", "sources", "companies.json")
_UA = {"User-Agent": "Mozilla/5.0 (autoapply-remote/1.0)", "Accept": "application/json"}


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def age_days(val, now):
    """Accept epoch (int/float/numeric str) or ISO string. -> whole days, or None."""
    if val is None or val == "":
        return None
    dt = None
    try:
        dt = datetime.datetime.fromtimestamp(float(val), datetime.timezone.utc)
    except (ValueError, TypeError, OSError):
        s = str(val).replace("Z", "+00:00")
        for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.datetime.fromisoformat(s) if fmt is None else datetime.datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int((now - dt).total_seconds() // 86400)


def _loc_join(v):
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x)
    return v or ""


# Per-source: endpoint + how to reach the array + field map. Each maps a raw record to
# (company, title, location, date_value, req_id, url, remote_bool).
SOURCES = {
    "remoteok": {
        "url": lambda lim: "https://remoteok.com/api",
        "array": lambda d: d[1:] if isinstance(d, list) else [],  # [0] is a legal notice
        "norm": lambda r: (r.get("company"), r.get("position"), r.get("location"),
                           r.get("epoch") or r.get("date"), r.get("id"), r.get("url"), True),
    },
    "remotive": {
        "url": lambda lim: f"https://remotive.com/api/remote-jobs?limit={lim}",
        "array": lambda d: d.get("jobs", []),
        "norm": lambda r: (r.get("company_name"), r.get("title"), r.get("candidate_required_location"),
                           r.get("publication_date"), r.get("id"), r.get("url"), True),
    },
    "arbeitnow": {
        "url": lambda lim: "https://www.arbeitnow.com/api/job-board-api",
        "array": lambda d: d.get("data", []),
        "norm": lambda r: (r.get("company_name"), r.get("title"), r.get("location"),
                           r.get("created_at"), r.get("slug"), r.get("url"), bool(r.get("remote"))),
    },
    "himalayas": {
        "url": lambda lim: f"https://himalayas.app/jobs/api?limit={lim}",
        "array": lambda d: d.get("jobs", []),
        "norm": lambda r: (r.get("companyName"), r.get("title"), _loc_join(r.get("locationRestrictions")),
                           r.get("pubDate"), r.get("guid"), r.get("applicationLink"), True),
    },
    "jobicy": {
        "url": lambda lim: f"https://jobicy.com/api/v2/remote-jobs?count={lim}",
        "array": lambda d: d.get("jobs", []),
        "norm": lambda r: (r.get("companyName"), r.get("jobTitle"), r.get("jobGeo"),
                           r.get("pubDate"), r.get("id"), r.get("url"), True),
    },
}


def fetch_source(name, limit):
    cfg = SOURCES[name]
    try:
        req = urllib.request.Request(cfg["url"](limit), headers=_UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return name, cfg["array"](json.loads(r.read()))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as e:
        print(f"ERROR: {name} — {e}", file=sys.stderr)
        return name, []


def slug_guesses(company):
    """The same nopunct/hyphen variants Phase 1 tries when guessing an ATS slug."""
    if not company:
        return []
    base = company.strip().lower()
    nopunct = re.sub(r"[^a-z0-9]", "", base)
    hyphen = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return [g for g in dict.fromkeys([nopunct, hyphen]) if g]


def load_known_slugs(path):
    """Map slug -> ats from companies.json, for direct-board resolution."""
    known = {}
    try:
        raw = json.load(open(path))
        items = raw.get("sources", raw) if isinstance(raw, dict) else raw
        for c in items:
            if c.get("slug"):
                known[c["slug"].lower()] = c.get("ats")
    except Exception:
        pass
    return known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=",".join(SOURCES),
                    help="comma list from: " + ", ".join(SOURCES))
    ap.add_argument("--q", help="case-insensitive regex on the title")
    ap.add_argument("--days", type=float, help="recency window on the post date")
    ap.add_argument("--limit", type=int, default=200, help="max rows requested per source")
    ap.add_argument("--companies", default=DEFAULT_COMPANIES,
                    help="companies.json for direct-board resolution")
    a = ap.parse_args()

    picked = [s.strip() for s in a.sources.split(",") if s.strip() in SOURCES]
    if not picked:
        print("no valid --sources (choose from: " + ", ".join(SOURCES) + ")", file=sys.stderr)
        sys.exit(64)

    now = now_utc()
    title_re = re.compile(a.q, re.I) if a.q else None
    known = load_known_slugs(a.companies)

    per_source = {}
    emitted = resolved = 0
    with ThreadPoolExecutor(max_workers=len(picked)) as ex:
        results = list(ex.map(lambda s: fetch_source(s, a.limit), picked))

    for name, rows in results:
        cfg = SOURCES[name]
        kept = 0
        for r in rows:
            company, title, loc, datev, rid, url, remote = cfg["norm"](r)
            if title_re and not (title and title_re.search(title)):
                continue
            days = age_days(datev, now)
            if a.days is not None and days is not None and days > a.days:
                continue
            direct_ats = direct_slug = None
            for g in slug_guesses(company):
                if g in known:
                    direct_ats, direct_slug = known[g], g
                    break
            if direct_ats:
                resolved += 1
            print(json.dumps({
                "source": name, "company": company, "title": title,
                "location": loc or "", "posted_days": days, "req_id": rid,
                "url": url, "remote": bool(remote),
                "direct_ats": direct_ats, "direct_slug": direct_slug,
            }, ensure_ascii=False))
            kept += 1
            emitted += 1
        per_source[name] = kept

    breakdown = " ".join(f"{k}={v}" for k, v in per_source.items())
    print(f"{emitted} emitted [{breakdown}] | {resolved} resolved to a direct board "
          f"(apply direct); {emitted - resolved} discovery-only (verify liveness)", file=sys.stderr)


if __name__ == "__main__":
    main()
