#!/usr/bin/env python3
"""BambooHR job-board adapter — public careers JSON, no auth.

BambooHR skews SMB. Every company board serves an unauthenticated JSON list (verified
2026-08-27):

    GET https://{slug}.bamboohr.com/careers/list

Returns {"meta":{"totalCount":N}, "result":[{id, jobOpeningName, departmentLabel,
employmentStatusLabel, location:{city,state}, isRemote}, …]} — but with **no post date**.
The date lives on the per-job detail endpoint, so for a title match we fetch:

    GET https://{slug}.bamboohr.com/careers/{id}/detail   → {datePosted, jobOpeningShareUrl}

BambooHR boards are small, so one detail request per *matched* title is cheap. No open slug
corpus exists, so this is a DISCOVERY-SEEDED source (like Breezy / SmartRecruiters / Recruitee):
point it at a company slug you've found (the subdomain of {slug}.bamboohr.com), not a bulk sweep.

APPLY CLASS: **provisional** — the apply form is a direct, no-account résumé upload (fill it in
real Chrome like Greenhouse), but with no *proven* end-to-end submit yet it runs a one-time
verify in Mode B before it auto-submits (see tools/apply_class.py).

NOTE: the vendor BambooHR-the-company hosts its OWN jobs on Greenhouse (slug `bamboohr17`), not
on a bamboohr.com board — don't let the vendor name confuse slug discovery.

Usage:
    python tools/fetch_bamboohr.py --slug acme --q "Product Manager|Program Manager" --days 7
    python tools/fetch_bamboohr.py --slug acme --limit 50

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

_UA = {"User-Agent": "autoapply-bamboohr/1.0", "Accept": "application/json"}


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def age_days(dt, now):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int((now - dt).total_seconds() // 86400)


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_list(slug, timeout=20):
    url = f"https://{slug}.bamboohr.com/careers/list"
    try:
        data = _get(url, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        print(f"ERROR: {slug} — {e}", file=sys.stderr)
        sys.exit(65)
    return data.get("result", []) if isinstance(data, dict) else []


def fetch_detail(slug, job_id, timeout=20):
    """Return (date_posted_str, share_url) — best-effort; a failed detail fetch is non-fatal."""
    url = f"https://{slug}.bamboohr.com/careers/{job_id}/detail"
    try:
        d = _get(url, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        return None, None
    # detail payload is {meta, result:{jobOpening:{…}, formFields}} — the date + canonical
    # share url live under result.jobOpening (fall back through looser shapes defensively).
    res = d.get("result", d) if isinstance(d, dict) else {}
    j = res.get("jobOpening", res) if isinstance(res, dict) else {}
    return j.get("datePosted"), j.get("jobOpeningShareUrl")


def loc_str(p):
    lo = p.get("location") or {}
    parts = [lo.get("city"), lo.get("state")]
    s = ", ".join(x for x in parts if x)
    if p.get("isRemote"):
        s = (s + " (remote)").strip() if s else "Remote"
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="BambooHR subdomain, e.g. acme ({slug}.bamboohr.com)")
    ap.add_argument("--company", help="display name override (defaults to the slug)")
    ap.add_argument("--q", help="case-insensitive regex on the title")
    ap.add_argument("--days", type=float, help="recency window on datePosted")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--now", help="ISO override for 'now' (testing)")
    a = ap.parse_args()

    now = (datetime.datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now
           else datetime.datetime.now(datetime.timezone.utc))
    title_re = re.compile(a.q, re.I) if a.q else None

    matched = 0
    for p in fetch_list(a.slug):
        title = p.get("jobOpeningName")
        if title_re and not (title and title_re.search(title)):
            continue
        job_id = p.get("id")
        date_posted, share_url = fetch_detail(a.slug, job_id)
        days = age_days(parse_dt(date_posted), now)
        if a.days is not None and days is not None and days > a.days:
            continue
        print(json.dumps({
            "ats": "bamboohr",
            "company": a.company or a.slug,
            "title": title,
            "location": loc_str(p),
            "posted_days": days,
            "req_id": job_id,
            "url": share_url or f"https://{a.slug}.bamboohr.com/careers/{job_id}",
        }, ensure_ascii=False))
        matched += 1
        if matched >= a.limit:
            break

    print(f"{matched} matched @ {a.slug}"
          + (f" (<= {a.days:g}d)" if a.days is not None else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
