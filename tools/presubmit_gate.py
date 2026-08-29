#!/usr/bin/env python3
"""Pre-submit gate for a tailored resume — runs all three checks and returns a
single GO / REVIEW / BLOCK verdict. Nothing goes out un-gated.

  1. deai_lint  (voice)  — HARD. AI tells in a prose zone -> BLOCK.
  2. claim_trace (truth) — HARD. number drift or never-claim hit -> BLOCK.
  3. ats_check  (fit)    — ADVISORY. missing REQUIRED JD terms -> REVIEW
     (the agent classifies each: 'have it' -> add truthfully, or 'gap' ->
     acknowledge in the cover note. A gap is NEVER faked on the resume.)

Exit codes:  0 = GO,  1 = BLOCK,  2 = REVIEW

Usage:
  python tools/presubmit_gate.py <variant.docx> [keywords.json]

Without keywords.json the truth+voice gates still run; the fit gate is skipped
(reported as 'no JD keywords supplied'). Provide keywords.json — the JD's terms,
same format as ats_check — to gate on keyword fit for a specific posting.
"""
import sys, os, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def run_hard(script, variant):
    """Run a CI-style gate tool; return (passed, first_failure_lines)."""
    p = subprocess.run([sys.executable, os.path.join(HERE, script), variant],
                       capture_output=True, text=True)
    ok = p.returncode == 0
    detail = [l for l in p.stdout.splitlines() if "✗" in l or "⚠" in l]
    return ok, detail


def run_ats(variant, kw_path):
    from ats_check import check
    keywords = json.load(open(kw_path))
    rows = check(variant, keywords)
    req = [r for r in rows if r["priority"] == "required"]
    missing_req = [r["term"] for r in req if r["status"] == "missing"]
    syn_req = [r["term"] for r in req if r["status"] == "synonym-only"]
    cov = sum(1 for r in req if r["status"] == "covered")
    return {"req_total": len(req), "req_covered": cov,
            "missing_required": missing_req, "synonym_required": syn_req,
            "missing_preferred": [r["term"] for r in rows
                                  if r["priority"] == "preferred" and r["status"] == "missing"]}


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    variant = sys.argv[1]
    kw_path = sys.argv[2] if len(sys.argv) > 2 else None
    name = os.path.basename(variant)

    print(f"\n{'='*70}\nPRE-SUBMIT GATE — {name}\n{'='*70}")

    voice_ok, voice_detail = run_hard("deai_lint.py", variant)
    truth_ok, truth_detail = run_hard("claim_trace.py", variant)

    print(f"  1. voice (deai_lint)   {'PASS' if voice_ok else 'FAIL'}")
    for l in voice_detail: print(f"        {l.strip()}")
    print(f"  2. truth (claim_trace) {'PASS' if truth_ok else 'FAIL'}")
    for l in truth_detail: print(f"        {l.strip()}")

    ats = None
    if kw_path:
        ats = run_ats(variant, kw_path)
        print(f"  3. fit (ats_check)     {ats['req_covered']}/{ats['req_total']} required covered verbatim")
        if ats["synonym_required"]:
            print(f"        swap to JD wording (truthful): {', '.join(ats['synonym_required'])}")
        if ats["missing_required"]:
            print(f"        MISSING required (classify have-it vs gap): {', '.join(ats['missing_required'])}")
    else:
        print("  3. fit (ats_check)     SKIPPED — no JD keywords supplied")

    # verdict
    print("-"*70)
    if not (voice_ok and truth_ok):
        verdict, code = "BLOCK", 1
        why = "truth/voice gate failed — fix before it can go out"
    elif ats and ats["missing_required"]:
        verdict, code = "REVIEW", 2
        why = ("required JD terms missing — agent must classify each as 'have it' "
               "(add truthfully) or 'gap' (acknowledge in cover note, never fake)")
    else:
        verdict, code = "GO", 0
        why = ("truth + voice clean" if not kw_path
               else "truth + voice clean, required JD terms covered or truthfully swappable")
    print(f"VERDICT: {verdict}  — {why}")
    print("Note: GO clears the resume. Final submit is always the user's click.")
    sys.exit(code)


if __name__ == "__main__":
    main()
