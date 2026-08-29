#!/usr/bin/env python3
"""Fail-closed profile field lookup — pull only the fields a form needs, instead of
loading all of candidate_profile.json (~3.7k tokens) into context.

Usage:
  python tools/profile_get.py candidate.legal_name work_authorization.us_authorized
  python tools/profile_get.py compensation.target_base

Dotted paths index into nested objects; a numeric segment indexes a list.

Batch in ONE call — pass every field you need at once (a worker should resolve all standing
facts in a single invocation, never one call per field):
  python tools/profile_get.py --common                 # the standard set every form needs
  python tools/profile_get.py --common current_status.notice_period   # standard set + extras

Fail-closed by design (enforces the skill's "TBD/absent → ASK, never guess" rule):
  - Found, concrete value        → prints  "<path> = <value>"
  - Missing / null / "TBD" / in   → prints  "ASK: <path> — not in profile, do not guess"
    the never_guess list                     and exits non-zero
Exit code is non-zero if ANY requested path must be asked, so a caller can stop.
"""
import sys, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "..", "profile", "candidate_profile.json")

PLACEHOLDERS = {"", "tbd", "todo", "n/a", "na", "unknown", "?"}

# The fields nearly every application form asks for — resolved in one call via --common so a
# worker gets all standing identity/auth/logistics facts in a single round-trip.
COMMON = [
    "candidate.legal_name", "candidate.preferred_name", "candidate.email", "candidate.phone",
    "candidate.linkedin_url", "candidate.github_url",
    "candidate.street_address", "candidate.city", "candidate.state", "candidate.zip_code",
    "candidate.country", "pronouns",
    "work_authorization.current_authorization",
    "work_authorization.requires_sponsorship_now",
    "work_authorization.requires_sponsorship_in_future",
    "current_status.available_start_date", "current_status.notice_period",
]


def resolve(obj, path):
    cur = obj
    for seg in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(seg)]
            except (ValueError, IndexError):
                return (False, None)
        elif isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return (False, None)
    return (True, cur)


def is_placeholder(v):
    if v is None:
        return True
    if isinstance(v, str) and v.strip().lower() in PLACEHOLDERS:
        return True
    return False


def main():
    args = sys.argv[1:]
    paths = []
    if "--common" in args:
        paths.extend(COMMON)
        args = [a for a in args if a != "--common"]
    paths.extend(args)
    if not paths:
        print("usage: profile_get.py [--common] <dotted.path> [more.paths ...]", file=sys.stderr)
        sys.exit(64)
    with open(PROFILE, encoding="utf-8") as f:
        data = json.load(f)
    never_guess = {str(x).lower() for x in data.get("never_guess", [])}

    must_ask = False
    for path in paths:
        found, val = resolve(data, path)
        leaf = path.split(".")[-1]
        if not found or is_placeholder(val) or leaf.lower() in never_guess:
            print(f"ASK: {path} — not in profile, do not guess")
            must_ask = True
        else:
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)
            print(f"{path} = {val}")
    sys.exit(1 if must_ask else 0)


if __name__ == "__main__":
    main()
