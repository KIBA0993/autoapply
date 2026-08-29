#!/usr/bin/env python3
"""Classify postings by who submits — the skill (auto) or you (manual hand-off).

The one question this answers up front: of these postings, which can the skill fill AND
submit unattended (Mode B), and which need your manual submit because they gate behind an
account/login or hand the submit back? The signal is the ATS alone — already recorded on
every row — so no browser, no fetch.

Buckets:
  auto        — skill fills AND submits: greenhouse, lever, ashby, workable (no account),
                PLUS any ATS you've verified (see provisional).
  provisional — no account, but the skill has no *proven* end-to-end submit yet:
                smartrecruiters, recruitee, breezy. In Mode B these run a ONE-TIME VERIFY
                (fill + gate, you confirm the first submit); on a confirmed success the ATS
                is recorded verified and is treated as `auto` from then on. Promote with
                `--mark-verified <ats>` (also done automatically by the Mode B verify path).
  manual      — YOU submit: account/tenant login (workday, icims, taleo, oracle, custom).
  discovery   — don't apply direct (aggregators, LinkedIn Easy Apply); route to the real board.

The verified set persists in sources/verified_ats.json (gitignored — local state).

Usage:
  python tools/apply_class.py greenhouse workday smartrecruiters   # classify ATS names
  python tools/apply_class.py --pool dashboard/job_pool.csv --status Ready            # split summary
  python tools/apply_class.py --pool dashboard/job_pool.csv --status Ready --only auto --top 10
  python tools/apply_class.py --mark-verified smartrecruiters      # promote after a verified submit
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERIFIED_FILE = os.path.join(ROOT, "sources", "verified_ats.json")

# no account, but no proven end-to-end submit yet — graduate to auto after one verified submit
PROVISIONAL = {"smartrecruiters", "recruitee", "breezy", "bamboohr"}

# ats -> (bucket, submits_bool, reason)   [provisional + verified handled in classify()]
CLASS = {
    "greenhouse":     ("auto", True,  "no account, on-page submit — skill fills + submits"),
    "lever":          ("auto", True,  "no account, on-page submit — skill fills + submits"),
    "ashby":          ("auto", True,  "no account, on-page submit — skill fills + submits"),
    "workable":       ("auto", True,  "no account, on-page submit — skill fills + submits"),
    "workday":        ("manual", False, "account per tenant — you create it and submit"),
    "icims":          ("manual", False, "account/login — you submit"),
    "taleo":          ("manual", False, "account/login — you submit"),
    "oracle":         ("manual", False, "account/login — you submit"),
    "custom_browser": ("manual", False, "custom/embedded flow — you submit"),
    "custom":         ("manual", False, "custom/embedded flow — you submit"),
    "linkedin":       ("discovery", False, "Easy Apply — discovery only; apply on the real board"),
    "remoteok":       ("discovery", False, "aggregator — route to the direct ATS"),
    "remotive":       ("discovery", False, "aggregator — route to the direct ATS"),
    "arbeitnow":      ("discovery", False, "aggregator — route to the direct ATS"),
    "himalayas":      ("discovery", False, "aggregator — route to the direct ATS"),
    "jobicy":         ("discovery", False, "aggregator — route to the direct ATS"),
}

LABEL = {
    "auto":        "SKILL SUBMITS",
    "provisional": "VERIFY ONCE → then auto",
    "manual":      "YOU SUBMIT",
    "discovery":   "DISCOVERY (don't apply direct)",
}
BUCKETS = ("auto", "provisional", "manual", "discovery")


def load_verified():
    try:
        return {str(x).strip().lower() for x in json.load(open(VERIFIED_FILE))}
    except Exception:
        return set()


def mark_verified(ats):
    ats = ats.strip().lower()
    v = load_verified()
    if ats in v:
        return False
    v.add(ats)
    os.makedirs(os.path.dirname(VERIFIED_FILE), exist_ok=True)
    tmp = VERIFIED_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(sorted(v), f, indent=0)
    os.replace(tmp, VERIFIED_FILE)
    return True


def classify(ats, verified=None):
    a = (ats or "").strip().lower()
    if verified is None:
        verified = load_verified()
    if a in verified:
        return ("auto", True, "verified — promoted to auto")
    if a in PROVISIONAL:
        return ("provisional", False, "no account, but no proven submit yet — first is a one-time verify, then auto")
    return CLASS.get(a, ("manual", False, "unknown ATS — treat as hand-off until verified"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ats", nargs="*", help="ATS name(s) to classify")
    ap.add_argument("--pool", help="job_pool.csv to summarize (uses its `ats` column)")
    ap.add_argument("--status", help="only rows whose status contains this (case-insensitive)")
    ap.add_argument("--only", choices=BUCKETS,
                    help="keep only this class — e.g. --only auto for a Mode B set, --only manual for your to-do list")
    ap.add_argument("--top", type=int, help="with --only, take the first N rows (pool must already be in rank order)")
    ap.add_argument("--list", action="store_true", help="with --pool, list each row (company · title · url)")
    ap.add_argument("--mark-verified", metavar="ATS",
                    help="record ATS as verified so it classifies as auto from now on")
    a = ap.parse_args()

    if a.mark_verified:
        changed = mark_verified(a.mark_verified)
        print(f"{a.mark_verified.lower()}: {'now verified → auto' if changed else 'already verified'}. "
              f"Verified set: {', '.join(sorted(load_verified())) or '(none)'}")
        return

    if not a.pool and not a.ats:
        ap.error("give ATS name(s), --pool FILE, or --mark-verified ATS")

    verified = load_verified()

    if a.ats:
        for x in a.ats:
            bucket, _submits, reason = classify(x, verified)
            print(f"{x:<16} {LABEL[bucket]:<24} {reason}")
        return

    counts = {b: 0 for b in BUCKETS}
    rows = []
    with open(a.pool, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if a.status and a.status.lower() not in (r.get("status", "").lower()):
                continue
            bucket, _s, _reason = classify(r.get("ats", ""), verified)
            counts[bucket] += 1
            rows.append((bucket, r.get("company", ""), r.get("job_title", ""),
                         r.get("ats", ""), r.get("job_url", "")))

    if a.only:
        picked = [r for r in rows if r[0] == a.only]
        if a.top:
            picked = picked[:a.top]
        head = "top " + str(a.top) if a.top else "all"
        print(f"{LABEL[a.only]} — {head} ({len(picked)} shown, {counts[a.only]} in scope):")
        for _b, company, title, ats, url in picked:
            print(f"  {company} · {title}  [{ats}]  {url}")
        return

    total = sum(counts.values())
    scope = f" (status~='{a.status}')" if a.status else ""
    print(f"{total} postings{scope}:  {counts['auto']} SKILL SUBMITS · "
          f"{counts['provisional']} VERIFY-ONCE · {counts['manual']} YOU SUBMIT · "
          f"{counts['discovery']} discovery")
    if a.list:
        for bucket in BUCKETS:
            for _b, company, title, ats, url in [r for r in rows if r[0] == bucket]:
                print(f"  {LABEL[bucket]:<24} {company} · {title}  [{ats}]  {url}")


if __name__ == "__main__":
    main()
