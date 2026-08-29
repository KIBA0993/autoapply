#!/usr/bin/env python3
"""Fuzzy dedup + saturation + staleness check — keeps the big CSVs OUT of context.

Replaces "load job_pool.csv / applied_history.csv into the model" with one script
that prints ONLY the hits. Implements the fuzzy rules the skill mandates (a plain
grep cannot): prefix match and normalized seniority+family match. This is the check
that exact-match missed on Affirm 'Credit & Pricing' (Phase 2.5).

Usage:
  python tools/dedupe_check.py "Company" "Job Title"
  python tools/dedupe_check.py "Affirm" "Senior Product Manager, Credit & Pricing"

Output is advisory — it SURFACES, it does not decide. Exit codes let a caller branch:
  0  NEW      — no company history, not saturated
  2  SURFACE  — probable dup / seen-before / HEAVY saturation → human decides
  1  BLOCK    — exact/prefix duplicate OR SATURATED → skip unless the user overrides

The model reads the printed lines; it should never need to load the CSVs themselves.
"""
import sys, os, csv, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.join(HERE, "..", "dashboard")
HISTORY = os.path.join(DASH, "applied_history.csv")
SATURATION = os.path.join(DASH, "company_saturation.csv")
APPLOG = os.path.join(DASH, "application_log.csv")   # this tool's own submits (log_application.py)

STALE_DAYS = 14   # history is a point-in-time Simplify export; warn if older than this
SATURATED = 10    # >= this many prior apps → saturated
HEAVY = 5         # >= this → surface the count
# User turned the saturation SKIP off 2026-08-05. While False, saturation never BLOCKs —
# it only surfaces the count as info. The exact/prefix DUPLICATE guard is unaffected.
# Flip back to True to re-enable "SATURATED → skip".
SATURATION_BLOCKS = False

_SENIORITY = {
    "sr": "senior", "snr": "senior", "sr.": "senior",
    "jr": "junior", "jr.": "junior",
    "princ": "principal", "principal": "principal",
    "staff": "staff", "lead": "lead", "senior": "senior", "junior": "junior",
    "director": "director", "head": "head", "vp": "vp",
}
_FAMILY = {  # collapse product-management vocabulary to one token
    "pm": "productmanager", "product manager": "productmanager",
    "product management": "productmanager", "product owner": "productmanager",
    "gpm": "productmanager", "tpm": "technicalproductmanager",
}


def norm_company(s):
    s = (s or "").lower()
    s = re.sub(r"[.,/&']", " ", s)
    s = re.sub(r"\b(inc|llc|ltd|corp|co|the)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_title(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for k, v in _FAMILY.items():  # multi-word family phrases first
        s = re.sub(rf"\b{k}\b", v, s)
    toks = [_SENIORITY.get(t, t) for t in s.split()]
    return toks


def seniority_of(toks):
    return {t for t in toks if t in set(_SENIORITY.values())}


def is_prefix(a, b):
    """True if token list a is a prefix of b (or vice versa)."""
    if not a or not b:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return long[: len(short)] == short


def load_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_applog(path=APPLOG):
    """This tool's own submitted applications, mapped to the history row shape
    (company / job_title / applied_date). Counts toward dedup so we catch repeats
    of what WE sent since the last Simplify export — but NOT toward the export's
    staleness check (that stays about applied_history.csv only). Skips blank/legacy
    rows and anything not actually submitted."""
    out = []
    for r in load_rows(path):
        co = (r.get("company") or "").strip()
        if not co:
            continue
        status = (r.get("status") or "").strip().lower()
        if status and "submit" not in status and "confirm" not in status:
            continue   # parked/other non-submission log rows don't count as prior apps
        out.append({
            "company": co,
            "job_title": (r.get("title") or "").strip(),
            "applied_date": (r.get("date") or "").strip(),
        })
    return out


def parse_date(s):
    try:
        return datetime.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def check_one(company, title, history, saturation):
    """Per-pair check. Returns (verdict, lines) WITHOUT the global staleness line."""
    nc, nt = norm_company(company), norm_title(title)
    same_co = [r for r in history if norm_company(r.get("company")) == nc]
    verdict, lines = 0, []

    # --- title-level dedup against this company's history ---
    exact_or_prefix, probable = [], []
    for r in same_co:
        rt = norm_title(r.get("job_title"))
        if rt == nt or is_prefix(nt, rt):
            exact_or_prefix.append(r)
        elif seniority_of(rt) == seniority_of(nt) and (
            "productmanager" in rt) == ("productmanager" in nt):
            probable.append(r)

    if exact_or_prefix:
        verdict = 1
        for r in sorted(exact_or_prefix, key=lambda r: r.get("applied_date", ""), reverse=True)[:3]:
            lines.append(f"DUP: {r['company']} — {r['job_title']} ({r.get('applied_date','?')})")
    elif probable:
        verdict = max(verdict, 2)
        for r in sorted(probable, key=lambda r: r.get("applied_date", ""), reverse=True)[:3]:
            lines.append(f"PROBABLE: {r['company']} — {r['job_title']} ({r.get('applied_date','?')})")
    elif same_co:
        verdict = max(verdict, 2)
        dates = sorted([d for d in (r.get("applied_date") for r in same_co) if d])
        lines.append(f"SEEN: {company} — {len(same_co)} prior app(s), "
                     f"{dates[0] if dates else '?'}..{dates[-1] if dates else '?'}, "
                     f"none title-matching")

    # --- saturation ---
    for r in saturation:
        if norm_company(r.get("company")) == nc:
            n = int(re.sub(r"\D", "", r.get("applications", "0")) or 0)
            if n >= SATURATED:
                if SATURATION_BLOCKS:
                    verdict = 1
                    lines.append(f"SATURATED: {company} ({n} apps) — skip unless user overrides")
                else:
                    if verdict != 1:      # never downgrade a duplicate BLOCK to surface
                        verdict = 2
                    lines.append(f"SATURATED: {company} ({n} apps) — threshold OFF, surfacing only")
            elif n >= HEAVY:
                if verdict != 1:          # never downgrade a duplicate BLOCK to surface
                    verdict = 2
                lines.append(f"HEAVY: {company} ({n} apps) — surface, let user decide")
            break

    return verdict, lines


def staleness_line(history):
    all_dates = [d for d in (parse_date(r.get("applied_date")) for r in history) if d]
    if not all_dates:
        return None
    newest = max(all_dates)
    age = (datetime.date.today() - newest).days
    if age > STALE_DAYS:
        return (f"STALE: newest applied_date is {newest} ({age}d old) — "
                f"history may be behind; trust the Simplify banner over this CSV")
    return None


# severity order: BLOCK(1) > SURFACE(2) > NEW(0)
_SEV = {0: 0, 2: 1, 1: 2}
def worst_of(a, b):
    return a if _SEV[a] >= _SEV[b] else b


def main():
    args = sys.argv[1:]
    history = load_rows(HISTORY)
    stale = staleness_line(history)          # staleness of the Simplify export only
    history = history + load_applog()        # our own submits also count toward dedup
    saturation = load_rows(SATURATION)

    # --- batch mode: read "Company\tTitle" (or "Company|Title") pairs from stdin ---
    # One process for N candidates instead of N round-trips. Exit = the WORST verdict.
    if args and args[0] == "--batch":
        pairs = []
        for raw in sys.stdin:
            raw = raw.rstrip("\n")
            if not raw.strip():
                continue
            parts = re.split(r"\t|\s*\|\s*", raw, maxsplit=1)
            if len(parts) < 2:
                print(f"SKIP (unparseable): {raw}", file=sys.stderr)
                continue
            pairs.append((parts[0].strip(), parts[1].strip()))
        worst = 0
        for company, title in pairs:
            verdict, lines = check_one(company, title, history, saturation)
            print(f"=== {company} — {title} ===")
            if lines:
                print("\n".join(lines))
            else:
                print(f"NEW: {company} — {title}  (no prior history, not saturated)")
            print()
            worst = worst_of(worst, verdict)
        if stale:
            print(stale)
        sys.exit(worst)

    # --- single-pair mode (back-compat: identical output + exit code) ---
    if len(args) < 2:
        print("usage: dedupe_check.py \"Company\" \"Job Title\"", file=sys.stderr)
        print("       dedupe_check.py --batch   < pairs.tsv   (Company<TAB>Title per line)", file=sys.stderr)
        sys.exit(64)
    company, title = args[0], args[1]
    verdict, lines = check_one(company, title, history, saturation)
    if stale:
        lines.append(stale)
    if not lines:
        print(f"NEW: {company} — {title}  (no prior history, not saturated)")
    else:
        print("\n".join(lines))
    sys.exit(verdict)


if __name__ == "__main__":
    main()
