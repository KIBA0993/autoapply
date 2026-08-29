# Factual-grounding audit — the drafter/reviewer split

Borrowed from the ai-job-search project (MadsLorentzen), adapted for DOCX +
`candidate_profile.json`. The second of the two ideas worth taking from it; the
first is `ats-keyword-check.md`.

**Why it exists:** the truthfulness gate used to be the *drafter* checking its own
work. That failed. On 2026-07-22, OAuth cross-contaminated a variant — the same
agent that wrote the line was the one asked to catch it, and didn't. A claim you
just wrote reads as true to you. So the audit is done by a **separate reviewer**
that never saw the drafting, with the sources of truth in hand and one job: refute.

This is the check that most directly protects the final round. The losses have been
to "closer experience" — which means the résumé is already being read closely by
the end. A single unsupported line that collapses under one follow-up question is
the exact failure mode, and it is cheaper to catch here than in the room.

## The split of labor

| Step | Who | What |
|---|---|---|
| Draft | **drafter** (main agent) | Tailor the variant per `tailoring.md`. Route, rephrase to the JD's vocabulary, add only have-it terms. |
| Mechanical trace | **tool** | `tools/claim_trace.py` — number drift + never-claim literal scan. Precise, no judgment. |
| Judgment audit | **reviewer** (separate agent) | Read the variant against MASTER + profile + JD. Refute every claim; hunt unsurfaced truthful gains. |
| Verdict | **reviewer** | `SEND` / `FIX-THEN-SEND` (with the exact lines) / `DO-NOT-SEND`. |

The independence is the point. Do **not** collapse the reviewer back into the
drafter to save a step — that rebuilds the exact hole this closes.

## Step 1 — Mechanical trace

If the pre-submit gate has already run (SKILL.md §3c-gate), its truth-gate output **is** this trace — feed that to the reviewer and skip the standalone call. Run it directly only if you're auditing before a gate run:

```bash
python tools/claim_trace.py ~/Documents/Resume/{variant}.docx
```

Defaults resolve MASTER and `profile/candidate_profile.json`. It checks two things
a machine does better than judgment, and exits non-zero if either fails:

1. **Number drift** — every metric in the variant (`%`, `$`, `x`, `pt`, `M/K/B`,
   `N years`, any 4+ digit number) must have its digit-core present in MASTER or the
   profile. A metric that traces to neither is invented or scaled — the tool flags
   it; it cannot tell which, so the reviewer decides.
2. **Never-claim** — a literal scan for every term in `profile.never_claim`
   (OAuth, legal_tech_platform). One hit fails the whole audit. No judgment call.

Verified to catch both: an injected `73%` (absent from MASTER) flagged as drift, an
injected `OAuth` failed the never-claim scan, exit 1. A run that only ever passes is
worthless — this one bites.

## Step 2 — Reviewer agent (the judgment half)

Spawn a **separate** agent (the `Agent` tool). It is not the drafter. Give it:

- the tailored variant's text (read `word/document.xml` from the `.docx` zip)
- MASTER's text and `candidate_profile.json` (the sources of truth)
- the JD body (from the ATS API)
- the `claim_trace.py` output

Charge it with exactly this, adversarial by default:

1. **Refute every substantive claim.** For each bullet/summary line, find the
   supporting fact in MASTER or the profile. No support → flag it. A *rephrased*
   bullet is fine only if the underlying fact is unchanged; a rephrase that drifts
   the meaning is a flag. Default to "flag" when unsure — the drafter can defend it.
2. **Catch what the tool can't.** Added skills or domains not owned; a title read as
   more senior than held; an adjacent experience stretched to sound like the JD's.
3. **Hunt unsurfaced gains (positioning).** Name every JD requirement the candidate
   *can* support from MASTER but the variant didn't surface. This is upside, not a
   defect — it is how a real history is made to read as the closer experience.
4. **Verdict:** `SEND` · `FIX-THEN-SEND` (list the exact lines and the fix) ·
   `DO-NOT-SEND` (a claim can't be grounded and can't be cut without gutting the fit).

## The rule that makes this safe

The reviewer **removes and reorders; it never invents to close a gap.** A JD
requirement the candidate genuinely lacks stays off the résumé — acknowledged in the
cover answer's framing if anywhere. The audit's power is subtractive: it is trusted
*because* its bias is toward cutting, not adding. An audit that adds claims is just a
second drafter, and inherits the same blind spot this exists to remove.

## When to run it

Every time a variant is tailored or refreshed before it goes out on a High-fit,
tier 1–2 application — right after the ATS keyword check, before the form fill.
Skip it only when the routed variant is sent unmodified (no tailoring → nothing new
to ground; the standing variants already passed this when they were built).
