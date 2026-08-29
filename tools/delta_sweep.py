#!/usr/bin/env python3
"""Delta sweep — ETag-conditional board fetch across many companies.

The efficiency engine for scanning a large company list every run. Two layers of delta:

  Layer 1 (this tool): board-level. Store each board's ETag; next run send it back as
    If-None-Match. Unchanged boards reply HTTP 304 with 0 bytes — skip them, no download,
    no parse. Verified 2026-08-05 that Greenhouse/Ashby/Lever all return ETags and honor
    conditional GETs (Greenhouse 304 => 0 bytes). Most boards don't change day to day, so
    a daily "scan everything" run is mostly cheap 304s after the first baseline.

  Layer 2 (downstream, existing tools): job-level. This tool emits the CURRENT postings
    from CHANGED boards; dedupe_check.py (vs job_pool.csv) drops the ones already seen, so
    only genuinely-new postings survive. liveness_check.py catches closures.

Supports the three slug-based public APIs: greenhouse, ashby, lever.
(Workday/SmartRecruiters paginate differently — use their own fetch_* adapters.)

Input: companies as JSON [{"ats","slug"}, ...] via --companies FILE, or TSV "ats<TAB>slug"
on stdin. ETag store persists in --etag-cache (default sources/etag_cache.json).

Output: one JSON object per matching posting (JSONL):
  ats, company, title, location, posted_days, req_id, url
Summary to stderr: boards checked / unchanged(304) / changed / errors / postings emitted.

  python tools/delta_sweep.py --companies sources/companies.json --title 'Product Manager' --days 3
  printf 'greenhouse\tnovacredit\nashby\tsocure\n' | python tools/delta_sweep.py --title 'Product Manager'
"""
import argparse
import datetime
import json
import os
import re
import signal
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CACHE = os.path.join(HERE, "..", "sources", "etag_cache.json")
_UA = {"User-Agent": "autoapply-delta/1.0", "Accept": "application/json"}

ENDPOINT = {
    "greenhouse": lambda s: f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs",
    "ashby":      lambda s: f"https://api.ashbyhq.com/posting-api/job-board/{s}",
    "lever":      lambda s: f"https://api.lever.co/v0/postings/{s}?mode=json",
}


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


def rows_from(ats, slug, data, now):
    """Normalize a board payload into [(title, location, url, posted_days, req_id)]."""
    out = []
    if ats == "greenhouse":
        for j in data.get("jobs", []):
            dt = parse_iso(j.get("first_published")) or parse_iso(j.get("updated_at"))
            out.append((j.get("title"), (j.get("location") or {}).get("name", ""),
                        j.get("absolute_url"), age_days(dt, now), j.get("id")))
    elif ats == "ashby":
        for j in data.get("jobs", []):
            dt = parse_iso(j.get("publishedAt"))
            out.append((j.get("title"), j.get("location") or "",
                        j.get("jobUrl") or j.get("applyUrl"), age_days(dt, now), j.get("id")))
    elif ats == "lever":
        for j in (data if isinstance(data, list) else []):
            ms = j.get("createdAt")
            dt = (datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)
                  if isinstance(ms, (int, float)) else None)
            out.append((j.get("text"), (j.get("categories") or {}).get("location", ""),
                        j.get("hostedUrl"), age_days(dt, now), j.get("id")))
    return out


def fetch_board(ats, slug, etag):
    """Conditional GET. Returns (status, new_etag, data|None).
    status: 'unchanged' (304) | 'changed' (200) | 'error'."""
    url = ENDPOINT[ats](slug)
    headers = dict(_UA)
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            new_etag = r.headers.get("ETag")
            return "changed", new_etag, json.loads(body)
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return "unchanged", etag, None
        return "error", etag, None
    except Exception:
        return "error", etag, None


def save_cache(path, cache):
    """Atomic write (temp file + os.replace) so a run killed mid-write can't corrupt the
    cache — a corrupted cache silently falls back to empty and forces a cold, slow re-run."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f, indent=0)
    os.replace(tmp, path)


def load_companies(args):
    if args.companies:
        raw = json.load(open(args.companies))
        items = raw.get("sources", raw) if isinstance(raw, dict) else raw
        return [(c["ats"].lower(), c["slug"]) for c in items
                if c.get("ats", "").lower() in ENDPOINT and c.get("slug")]
    out = []
    for line in sys.stdin:
        p = line.rstrip("\n").split("\t")
        if len(p) >= 2 and p[0].strip().lower() in ENDPOINT:
            out.append((p[0].strip().lower(), p[1].strip()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", help="JSON [{ats,slug}] or {sources:[...]}; else read TSV from stdin")
    ap.add_argument("--etag-cache", default=DEFAULT_CACHE)
    ap.add_argument("--title", help="case-insensitive regex on the title")
    ap.add_argument("--days", type=float, help="recency window on the post date")
    ap.add_argument("--concurrency", type=int, default=24)
    ap.add_argument("--now", help="ISO override for 'now' (testing)")
    a = ap.parse_args()

    companies = load_companies(a)
    if not companies:
        print("no companies (need --companies FILE or TSV on stdin)", file=sys.stderr)
        sys.exit(64)

    cache = {}
    if os.path.exists(a.etag_cache):
        try:
            cache = json.load(open(a.etag_cache))
        except Exception:
            cache = {}

    now = parse_iso(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc)
    title_re = re.compile(a.title, re.I) if a.title else None

    def work(item):
        ats, slug = item
        key = f"{ats}:{slug}"
        status, new_etag, data = fetch_board(ats, slug, cache.get(key))
        return key, ats, slug, status, new_etag, data

    # Turn a timeout/kill (SIGTERM, e.g. a foreground command hitting the harness cap) into
    # a graceful KeyboardInterrupt so the finally-block flush still runs.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))

    unchanged = changed = errors = emitted = processed = 0
    dirty = False
    FLUSH_EVERY = 500  # persist ETag progress mid-run so an interrupt loses <=500 boards, not all

    ex = ThreadPoolExecutor(max_workers=a.concurrency)
    futures = [ex.submit(work, item) for item in companies]
    try:
        # as_completed (not ex.map): one slow board no longer stalls processing of the boards
        # behind it, and progress is flushed as results land rather than only at the very end.
        for fut in as_completed(futures):
            key, ats, slug, status, new_etag, data = fut.result()
            processed += 1
            if status == "unchanged":
                unchanged += 1
            elif status == "error":
                errors += 1
            else:
                changed += 1
                if new_etag:
                    cache[key] = new_etag
                    dirty = True
                for title, loc, url, days, jid in rows_from(ats, slug, data, now):
                    if title_re and not (title and title_re.search(title)):
                        continue
                    if a.days is not None and days is not None and days > a.days:
                        continue
                    print(json.dumps({"ats": ats, "company": slug, "title": title,
                                      "location": loc, "posted_days": days,
                                      "req_id": jid, "url": url}, ensure_ascii=False))
                    emitted += 1
            if processed % FLUSH_EVERY == 0 and dirty:
                sys.stdout.flush()
                save_cache(a.etag_cache, cache)
                dirty = False
    finally:
        # Persist whatever we have — even on Ctrl-C / SIGTERM / exception — and stop pending work.
        ex.shutdown(wait=False, cancel_futures=True)
        if dirty:
            save_cache(a.etag_cache, cache)
        sys.stdout.flush()

    print(f"{len(companies)} boards: {unchanged} unchanged(304), {changed} changed, "
          f"{errors} error | {emitted} postings emitted", file=sys.stderr)


if __name__ == "__main__":
    main()
