#!/usr/bin/env python3
"""Independently confirm a Mode B worker's 'submitted' claim — the trust check.

A conductor/worker Mode B run discards each worker's context, so the only thing that
returns is the worker's receipt. A receipt that SAYS 'submitted' is not trusted on its
prose: this verifies the two deterministic side effects a real submit leaves behind, both
written by log_application.py —
  1. the archive folder dashboard/applications/<date>_<company>_<title>/ exists and is
     non-empty, and
  2. a row in dashboard/application_log.csv matches the job (by url, else company+title).
If either is missing, the conductor must DOWNGRADE the receipt to couldnt_confirm — never
count it as submitted, and (per the never-re-dispatch rule) never re-queue it.

Exit 0 = both confirmed.  Exit 1 = not confirmed (downgrade).  Exit 64 = usage.

  python tools/verify_submit.py --company "Novacredit" --title "Senior PM, Credit" \
    --url https://job-boards.greenhouse.io/novacredit/jobs/123
"""
import argparse
import csv
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from log_application import slug, DEFAULT_LOG, DEFAULT_ARCHIVE, ROOT  # noqa: E402


def find_archive(company, title, date=None):
    """Non-empty archive folders matching this company+title (any date, or a given one)."""
    tail = f"{slug(company)}_{slug(title)}"
    hits = [d for d in glob.glob(os.path.join(DEFAULT_ARCHIVE, f"*_{tail}"))
            if os.path.isdir(d)]
    if date:
        dated = [d for d in hits if os.path.basename(d).startswith(date + "_")]
        hits = dated or hits
    return [d for d in hits if os.listdir(d)]


def find_log_row(url, company, title, log=DEFAULT_LOG):
    if not os.path.exists(log):
        return None
    with open(log, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    u = (url or "").strip()
    if u:
        for r in rows:
            if (r.get("url", "") or "").strip() == u:
                return r
    for r in rows:   # fallback: url may be normalized differently across steps
        if slug(r.get("company")) == slug(company) and slug(r.get("title")) == slug(title):
            return r
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--date", help="ISO date the submit was logged (optional; narrows archive match)")
    ap.add_argument("--log", default=DEFAULT_LOG)
    a = ap.parse_args()

    archives = find_archive(a.company, a.title, a.date)
    row = find_log_row(a.url, a.company, a.title, a.log)

    if archives and row is not None:
        print(f"CONFIRMED: {a.company} · {a.title}  "
              f"[log status={row.get('status', '?')}, "
              f"archive={os.path.relpath(archives[0], ROOT)}]")
        sys.exit(0)

    missing = []
    if not archives:
        missing.append("archive folder")
    if row is None:
        missing.append("log row")
    print(f"NOT CONFIRMED: {a.company} · {a.title} — missing {', '.join(missing)} "
          f"-> downgrade to couldnt_confirm", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
