#!/usr/bin/env python3
"""Record a submitted application AND archive what was sent, for interview prep.

Phase 4's durable record. Two things every submit should leave behind so that weeks
later — when a recruiter calls — you can see exactly what you applied to and with what:

  1. A row in dashboard/application_log.csv (opens in Excel):
     date, company, title, url, ats, resume_variant, resume_file, jd_path, status, notes
  2. An archive folder dashboard/applications/<date>_<company>_<title>/ holding:
       - a COPY of the exact résumé file that was sent (resume<ext>) — the routed
         variant can change later, so snapshot it at submit time, don't just name it
       - jd.md — the full job description text (so you prep against what you actually applied to)

Both writes are atomic (temp + os.replace) so an interrupted run can't corrupt the log.
The log's columns are migrated forward automatically if an older 8-column log exists.

  python tools/log_application.py \
    --company "Novacredit" --title "Senior PM, Credit" \
    --url https://job-boards.greenhouse.io/novacredit/jobs/123 --ats greenhouse \
    --variant payments_infra --resume resumes/payments_infra.docx \
    --jd-file /tmp/nova_jd.txt --notes "comp: deferred; consent: standing-yes"

--jd-file may be omitted (records the row, notes JD not archived). --status defaults
to Submitted. Prints the archive folder path.
"""
import argparse
import csv
import datetime
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_LOG = os.path.join(ROOT, "dashboard", "application_log.csv")
DEFAULT_ARCHIVE = os.path.join(ROOT, "dashboard", "applications")

COLUMNS = ["date", "company", "title", "url", "ats",
           "resume_variant", "resume_file", "jd_path", "status", "notes"]


def slug(s, n=40):
    s = re.sub(r"[^\w\s-]", "", (s or "").strip().lower())
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:n] or "unknown"


def atomic_write(path, write_fn):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        write_fn(f)
    os.replace(tmp, path)


def append_row(log_path, row):
    """Append one row, migrating an older/short header forward. Rewrites the whole
    file through a DictReader/DictWriter so the result is always well-formed CSV."""
    rows = []
    if os.path.exists(log_path):
        with open(log_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    rows.append(row)

    def _w(f):
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})

    atomic_write(log_path, _w)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--ats", default="")
    ap.add_argument("--variant", default="", help="résumé variant name (from resume_routing.md)")
    ap.add_argument("--resume", help="path to the exact résumé file that was sent (gets copied)")
    ap.add_argument("--jd-file", help="path to a text/markdown file with the full JD (gets copied)")
    ap.add_argument("--notes", default="", help="non-obvious answers given (comp, consents, etc.)")
    ap.add_argument("--status", default="Submitted")
    ap.add_argument("--date", help="ISO date override (default: today, UTC)")
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--archive-dir", default=DEFAULT_ARCHIVE)
    a = ap.parse_args()

    date = a.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    folder = f"{date}_{slug(a.company)}_{slug(a.title)}"
    archive = os.path.join(a.archive_dir, folder)
    os.makedirs(archive, exist_ok=True)

    resume_dest = ""
    if a.resume:
        if not os.path.exists(a.resume):
            print(f"resume not found: {a.resume}", file=sys.stderr)
            sys.exit(66)
        ext = os.path.splitext(a.resume)[1] or ".docx"
        resume_dest = os.path.join(archive, "resume" + ext)
        shutil.copy2(a.resume, resume_dest)

    jd_dest = ""
    if a.jd_file:
        if not os.path.exists(a.jd_file):
            print(f"jd-file not found: {a.jd_file}", file=sys.stderr)
            sys.exit(66)
        jd_dest = os.path.join(archive, "jd.md")
        shutil.copy2(a.jd_file, jd_dest)

    notes = a.notes
    if not jd_dest:
        notes = (notes + " | JD not archived" if notes else "JD not archived")

    append_row(a.log, {
        "date": date, "company": a.company, "title": a.title, "url": a.url,
        "ats": a.ats, "resume_variant": a.variant,
        "resume_file": os.path.relpath(resume_dest, ROOT) if resume_dest else "",
        "jd_path": os.path.relpath(jd_dest, ROOT) if jd_dest else "",
        "status": a.status, "notes": notes,
    })

    print(f"logged: {a.company} · {a.title}  ->  {os.path.relpath(archive, ROOT)}")


if __name__ == "__main__":
    main()
