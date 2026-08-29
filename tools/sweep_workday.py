#!/usr/bin/env python3
"""Workday sweep — run the CXS search across many tenants, fail-open per tenant.

The broad-coverage companion to tools/fetch_workday.py (single tenant). Workday runs a
huge share of ENTERPRISE careers sites (NVIDIA, Adobe, Salesforce, Cisco, Dell...) that
are absent from Greenhouse/Ashby/Lever — this sweeps all of them in one pass.

Each tenant is a "tenant|datacenter|site" triple (from sources/workday_companies.json,
sourced from the open Feashliaa corpus). For each, we POST:
    {host}/wday/cxs/{tenant}/{site}/jobs   with searchText = --q
Workday does the title match SERVER-SIDE, so --q keeps each response small.

IMPORTANT — no delta here. Unlike delta_sweep.py (Greenhouse/Ashby/Lever), Workday is a
paginated POST with NO ETag/If-None-Match support, so there is no 304 shortcut: every run
is a full fetch. Recency is done on Workday's coarse postedOn field (Today/Yesterday/N Days)
via --days. That's the documented cost of Workday coverage.

A tenant that errors (dead site name, throttle, timeout) is counted and SKIPPED — one bad
triple never aborts the sweep (contrast fetch_workday.py, which sys.exits on any error).

Input: --companies FILE (JSON {"sources":["tenant|dc|site",...]} or a bare list), or the
same triples as TSV/lines on stdin. Output: one JSON object per matching posting (JSONL):
  ats, company, title, location, posted_days, req_id, url
Summary to stderr: tenants / with-hits / empty / errors / postings emitted.

  python tools/sweep_workday.py --companies sources/workday_companies.json --q "product manager" --days 3
  python tools/sweep_workday.py --companies sources/workday_companies.json --q manager --title 'product manager|program manager' --days 7
"""
import argparse
import json
import os
import re
import signal
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_workday import parse_posted_days  # reuse the postedOn parser

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) autoapply-wd-sweep/1.0",
}


def fetch_tenant(triple, query, limit, page_size=20, timeout=25):
    """POST the CXS search for one tenant. Returns (status, rows).
    status: 'hit' | 'empty' | 'error'. Never raises — fail-open."""
    parts = triple.split("|")
    if len(parts) != 3:
        return "error", []
    tenant, dc, site = parts
    host = f"{tenant}.{dc}.myworkdayjobs.com"
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    rows, offset = [], 0
    try:
        while len(rows) < limit:
            body = json.dumps({
                "appliedFacets": {},
                "limit": min(page_size, limit - len(rows)),
                "offset": offset,
                "searchText": query,
            }).encode()
            req = urllib.request.Request(url, data=body, headers=_HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            postings = data.get("jobPostings", [])
            total = data.get("total", 0)
            if not postings:
                break
            for j in postings:
                ext = j.get("externalPath", "")
                rows.append({
                    "ats": "workday",
                    "company": tenant,
                    "title": j.get("title"),
                    "location": j.get("locationsText"),
                    "posted_days": parse_posted_days(j.get("postedOn")),
                    "req_id": (j.get("bulletFields") or [None])[0],
                    "url": f"https://{host}/{site}{ext}" if ext else None,
                })
                if len(rows) >= limit:
                    break
            offset += len(postings)
            if offset >= total:
                break
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        return "error", []
    return ("hit" if rows else "empty"), rows


def load_triples(args):
    if args.companies:
        raw = json.load(open(args.companies))
        items = raw.get("sources", raw) if isinstance(raw, dict) else raw
        return [x if isinstance(x, str) else "|".join((x["tenant"], x.get("dc", ""), x["site"]))
                for x in items]
    return [ln.strip() for ln in sys.stdin if ln.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", help='JSON {"sources":["tenant|dc|site",...]} or a bare list; else lines on stdin')
    ap.add_argument("--q", default="product manager", help="Workday server-side searchText")
    ap.add_argument("--title", help="extra client-side regex on the title (precision on top of --q)")
    ap.add_argument("--days", type=float, help="recency window on postedOn (Today=0, Yesterday=1, 'N Days')")
    ap.add_argument("--limit", type=int, default=50, help="max postings pulled per tenant")
    ap.add_argument("--concurrency", type=int, default=16)
    a = ap.parse_args()

    triples = load_triples(a)
    if not triples:
        print("no tenants (need --companies FILE or triples on stdin)", file=sys.stderr)
        sys.exit(64)

    title_re = re.compile(a.title, re.I) if a.title else None

    def work(t):
        return (t, *fetch_tenant(t, a.q, a.limit))

    # Turn a timeout/kill (SIGTERM) into a graceful KeyboardInterrupt so the finally flush runs.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))

    hits = empty = errors = emitted = processed = 0
    FLUSH_EVERY = 200  # flush stdout periodically so a killed/redirected run keeps its rows

    ex = ThreadPoolExecutor(max_workers=a.concurrency)
    futures = [ex.submit(work, t) for t in triples]
    try:
        # as_completed (not ex.map): a slow tenant (up to the 25s timeout) no longer stalls
        # the tenants behind it.
        for fut in as_completed(futures):
            triple, status, rows = fut.result()
            processed += 1
            if status == "error":
                errors += 1
            elif status == "empty":
                empty += 1
            else:
                hits += 1
                for row in rows:
                    t = row["title"]
                    if title_re and not (t and title_re.search(t)):
                        continue
                    d = row["posted_days"]
                    if a.days is not None and d is not None and d > a.days:
                        continue
                    print(json.dumps(row, ensure_ascii=False))
                    emitted += 1
            if processed % FLUSH_EVERY == 0:
                sys.stdout.flush()
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
        sys.stdout.flush()

    print(f"{len(triples)} tenants: {hits} with-hits, {empty} empty, {errors} error "
          f"| {emitted} postings emitted", file=sys.stderr)


if __name__ == "__main__":
    main()
