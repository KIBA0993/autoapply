#!/usr/bin/env python3
"""Record a posting the user declined (or a hard-gate they won't pass), so it never
re-enters a Mode B top-X and never burns another worker dispatch.

Appends to dashboard/declined_postings.csv (gitignored via dashboard/*.csv).
`freeze_authorized.py` excludes any url here from the frozen set — a declined posting
does not take a top-X slot on the next run.

  python tools/decline.py --url https://job-boards.greenhouse.io/airwallex/jobs/123 \
    --company Airwallex --title "Sr PM AI Risk & Fraud" --reason "AI-policy hard-gate, user declined"
"""
import argparse
import csv
import datetime
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FILE = os.path.join(ROOT, "dashboard", "declined_postings.csv")
COLUMNS = ["date", "url", "company", "title", "reason"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="the exact posting URL to never re-surface")
    ap.add_argument("--company", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--date", help="ISO date (default: today, UTC)")
    a = ap.parse_args()

    date = a.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    url = a.url.strip().rstrip("/")

    rows = []
    if os.path.exists(FILE):
        with open(FILE, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    if any((r.get("url") or "").strip().rstrip("/") == url for r in rows):
        print(f"already declined: {url}")
        return

    rows.append({"date": date, "url": url, "company": a.company, "title": a.title, "reason": a.reason})
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    os.replace(tmp, FILE)
    print(f"declined recorded: {a.company} · {a.title}  [{url}]")


if __name__ == "__main__":
    main()
