#!/usr/bin/env python3
"""SmartRecruiters job-search adapter — public postings API, no auth.

SmartRecruiters skews toward large regulated-finance / payments enterprises (Visa, banks,
card networks, insurers) — the slice Greenhouse/Ashby/Lever underrepresent. Every company
exposes the same public endpoint (verified 2026-08-05 against Visa):

    GET https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=&offset=

Returns JSON: content[] with name, releasedDate (ISO, true post date), location, refNumber.
Public apply URL is https://jobs.smartrecruiters.com/{company}/{id} (verified 200).

Usage:
    python tools/fetch_smartrecruiters.py --company Visa --q "Product Manager|Program Manager" --days 7
    python tools/fetch_smartrecruiters.py --company Visa --limit 50

Emits one JSON object per matching posting to stdout (JSONL):
    company, title, location, posted_days (int|null), req_id, url
posted_days feeds the Phase-2 freshness banding and the --days recency window.
--q is a case-insensitive regex on the title. --company is the SmartRecruiters company id
(case-sensitive — take it from the real careers URL, e.g. jobs.smartrecruiters.com/Visa/...).
"""
import argparse
import datetime
import json
import re
import sys
import urllib.request
import urllib.error

_UA = {"User-Agent": "autoapply-smartrecruiters/1.0", "Accept": "application/json"}
PAGE = 100
MAX_PAGES = 30  # backstop so a huge company can't loop forever


def parse_iso(s):
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


def fetch(company, timeout=20):
    base = f"https://api.smartrecruiters.com/v1/companies/{company}/postings"
    offset, pages = 0, 0
    while pages < MAX_PAGES:
        req = urllib.request.Request(f"{base}?limit={PAGE}&offset={offset}", headers=_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"ERROR: {company} — {e}", file=sys.stderr)
            sys.exit(65)
        content = data.get("content", [])
        if not content:
            break
        for p in content:
            yield p
        offset += len(content)
        pages += 1
        if offset >= data.get("totalFound", 0):
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True, help="SmartRecruiters company id, e.g. Visa")
    ap.add_argument("--q", help="case-insensitive regex on the title")
    ap.add_argument("--days", type=float, help="recency window on releasedDate")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--now", help="ISO override for 'now' (testing)")
    a = ap.parse_args()

    now = parse_iso(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc)
    title_re = re.compile(a.q, re.I) if a.q else None

    matched = 0
    for p in fetch(a.company):
        title = p.get("name")
        if title_re and not (title and title_re.search(title)):
            continue
        days = age_days(parse_iso(p.get("releasedDate")), now)
        if a.days is not None and days is not None and days > a.days:
            continue
        loc = p.get("location") or {}
        loc_str = loc.get("fullLocation") or ", ".join(
            x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
        if loc.get("remote"):
            loc_str = (loc_str + " (remote)").strip()
        print(json.dumps({
            "company": a.company,
            "title": title,
            "location": loc_str,
            "posted_days": days,
            "req_id": p.get("refNumber"),
            "url": f"https://jobs.smartrecruiters.com/{a.company}/{p.get('id')}",
        }, ensure_ascii=False))
        matched += 1
        if matched >= a.limit:
            break

    print(f"{matched} matched @ {a.company}"
          + (f" (<= {a.days:g}d)" if a.days is not None else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
