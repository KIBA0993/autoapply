#!/usr/bin/env python3
"""Breezy HR job-search adapter — public board JSON, no auth.

Breezy HR skews to SMB / early-stage startups. The documented API needs a token, but every
public board also serves an unauthenticated JSON list (verified 2026-08-06 against breezy):

    GET https://{slug}.breezy.hr/json

Returns a JSON array of positions: name, location{name,is_remote,country,state},
published_date (ISO), url (public posting URL), department, salary. One request, whole
board. No pagination, no ETag.

No open slug corpus exists for Breezy, so this is a DISCOVERY-SEEDED source (like
SmartRecruiters / Recruitee): point it at a company slug you've found, not a bulk sweep.
The slug is the subdomain of the careers URL ({slug}.breezy.hr).

Usage:
    python tools/fetch_breezy.py --slug acme --q "Product Manager|Program Manager" --days 7
    python tools/fetch_breezy.py --slug acme --limit 50

Emits one JSON object per matching posting to stdout (JSONL):
    ats, company, title, location, posted_days (int|null), req_id, url
--q is a case-insensitive regex on the title.
"""
import argparse
import datetime
import json
import re
import sys
import urllib.request
import urllib.error

_UA = {"User-Agent": "autoapply-breezy/1.0", "Accept": "application/json"}


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_days(dt, now):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int((now - dt).total_seconds() // 86400)


def fetch(slug, timeout=20):
    url = f"https://{slug}.breezy.hr/json"
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        print(f"ERROR: {slug} — {e}", file=sys.stderr)
        sys.exit(65)
    return data if isinstance(data, list) else data.get("positions", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="Breezy subdomain, e.g. acme")
    ap.add_argument("--q", help="case-insensitive regex on the title")
    ap.add_argument("--days", type=float, help="recency window on published_date")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--now", help="ISO override for 'now' (testing)")
    a = ap.parse_args()

    now = (datetime.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now
           else datetime.datetime.now(datetime.timezone.utc))
    title_re = re.compile(a.q, re.I) if a.q else None

    matched = 0
    for p in fetch(a.slug):
        title = p.get("name")
        if title_re and not (title and title_re.search(title)):
            continue
        days = age_days(parse_dt(p.get("published_date")), now)
        if a.days is not None and days is not None and days > a.days:
            continue
        loc_obj = p.get("location") or {}
        loc = loc_obj.get("name") or ""
        if loc_obj.get("is_remote"):
            loc = (loc + " (remote)").strip()
        print(json.dumps({
            "ats": "breezy",
            "company": (p.get("company") or {}).get("name") or a.slug,
            "title": title,
            "location": loc,
            "posted_days": days,
            "req_id": p.get("friendly_id") or p.get("id"),
            "url": p.get("url"),
        }, ensure_ascii=False))
        matched += 1
        if matched >= a.limit:
            break

    print(f"{matched} matched @ {a.slug}"
          + (f" (<= {a.days:g}d)" if a.days is not None else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
