#!/usr/bin/env python3
"""Workday CXS job-search adapter — one script covers every Workday tenant.

Workday runs a huge share of enterprise careers sites, and every tenant exposes the
SAME undocumented-but-stable JSON search endpoint:

    POST https://{host}/wday/cxs/{tenant}/{site}/jobs
    body: {"appliedFacets":{}, "limit":20, "offset":0, "searchText":"..."}

Verified live 2026-08-05 against nvidia.wd5.myworkdayjobs.com (1126 PM results).
Returns structured JSON — same quality as the Greenhouse/Ashby/Lever APIs — so it
belongs in Phase 1 as a lead SOURCE. Note: applying to a Workday role is account-gated
per tenant (Tier 4 in application_rules.md) → surface the lead, hand the apply to the user.

Usage:
    # explicit host (from the registry) — most reliable:
    python tools/fetch_workday.py --host nvidia.wd5.myworkdayjobs.com \
        --tenant nvidia --site NVIDIAExternalCareerSite --q "product manager"

    # or tenant + datacenter:
    python tools/fetch_workday.py --tenant nvidia --dc wd5 \
        --site NVIDIAExternalCareerSite --q "product manager" --limit 50

Emits one JSON object per posting to stdout (JSONL), a count summary to stderr.
Fields: company, title, location, posted_days (int|null), req_id, url.
posted_days feeds the Phase-2 freshness banding (Fresh<=7, Older 8-30, Stale>30).
"""
import argparse
import json
import re
import sys
import urllib.request
import urllib.error


def parse_posted_days(s):
    """'Posted Today'->0, 'Posted Yesterday'->1, 'Posted 23 Days Ago'->23,
    'Posted 30+ Days Ago'->30. Unknown -> None."""
    if not s:
        return None
    t = s.lower()
    if "today" in t:
        return 0
    if "yesterday" in t:
        return 1
    m = re.search(r"(\d+)\s*\+?\s*day", t)
    if m:
        return int(m.group(1))
    return None


def fetch(host, tenant, site, query, limit, page_size=20, timeout=25):
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    out, offset = [], 0
    while len(out) < limit:
        body = json.dumps({
            "appliedFacets": {},
            "limit": min(page_size, limit - len(out)),
            "offset": offset,
            "searchText": query,
        }).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # a browser-ish UA; Workday CXS accepts plain clients but be polite
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) autoapply/1.0",
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"ERROR: {host} — {e}", file=sys.stderr)
            sys.exit(65)
        postings = data.get("jobPostings", [])
        total = data.get("total", 0)
        if not postings:
            break
        for j in postings:
            ext = j.get("externalPath", "")
            out.append({
                "company": tenant,
                "title": j.get("title"),
                "location": j.get("locationsText"),
                "posted_days": parse_posted_days(j.get("postedOn")),
                "req_id": (j.get("bulletFields") or [None])[0],
                # Workday redirects /{site}{externalPath} to the localized detail page
                "url": f"https://{host}/{site}{ext}" if ext else None,
            })
            if len(out) >= limit:
                break
        offset += len(postings)
        if offset >= total:
            break
    return out, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", help="e.g. nvidia.wd5.myworkdayjobs.com (overrides --dc)")
    ap.add_argument("--tenant", required=True, help="e.g. nvidia")
    ap.add_argument("--dc", help="datacenter, e.g. wd5 (used only if --host omitted)")
    ap.add_argument("--site", required=True, help="e.g. NVIDIAExternalCareerSite")
    ap.add_argument("--q", default="", help="search text")
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()

    host = a.host
    if not host:
        if not a.dc:
            print("ERROR: need --host or --dc", file=sys.stderr)
            sys.exit(64)
        host = f"{a.tenant}.{a.dc}.myworkdayjobs.com"

    rows, total = fetch(host, a.tenant, a.site, a.q, a.limit)
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    print(f"{len(rows)} returned of {total} total for '{a.q}' @ {a.tenant}", file=sys.stderr)


if __name__ == "__main__":
    main()
