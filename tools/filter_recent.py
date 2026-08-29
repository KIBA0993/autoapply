#!/usr/bin/env python3
"""Recency window for the find phase — keep only postings newer than N days/hours.

For a daily / regular refresh you don't want the whole board every run, only what's
*newly posted* since last time. Each ATS exposes a true first-posted date (verified
2026-08-05), so the window is accurate — not just "last edited":

  greenhouse : first_published   (ISO; falls back to updated_at if absent)
  ashby      : publishedAt       (ISO)
  lever      : createdAt         (epoch ms)
  workday    : use tools/fetch_workday.py — it already emits posted_days; filter on that.

Reads a board API response on stdin, prints only in-window rows as TSV:
  title <TAB> location <TAB> url <TAB> posted_date <TAB> age_days
so a batch of matches drops straight into job_pool.csv without entering model context.

Usage:
  curl -s <greenhouse board API> | python tools/filter_recent.py --ats greenhouse --days 3
  curl -s <ashby board API>      | python tools/filter_recent.py --ats ashby --hours 24 --title 'Product Manager'
  curl -s <lever board API>      | python tools/filter_recent.py --ats lever --days 7

--title is an optional case-insensitive regex on the title (combine recency + role filter
in one pass). --now (ISO) overrides "now" for deterministic testing.
Exit: 0 if any rows matched, 3 if none matched, 64 usage.
"""
import argparse
import datetime
import json
import re
import sys


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        return None


def extract(ats, j):
    """Return (title, location, url, posted_dt) for one job, or None to skip."""
    ats = ats.lower()
    if ats in ("greenhouse", "gh"):
        dt = parse_iso(j.get("first_published")) or parse_iso(j.get("updated_at"))
        loc = (j.get("location") or {}).get("name", "")
        return j.get("title"), loc, j.get("absolute_url"), dt
    if ats == "ashby":
        dt = parse_iso(j.get("publishedAt"))
        loc = j.get("location") or ""
        return j.get("title"), loc, j.get("jobUrl") or j.get("applyUrl"), dt
    if ats == "lever":
        ms = j.get("createdAt")
        dt = (datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc)
              if isinstance(ms, (int, float)) else None)
        loc = (j.get("categories") or {}).get("location") or j.get("country") or ""
        return j.get("text"), loc, j.get("hostedUrl"), dt
    return None


def jobs_of(ats, data):
    if isinstance(data, list):           # lever
        return data
    return data.get("jobs", [])          # greenhouse / ashby


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ats", required=True, choices=["greenhouse", "gh", "ashby", "lever"])
    ap.add_argument("--days", type=float)
    ap.add_argument("--hours", type=float)
    ap.add_argument("--title", help="case-insensitive regex filter on the title")
    ap.add_argument("--now", help="ISO override for 'now' (testing)")
    a = ap.parse_args()

    if a.days is None and a.hours is None:
        print("need --days or --hours", file=sys.stderr)
        sys.exit(64)
    window_h = (a.hours if a.hours is not None else a.days * 24)

    now = parse_iso(a.now) if a.now else datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    title_re = re.compile(a.title, re.I) if a.title else None

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"bad JSON on stdin: {e}", file=sys.stderr)
        sys.exit(64)

    matched = 0
    undated = 0
    for j in jobs_of(a.ats, data):
        rec = extract(a.ats, j)
        if not rec:
            continue
        title, loc, url, dt = rec
        if title_re and not (title and title_re.search(title)):
            continue
        if dt is None:
            undated += 1            # no date -> can't window; surface separately, don't drop silently
            print(f"{title}\t{loc}\t{url}\t?\t?")
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        age_h = (now - dt).total_seconds() / 3600
        if age_h <= window_h:
            matched += 1
            print(f"{title}\t{loc}\t{url}\t{dt.date().isoformat()}\t{age_h/24:.1f}")

    print(f"{matched} within {window_h:.0f}h"
          + (f", {undated} undated (shown with '?')" if undated else ""),
          file=sys.stderr)
    sys.exit(0 if (matched or undated) else 3)


if __name__ == "__main__":
    main()
