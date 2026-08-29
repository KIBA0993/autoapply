#!/usr/bin/env python3
"""Recruitee job-search adapter — public offers API, no auth.

Recruitee is common among SMB / mid-market and European scaleups. Every company exposes
the same public endpoint (verified 2026-08-06 against channable):

    GET https://{slug}.recruitee.com/api/offers/

Returns JSON: offers[] with title, location, published_at (ISO+' UTC', true post date),
status, careers_url (public posting URL), remote/hybrid/on_site flags. No pagination — one
request returns the whole board. No ETag (can't do the 304 delta the big-three get).

There is NO open slug corpus for Recruitee, so this is a DISCOVERY-SEEDED source (like
SmartRecruiters): you point it at a company slug you've found, not a bulk sweep. The slug
is the subdomain from the careers URL (jobs are often re-hosted at jobs.{company}.com, but
the API always lives at {slug}.recruitee.com — take the slug from there).

Usage:
    python tools/fetch_recruitee.py --slug channable --q "Product Manager|Program Manager" --days 7
    python tools/fetch_recruitee.py --slug channable --limit 50

Emits one JSON object per matching posting to stdout (JSONL):
    ats, company, title, location, posted_days (int|null), req_id, url
Only status=='published' offers are emitted. --q is a case-insensitive regex on the title.
"""
import argparse
import datetime
import json
import re
import sys
import urllib.request
import urllib.error

_UA = {"User-Agent": "autoapply-recruitee/1.0", "Accept": "application/json"}


def parse_dt(s):
    """Recruitee stamps look like '2026-08-03 15:40:43 UTC'."""
    if not s:
        return None
    s = s.replace(" UTC", "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    return None


def age_days(dt, now):
    if dt is None:
        return None
    return int((now - dt).total_seconds() // 86400)


def fetch(slug, timeout=20):
    url = f"https://{slug}.recruitee.com/api/offers/"
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()).get("offers", [])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        print(f"ERROR: {slug} — {e}", file=sys.stderr)
        sys.exit(65)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="Recruitee subdomain, e.g. channable")
    ap.add_argument("--q", help="case-insensitive regex on the title")
    ap.add_argument("--days", type=float, help="recency window on published_at")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--now", help="ISO override for 'now' (testing)")
    a = ap.parse_args()

    now = (datetime.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now
           else datetime.datetime.now(datetime.timezone.utc))
    title_re = re.compile(a.q, re.I) if a.q else None

    matched = 0
    for o in fetch(a.slug):
        if o.get("status") != "published":
            continue
        title = o.get("title")
        if title_re and not (title and title_re.search(title)):
            continue
        days = age_days(parse_dt(o.get("published_at") or o.get("created_at")), now)
        if a.days is not None and days is not None and days > a.days:
            continue
        loc = o.get("location") or ", ".join(
            x for x in (o.get("city"), o.get("state_name"), o.get("country")) if x)
        if o.get("remote"):
            loc = (loc + " (remote)").strip()
        print(json.dumps({
            "ats": "recruitee",
            "company": o.get("company_name") or a.slug,
            "title": title,
            "location": loc,
            "posted_days": days,
            "req_id": o.get("id"),
            "url": o.get("careers_url") or o.get("careers_apply_url"),
        }, ensure_ascii=False))
        matched += 1
        if matched >= a.limit:
            break

    print(f"{matched} matched @ {a.slug}"
          + (f" (<= {a.days:g}d)" if a.days is not None else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
