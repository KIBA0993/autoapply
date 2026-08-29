#!/usr/bin/env python3
"""Atomically APPEND new rows to job_pool.csv. The sanctioned way to add rows found by a
sweep/screen pass — companion to job_pool_update.py, which only mutates an existing row
matched by job_url.

Why this exists: job_pool.csv was corrupted on 2026-08-20 by ad-hoc rewrites (naive
regex/Edit rewrites of the whole file — not atomic, and don't guarantee CSV quoting on a
comma-heavy `notes` field). This tool reads with the csv module, appends new row dicts in
memory, and writes via temp-file + os.replace (atomic — a reader always sees the whole old
or whole new file). It also skips a row whose job_url already exists in the pool, so a
re-run of the same sweep never double-appends.

Usage:
  python tools/job_pool_append.py --rows path/to/new_rows.json
  # new_rows.json is a JSON array of objects; keys must be a subset of the pool's header.
  # Missing keys are written as "". Unknown keys abort (fail closed, no silent column drop).

Single-writer discipline still applies: don't run two sessions writing the pool at once.
"""
import argparse
import csv
import json
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
    ap.add_argument("--rows", required=True, help="JSON file: array of row objects to append")
    ap.add_argument("--pool", default=POOL, help="pool CSV (default dashboard/job_pool.csv)")
    ap.add_argument("--allow-dup-url", action="store_true",
                     help="append even if job_url already exists in the pool (default: skip)")
    a = ap.parse_args()

    with open(a.rows, encoding="utf-8") as f:
        new_rows = json.load(f)
    if not isinstance(new_rows, list):
        print("--rows file must contain a JSON array of row objects", file=sys.stderr)
        sys.exit(64)

    with open(a.pool, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        existing = list(reader)
    if fieldnames is None:
        print("empty/unreadable pool", file=sys.stderr)
        sys.exit(1)

    existing_urls = {_norm(r.get(URL_COL)) for r in existing}

    appended, skipped_dup = 0, 0
    out_rows = list(existing)
    for i, row in enumerate(new_rows):
        unknown = set(row.keys()) - set(fieldnames)
        if unknown:
            print(f"row {i}: unknown column(s) {sorted(unknown)} — pool columns are: "
                  f"{', '.join(fieldnames)}", file=sys.stderr)
            sys.exit(64)
        u = _norm(row.get(URL_COL))
        if u and u in existing_urls and not a.allow_dup_url:
            skipped_dup += 1
            continue
        out_rows.append({c: row.get(c, "") for c in fieldnames})
        if u:
            existing_urls.add(u)
        appended += 1

    tmp = a.pool + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in out_rows:
            w.writerow({c: r.get(c, "") for c in fieldnames})
    os.replace(tmp, a.pool)  # atomic swap — a concurrent reader never sees a half-written file

    print(f"appended {appended} row(s), skipped {skipped_dup} duplicate-url row(s); "
          f"pool now has {len(out_rows)} rows")


if __name__ == "__main__":
    main()
