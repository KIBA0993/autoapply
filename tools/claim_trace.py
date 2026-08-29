#!/usr/bin/env python3
"""Factual-grounding trace for a tailored resume — the mechanical half of the
drafter/reviewer split (borrowed from the ai-job-search project, adapted for
DOCX + candidate_profile.json).

The drafter (agent) tailors a variant. Before it goes out, a SEPARATE reviewer
audits it against the sources of truth instead of the drafter self-checking —
self-checking is exactly what let OAuth cross-contaminate a variant on 2026-07-22.

This tool does the part a machine does better than judgment:
  1. NUMBER DRIFT — every metric in the variant (%, $, x, pt, M/K/B, "N years")
     must appear in MASTER or candidate_profile.json. A number in the variant
     that traces to neither is either fabricated or scaled — the tool cannot tell
     which, so it flags it for the reviewer.
  2. NEVER-CLAIM — a literal scan for every term on profile.never_claim. Zero
     tolerance: one hit fails the whole audit.

What it does NOT do — that is the reviewer agent's job:
  - decide whether a *rephrased* bullet still traces to a real experience
  - judge whether an added skill is genuinely owned
  - hunt JD requirements the candidate can truthfully support but didn't surface

Usage:
  python tools/claim_trace.py <variant.docx> [master.docx] [candidate_profile.json]

Defaults resolve MASTER and the profile from the standard locations if omitted.
Exit code 1 if any never-claim hit or untraceable metric is found (CI-friendly).
"""
import sys, os, re, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ats_check import resume_text  # same docx text-layer extraction the ATS check uses

HOME = os.path.expanduser("~")
DEFAULT_MASTER = f"{HOME}/Documents/Resume/Candidate_Resume_MASTER.docx"
DEFAULT_PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "profile", "candidate_profile.json")

# A metric = digits with a unit that makes it a claim (%, $, x, pt, M/K/B, "years"),
# or a 4+ digit number (160000, 2024). Bare small integers (2 weeks, 3 systems, II)
# are listed but not flagged — low fabrication risk and too noisy to gate on.
_NUM = r"\$?\+?\d[\d,]*(?:\.\d+)?"
STRONG_UNIT = re.compile(
    rf"(?P<n>{_NUM})\s?(?P<u>%|percent|pts?\b|x\b|M\b|K\b|B\b|bn\b|million|billion)", re.I)
YEARS = re.compile(rf"(?P<n>\d+)\+?\s?(?:years?|yrs?)", re.I)
BIGINT = re.compile(r"(?<!\d)(\d{4,})(?!\d)")


def canon(num, unit=""):
    """('$100', 'M') -> '100m'; ('50', '%') -> '50%'; ('9+', '') -> '9'."""
    digits = re.sub(r"[^\d.]", "", num)
    digits = digits.rstrip(".")
    u = (unit or "").lower().strip()
    u = {"percent": "%", "pts": "pt", "bn": "b", "million": "m", "billion": "b"}.get(u, u)
    if u.endswith("s"):
        u = u[:-1]
    return digits + u


def metrics(text):
    """Return {canonical: context} for every strong metric mention in the text."""
    out = {}
    for m in STRONG_UNIT.finditer(text):
        c = canon(m.group("n"), m.group("u"))
        out.setdefault(c, _ctx(text, m.start()))
    for m in YEARS.finditer(text):
        c = canon(m.group("n"))  # bare year-count, e.g. '9'
        out.setdefault(c + "yr", _ctx(text, m.start()))
    for m in BIGINT.finditer(text):
        c = canon(m.group(1))
        out.setdefault(c, _ctx(text, m.start()))
    return out


def _ctx(text, i, span=44):
    a = max(0, i - span // 2)
    return re.sub(r"\s+", " ", text[a:a + span]).strip()


def numbers_in(text):
    """All canonical numbers present anywhere in a source (for traceability set).
    Deliberately loose — includes bare integers — so a metric is 'traced' if its
    digits appear anywhere in MASTER or the profile, even phrased differently."""
    s = set()
    for m in STRONG_UNIT.finditer(text):
        s.add(canon(m.group("n"), m.group("u")))
    for m in YEARS.finditer(text):
        s.add(canon(m.group("n")) + "yr")
        s.add(canon(m.group("n")))
    for m in re.finditer(_NUM, text):
        s.add(canon(m.group(0)))
    return s


def traced(metric_canon, source_nums):
    """A metric traces if its exact canonical, or its bare digit-core, is in source."""
    if metric_canon in source_nums:
        return True
    core = re.sub(r"[^\d.]", "", metric_canon).rstrip(".")
    return core in source_nums


def load_never_claim(profile_path):
    try:
        data = json.load(open(profile_path))
    except Exception:
        return []
    nc = data.get("never_claim", {})
    return [k for k in nc if not k.startswith("_")]


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        sys.exit(2)
    variant = args[0]
    master = args[1] if len(args) > 1 else DEFAULT_MASTER
    profile = args[2] if len(args) > 2 else DEFAULT_PROFILE

    vtext = resume_text(variant)
    mtext = resume_text(master) if os.path.exists(master) else ""
    ptext = open(profile).read() if os.path.exists(profile) else ""
    source_nums = numbers_in(mtext) | numbers_in(ptext)

    print(f"\nFactual trace — {os.path.basename(variant)}")
    print(f"  against MASTER: {os.path.basename(master)}"
          + ("" if mtext else "  (NOT FOUND — number drift check skipped)"))
    print("=" * 78)

    fail = False

    # 1. never-claim — zero tolerance
    never = load_never_claim(profile)
    vlow = vtext.lower()
    hits = [t for t in never if re.search(r"(?<!\w)" + re.escape(t.lower()) + r"(?!\w)", vlow)]
    print("\nNEVER-CLAIM SCAN")
    if hits:
        fail = True
        for t in hits:
            print(f"  ✗ FAIL  '{t}' appears in the variant — remove before sending")
    else:
        print(f"  ✓ clean  ({len(never)} terms checked: {', '.join(never) or 'none'})")

    # 2. number drift
    print("\nNUMBER DRIFT  (metric in variant not traceable to MASTER/profile)")
    if not mtext:
        print("  – skipped, MASTER not found")
    else:
        vm = metrics(vtext)
        untraced = {c: ctx for c, ctx in vm.items() if not traced(c, source_nums)}
        if untraced:
            fail = True
            for c, ctx in sorted(untraced.items()):
                print(f"  ⚠ {c:>8}  …{ctx}…")
            print("\n  Reviewer: for each, either it traces to MASTER phrased differently")
            print("  (fine) or it was invented/scaled (remove). The tool can't tell which.")
        else:
            print(f"  ✓ all {len(vm)} metrics trace to MASTER or the profile")

    print("\n" + "=" * 78)
    print("Mechanical pass done. Hand the variant + JD to the reviewer agent for the")
    print("judgment half: does every rephrased bullet still trace, and what JD")
    print("requirement could be surfaced truthfully but wasn't? See playbooks/factual-audit.md")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
