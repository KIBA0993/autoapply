#!/usr/bin/env python3
"""Freeze the Mode B authorized set into an IMMUTABLE snapshot — the safety artifact.

Mode B (pre-authorized top-X) must dispatch from a set that cannot change mid-run: no
re-rank can slide in an unauthorized job, and the per-row screen state (Phase-2.5 dedupe
+ saturation) is computed ONCE, here, at kickoff — so nothing downstream (least of all a
throwaway worker for a large conductor/worker run) recomputes it against a staler export
or against this run's own just-submitted rows and gets a different answer.

What it does:
  - reads the screened, ranked pool (job_pool.csv), keeps only AUTO-class rows
    (apply_class: greenhouse/lever/ashby/workable + any *verified* ATS). Provisional
    (SmartRecruiters/Recruitee/Breezy, unverified) and manual/discovery are EXCLUDED —
    an unattended worker can't perform the one-time Mode-A verify a provisional needs,
    and account-gated ATSes can't self-submit at all.
  - takes the top-N in file (rank) order.
  - runs the Phase-2.5 dedupe + saturation check ONCE per row and records the verdict.
    By DEFAULT (user standing preference 2026-08-18) every row is dispatch_eligible
    EXCEPT an exact/near-exact title repeat (verdict 1 BLOCK) — saturated/seen/fuzzy-dup
    rows are dispatched. Pass --new-only to restrict to NEW-verdict rows. Non-eligible
    rows are pre-parked from the snapshot (the conductor never spawns a worker for them).
  - writes sources/run_<ts>_authorized.json ONCE. Refuses to overwrite an existing file.

The snapshot is the ONLY source of set membership for the run. The conductor dispatches
strictly by the `url` in this file and never re-runs apply_class or dedupe_check mid-run.

Usage:
  python tools/freeze_authorized.py --pool dashboard/job_pool.csv --status Ready --top 30
  python tools/freeze_authorized.py --show sources/run_<ts>_authorized.json
"""
import argparse
import csv
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from apply_class import classify, load_verified  # noqa: E402
import dedupe_check as dd  # noqa: E402
import jd_dq  # noqa: E402  — mechanical pre-dispatch disqualifiers (location)

OUT_DIR = os.path.join(ROOT, "sources")
_LABEL = {0: "NEW", 2: "SURFACE", 1: "BLOCK"}


def _norm_url(u):
    return (u or "").strip().rstrip("/")


def _excluded_urls():
    """Exact URLs already submitted (application_log) or declined (declined_postings) —
    they never re-enter a top-X. An exact-url guard that complements the fuzzy title
    dedupe: it catches the 'same posting, different company-name spelling' miss the
    title matcher can't, and stops a declined posting from taking a slot again."""
    urls = set()
    for r in dd.load_rows(os.path.join(ROOT, "dashboard", "application_log.csv")):
        status = (r.get("status") or "").strip().lower()
        if r.get("url") and (not status or "submit" in status or "confirm" in status):
            urls.add(_norm_url(r.get("url")))
    for r in dd.load_rows(os.path.join(ROOT, "dashboard", "declined_postings.csv")):
        if r.get("url"):
            urls.add(_norm_url(r.get("url")))
    return urls


def _found_cutoff(since_days):
    if not since_days:
        return None
    today = datetime.datetime.now(datetime.timezone.utc).date()
    return today - datetime.timedelta(days=since_days)


def _found_date(r):
    raw = (r.get("date_found") or "").strip()[:10]
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None   # blank/unparseable → treated as too-old under a recency window


def build(pool, status, top, include_saturated=False, since_days=7, cap=None, dq_location=True):
    # `top` is the SUBMIT TARGET; `cap` is how many candidates to actually freeze
    # (a buffer ≥ top). The dispatch loop walks the frozen list in rank order and stops
    # at `top` clean submissions, backfilling past any not-viable skip / hard block — so
    # the reserve rows (top+1 … cap) must already be in the authorized snapshot.
    cap = cap or top
    verified = load_verified()
    history = dd.load_rows(dd.HISTORY)
    stale = dd.staleness_line(history)          # Simplify export staleness only
    history = history + dd.load_applog()        # our own submits also count toward dedup
    saturation = dd.load_rows(dd.SATURATION)

    excluded_urls = _excluded_urls()
    cutoff = _found_cutoff(since_days)          # None => no recency filter (--all-dates)
    picked, n_excluded, n_old, n_dq = [], 0, 0, 0
    with open(pool, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if status and status.lower() not in (r.get("status", "").lower()):
                continue
            bucket, _submits, _reason = classify(r.get("ats", ""), verified)
            if bucket != "auto":
                continue
            if cutoff is not None:
                fd = _found_date(r)
                if fd is None or fd < cutoff:
                    n_old += 1     # found before the recency window — an old backlog row, skip it
                    continue
            if _norm_url(r.get("job_url", "")) in excluded_urls:
                n_excluded += 1        # already submitted/declined — don't let it take a top-X slot
                continue
            # Mechanical location DQ — fail-safe: only drops rows that positively name a US
            # location outside the allowed metros (remote/blank/unknown are kept). A dropped row
            # just backfills, so a false drop never costs a wrong submit — only one candidate.
            if dq_location and not jd_dq.location_ok(r.get("location", ""), r.get("remote_policy", "")):
                n_dq += 1
                continue
            picked.append(r)
            if cap and len(picked) >= cap:
                break

    jobs = []
    for i, r in enumerate(picked, 1):
        company = r.get("company", "")
        title = r.get("job_title", "")
        verdict, lines = dd.check_one(company, title, history, saturation)
        # default: only NEW dispatches; rest pre-parked. With --include-saturated (user
        # opt-in, Option A): everything dispatches EXCEPT an exact/near-exact title repeat
        # (verdict 1 BLOCK) — saturated/seen/fuzzy-dup rows become eligible.
        eligible = (verdict != 1) if include_saturated else (verdict == 0)
        jobs.append({
            "seq": i,
            "url": (r.get("job_url", "") or "").strip(),
            "company": company,
            "title": title,
            "ats": (r.get("ats", "") or "").strip().lower(),
            "screen_verdict": _LABEL[verdict],   # frozen at kickoff — consume, never recompute
            "screen_notes": lines,               # DUP/HEAVY/SATURATED/etc. for park messaging
            "dispatch_eligible": eligible,
            # primary = the first `top` candidates; reserve = the backfill buffer the loop
            # reaches into only when an earlier row is a not-viable skip / hard block.
            "tier": "primary" if i <= top else "reserve",
        })
    return jobs, stale, n_excluded, n_old, n_dq


def show(path):
    with open(path, encoding="utf-8") as f:
        snap = json.load(f)
    elig = sum(1 for j in snap["jobs"] if j["dispatch_eligible"])
    mode = "include-saturated" if snap.get("include_saturated") else "new-only"
    sd = snap.get("since_days")
    window = "all-dates" if sd is None else f"found≤{sd}d"
    target = snap.get("target_submits", snap["top_x"])
    print(f"run_id={snap['run_id']}  created={snap['created']}  target={target}  "
          f"buffer={snap.get('buffer_cap', len(snap['jobs']))}  mode={mode}  window={window}  "
          f"frozen={len(snap['jobs'])}  eligible={elig}")
    if snap.get("staleness"):
        print(snap["staleness"])
    for j in snap["jobs"]:
        flag = "DISPATCH " if j["dispatch_eligible"] else "PRE-PARK "
        tier = j.get("tier", "primary")
        print(f"  {j['seq']:>2} {flag}[{j['screen_verdict']:<7}] ({tier:<7}) "
              f"{j['company']} · {j['title']}  [{j['ats']}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default=os.path.join(ROOT, "dashboard", "job_pool.csv"),
                    help="screened, ranked pool CSV")
    ap.add_argument("--status", default="Ready",
                    help="only rows whose status contains this (case-insensitive)")
    ap.add_argument("--top", type=int, default=30,
                    help="the SUBMIT TARGET — the loop dispatches until this many clean submits, "
                         "backfilling past not-viable skips / hard blocks.")
    ap.add_argument("--buffer", type=int, default=None,
                    help="how many candidates to actually freeze (the backfill reserve). "
                         "Default = 2×--top. Reserve rows (past --top) are dispatched only to "
                         "replace an earlier skip/block, never to exceed the target.")
    ap.add_argument("--out", help="snapshot path (default sources/run_<ts>_authorized.json)")
    ap.add_argument("--new-only", action="store_true",
                    help="restrict to NEW-verdict rows only. Default (standing preference) "
                         "dispatches saturated/seen/fuzzy-dup rows too, parking only "
                         "exact/near-exact title repeats.")
    ap.add_argument("--since-days", type=int, default=7,
                    help="only freeze postings whose date_found is within this many days "
                         "(standing preference 2026-08-19: a kickoff targets newly-added "
                         "postings, not the whole Ready backlog). Use --all-dates to disable.")
    ap.add_argument("--all-dates", action="store_true",
                    help="disable the date_found recency window (freeze the whole backlog).")
    ap.add_argument("--no-dq", action="store_true",
                    help="disable the mechanical location DQ (by default rows that positively name "
                         "a US location outside your home metro/the other target metros are dropped pre-dispatch; "
                         "remote/blank/unknown are always kept).")
    ap.add_argument("--show", metavar="SNAPSHOT", help="print an existing snapshot and exit")
    a = ap.parse_args()

    if a.show:
        show(a.show)
        return

    include_saturated = not a.new_only   # standing default = include saturated/seen (2026-08-18)
    since_days = None if a.all_dates else a.since_days
    cap = a.buffer if a.buffer else a.top * 2   # backfill reserve = 2×target by default
    jobs, stale, n_excluded, n_old, n_dq = build(a.pool, a.status, a.top, include_saturated,
                                                 since_days, cap, dq_location=not a.no_dq)
    if not jobs:
        print("no auto-class rows matched — nothing to freeze", file=sys.stderr)
        sys.exit(1)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = a.out or os.path.join(OUT_DIR, f"run_{ts}_authorized.json")
    if os.path.exists(out):
        print(f"refusing to overwrite existing snapshot: {out}", file=sys.stderr)
        sys.exit(3)

    snap = {
        "run_id": ts,
        "created": ts,
        "top_x": a.top,          # submit TARGET — stop after this many clean submits
        "target_submits": a.top,
        "buffer_cap": cap,       # reserve candidates frozen for backfill
        "include_saturated": include_saturated,
        "since_days": since_days,
        "pool": os.path.relpath(a.pool, ROOT),
        "staleness": stale,
        "jobs": jobs,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)
    os.replace(tmp, out)   # target didn't exist (checked above) — write is effectively write-once

    elig = sum(1 for j in jobs if j["dispatch_eligible"])
    n_primary = sum(1 for j in jobs if j.get("tier") == "primary")
    window = "all dates" if since_days is None else f"found within {since_days}d"
    print(f"froze {len(jobs)} auto-class rows [{window}] "
          f"(target {a.top} submits; {n_primary} primary + {len(jobs) - n_primary} reserve for backfill; "
          f"{elig} eligible, {len(jobs) - elig} pre-parked; "
          f"{n_excluded} already-submitted/declined skipped, {n_old} older-than-window skipped, "
          f"{n_dq} location-ineligible skipped) "
          f"-> {os.path.relpath(out, ROOT)}")
    if stale:
        print(stale, file=sys.stderr)


if __name__ == "__main__":
    main()
