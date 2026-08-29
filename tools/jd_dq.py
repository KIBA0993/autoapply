#!/usr/bin/env python3
"""Mechanical pre-dispatch disqualifiers — cheap, deterministic row filters run BEFORE a
browser worker is ever spawned. A dropped row is fail-safe: the freeze buffer just backfills
the slot, so a false drop costs at most one lost candidate, never a wrong submit.

Today this covers LOCATION only (the one hard, mechanical DQ in profile/application_rules.md:
"Hybrid or onsite outside your home metro or approved target metros — hard skip"). It is deliberately
conservative — it only drops a row when it can POSITIVELY identify a US location outside the
allowed set; anything remote, blank, or unrecognized is KEPT for the worker to judge from the
posting body (region-locked "remote" is a body-text call the header can't settle).

Comp is intentionally NOT handled here: application_rules.md sets no hard comp floor (ambiguous
comp routes to Consider/review, not skip) and job_pool.csv carries no comp column. If a comp
floor is ever defined + a comp column added at screen time, add it here as a second DQ.
"""
import re

# Allowed location tokens (lowercased, word-ish). Remote is handled separately.
_ALLOWED = [
    "atlanta", "georgia", "seattle", "new york", "nyc", "manhattan", "brooklyn",
    "california", "san francisco", "bay area", "los angeles", "san jose", "san diego",
    "oakland", "palo alto", "mountain view", "sunnyvale", "santa clara", "cupertino",
    "san mateo", "menlo park", "redwood city", "irvine", "sacramento", "berkeley",
]
_ALLOWED_STATES = {"ga", "ca", "wa", "ny"}   # 2-letter codes for the allowed metros/states

# A "City, ST" tail, e.g. "Austin, TX" or "Boston, MA (Onsite)".
_CITY_STATE = re.compile(r",\s*([A-Za-z]{2})\b")
_US_STATES = {
    "al", "ak", "az", "ar", "co", "ct", "de", "fl", "hi", "id", "il", "in", "ia",
    "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv",
    "nh", "nj", "nm", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn",
    "tx", "ut", "vt", "va", "wv", "wi", "wy", "dc",
} | _ALLOWED_STATES


def location_ok(location, remote_policy=""):
    """True = keep (eligible or undetermined); False = drop (clearly ineligible onsite)."""
    loc = (location or "").strip().lower()
    rp = (remote_policy or "").strip().lower()
    if not loc:
        return True                                   # unknown → keep, let the worker see it
    if "remote" in loc or "remote" in rp or "anywhere" in loc:
        return True                                   # remote → keep (region-lock is a body call)
    if any(tok in loc for tok in _ALLOWED):
        return True                                   # names an allowed metro/state → keep
    # Positively identify an out-of-area US state code in a "City, ST" string → drop.
    m = _CITY_STATE.search(location or "")
    if m:
        st = m.group(1).lower()
        if st in _US_STATES and st not in _ALLOWED_STATES:
            return False                              # e.g. "Austin, TX" onsite → drop
    return True                                       # unrecognized format → keep (fail-safe)


def dq_reason(location, remote_policy=""):
    """Return a short reason if the row is disqualified, else None."""
    if not location_ok(location, remote_policy):
        return "location-ineligible:{0}".format((location or "").strip()[:40])
    return None


if __name__ == "__main__":
    # tiny self-test / CLI: echo rows that would be dropped
    import sys
    cases = [
        ("Remote, US", "", True),
        ("your home metro, GA", "", True),
        ("San Francisco, CA (Hybrid)", "", True),
        ("New York, NY", "", True),
        ("Seattle, WA", "", True),
        ("Austin, TX", "", False),
        ("Boston, MA (Onsite)", "", False),
        ("Chicago, IL", "", False),
        ("", "", True),
        ("Remote", "US-remote", True),
        ("London, UK", "", True),          # non-US 2-letter not a US state → keep (worker judges)
    ]
    bad = 0
    for loc, rp, want in cases:
        got = location_ok(loc, rp)
        ok = "ok " if got == want else "FAIL"
        if got != want:
            bad += 1
        print("{0}  keep={1!s:<5} want={2!s:<5}  {3!r}".format(ok, got, want, loc))
    sys.exit(1 if bad else 0)
