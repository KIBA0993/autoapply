#!/usr/bin/env python3
"""Liveness pre-filter — prune dead/closed postings during SEARCH, not in Phase 3.

Leads pulled fresh from a same-run board sweep are live by construction. But BACKLOG
rows (job_pool.csv rows from earlier runs) and any search-sourced lead can be closed by
now — and discovering that during a fill wastes a full-context round-trip per dead row.
On the 2026-08-05 run, ~8 rows were re-verified dead one-by-one late in the flow (Jobber
404, Sift/Astra/Anchorage closed, Deel empty board).

This checks liveness at the API level, cheaply and concurrently, and prints only the DEAD
(and UNKNOWN) rows so the caller can drop them before screening/tailoring.

Detection (verified 2026-08-05):
  greenhouse : GET boards-api.greenhouse.io/v1/boards/{slug}/jobs/{id}  -> 200 live / 404 dead
  lever      : GET api.lever.co/v0/postings/{slug}/{id}?mode=json       -> 200 live / 404 dead
  ashby      : GET api.ashbyhq.com/posting-api/job-board/{slug}, id in list -> live / absent -> dead
  (branded/embedded GH wrappers like brex: use ats=greenhouse with the GH slug)

Input: TSV on stdin, one lead per line:  ats<TAB>slug<TAB>id
Output: one line per NON-live lead. Nothing for live leads (like dedupe_check).
  DEAD:    {ats} {slug}/{id}
  UNKNOWN: {ats} {slug}/{id} — {reason}   (network error / bad input — do NOT prune; verify)
Exit: 0 all live · 2 some dead/unknown (surface) · 64 usage.

Fail-open on network error: an UNKNOWN is never treated as dead, so a transient outage
never drops a live job. Only a definitive 404 / absent-from-list marks DEAD.
"""
import sys
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

TIMEOUT = 12
_UA = {"User-Agent": "autoapply-liveness/1.0"}
_ashby_cache = {}  # slug -> set(ids) | None (fetch failed)


def _http_status(url):
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def _ashby_ids(slug):
    if slug in _ashby_cache:
        return _ashby_cache[slug]
    req = urllib.request.Request(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}", headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read())
        ids = {str(j.get("id")) for j in data.get("jobs", [])}
    except Exception:
        ids = None
    _ashby_cache[slug] = ids
    return ids


def check(ats, slug, jid):
    """Return ('live'|'dead'|'unknown', reason)."""
    ats = (ats or "").strip().lower()
    if ats in ("greenhouse", "gh"):
        s = _http_status(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{jid}")
        if s == 200:
            return "live", ""
        if s == 404:
            return "dead", ""
        return "unknown", f"http {s}"
    if ats == "lever":
        s = _http_status(f"https://api.lever.co/v0/postings/{slug}/{jid}?mode=json")
        if s == 200:
            return "live", ""
        if s == 404:
            return "dead", ""
        return "unknown", f"http {s}"
    if ats == "ashby":
        ids = _ashby_ids(slug)
        if ids is None:
            return "unknown", "board fetch failed"
        return ("live", "") if str(jid) in ids else ("dead", "")
    return "unknown", f"unsupported ats '{ats}'"


def main():
    rows = []
    for raw in sys.stdin:
        raw = raw.rstrip("\n")
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) < 3:
            print(f"UNKNOWN: {raw} — need ats<TAB>slug<TAB>id", file=sys.stderr)
            continue
        rows.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    if not rows:
        print("usage: liveness_check.py  < leads.tsv   (ats<TAB>slug<TAB>id per line)",
              file=sys.stderr)
        sys.exit(64)

    # Ashby board lists are shared per slug — prefetch once, single-threaded, to seed cache.
    for slug in {slug for ats, slug, _ in rows if ats.strip().lower() == "ashby"}:
        _ashby_ids(slug)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda r: (r, check(*r)), rows))

    dead = unknown = 0
    for (ats, slug, jid), (verdict, reason) in results:
        if verdict == "dead":
            dead += 1
            print(f"DEAD:    {ats} {slug}/{jid}")
        elif verdict == "unknown":
            unknown += 1
            print(f"UNKNOWN: {ats} {slug}/{jid} — {reason}  (do NOT prune; verify)")
    live = len(rows) - dead - unknown
    print(f"\n{live} live, {dead} dead, {unknown} unknown of {len(rows)} checked",
          file=sys.stderr)
    sys.exit(2 if (dead or unknown) else 0)


if __name__ == "__main__":
    main()
