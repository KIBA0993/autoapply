#!/usr/bin/env python3
"""Atomically update ONE job_pool.csv row, matched by job_url. The ONLY sanctioned way to write
a status / marker / skip_reason back to the pool.

Why this exists: job_pool.csv was corrupted on 2026-08-20 because row updates (the
"submit-attempted marker", status changes) were done ad-hoc — a naive rewrite or an Edit — which
(a) isn't atomic, so a concurrent reader/writer catches a half-written file, and (b) doesn't
guarantee CSV quoting, so a comma-heavy `notes` field ragged the columns. This tool fixes both:
it reads with the csv module (correct quoting), mutates the matched row in memory, and writes via
temp-file + os.replace (atomic — a reader always sees the whole old or whole new file).

Single-writer discipline still applies: don't run two sessions writing the pool at once. This
tool makes each individual write safe; it can't serialize two separate processes.

Usage:
  # mark submit-attempted BEFORE clicking submit (durable marker; never re-applied on resume):
  python tools/job_pool_update.py --url <job_url> --set status="Submit-attempted"
  # record a terminal state + reason:
  python tools/job_pool_update.py --url <job_url> --set status=Submitted
  python tools/job_pool_update.py --url <job_url> --set status=Skipped --set skip_reason="jd-dq:comp-ceiling"
  python tools/job_pool_update.py --url <job_url> --set status="Needs input" --set blocker="non-standard consent"
  # append a timestamped line to notes (kept, never overwritten):
  python tools/job_pool_update.py --url <job_url> --note "Mode B run <id> seq7: submit-attempted marker"

--set overwrites a column; --note appends to `notes`. URL match is normalized (trim + strip
trailing slash). Exits non-zero if the url isn't found (so a caller notices a bad dispatch).
"""
import argparse
import csv
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POOL = os.path.join(ROOT, "dashboard", "job_pool.csv")
URL_COL = "job_url"


def _norm(u):
    return (u or "").strip().rstrip("/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="the exact job_url of the row to update")
    ap.add_argument("--set", action="append", default=[], metavar="COL=VALUE",
                    help="overwrite a column (repeatable), e.g. --set status=Submitted")
    ap.add_argument("--note", default=None, help="append a timestamped line to the notes column")
    ap.add_argument("--pool", default=POOL, help="pool CSV (default dashboard/job_pool.csv)")
    a = ap.parse_args()

    updates = {}
    for kv in a.set:
        if "=" not in kv:
            print(f"bad --set (need COL=VALUE): {kv}", file=sys.stderr)
            sys.exit(64)
        col, val = kv.split("=", 1)
        updates[col.strip()] = val
    if not updates and a.note is None:
        print("nothing to do — pass --set and/or --note", file=sys.stderr)
        sys.exit(64)

    with open(a.pool, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if fieldnames is None:
        print("empty/unreadable pool", file=sys.stderr)
        sys.exit(1)

    for col in updates:
        if col not in fieldnames:
            print(f"unknown column '{col}' — pool columns are: {', '.join(fieldnames)}",
                  file=sys.stderr)
            sys.exit(64)

    target = _norm(a.url)
    matches = [r for r in rows if _norm(r.get(URL_COL)) == target]
    if not matches:
        print(f"url not found in pool: {a.url}", file=sys.stderr)
        sys.exit(3)
    if len(matches) > 1:
        print(f"WARN: {len(matches)} rows match this url — updating all", file=sys.stderr)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    for r in matches:
        for col, val in updates.items():
            r[col] = val
        if a.note is not None:
            existing = (r.get("notes") or "").strip()
            line = f"[{ts}] {a.note}"
            r["notes"] = f"{existing} | {line}" if existing else line

    tmp = a.pool + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in fieldnames})
    os.replace(tmp, a.pool)   # atomic swap — a concurrent reader never sees a half-written file

    what = ", ".join(f"{k}={v!r}" for k, v in updates.items())
    if a.note is not None:
        what = (what + "; " if what else "") + f"note+={a.note!r}"
    print(f"updated {len(matches)} row(s) [{target}]: {what}")


if __name__ == "__main__":
    main()
