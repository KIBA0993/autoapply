# ATS keyword-coverage check

Borrowed from the ai-job-search project (MadsLorentzen), adapted for DOCX + US ATS JDs.

**Why it exists:** an ATS ranks a resume on the literal keywords it extracts from the *text layer*, not on what the resume means. A resume that reads as a perfect fit to a human can still score low because it phrases a required skill differently than the posting does. This check catches the highest-value miss: a keyword the candidate **genuinely has** but the resume never literally says.

It attacks the diagnosed problem directly — losing to "closer experience." Where the experience is genuinely there, this makes sure the screen sees it.

## The split of labor

| Step | Who | What |
|---|---|---|
| 1. Extract keywords | **agent** | Read the JD (via the ATS API). List required + preferred terms — tools, skills, the "N years of X" gates. Judgment. |
| 2. Match | **tool** | `tools/ats_check.py` extracts the resume's real text and matches each keyword verbatim + synonyms. Mechanical. |
| 3. Classify gaps | **agent** | For each `missing`, decide **have-it** (add) vs **gap** (leave) against `candidate_profile.json`. Judgment. |
| 4. Apply | **agent** | Add have-it terms truthfully; run the tailoring truthfulness gate; re-run the check. |

## Running it

In the full pre-submit sequence, **don't call `ats_check` standalone** — `presubmit_gate.py` bundles it, and its `missing_required` / `synonym_required` output is exactly step 3's input (SKILL.md §3c-gate). Call it directly only when iterating on keyword coverage in isolation:

```bash
python tools/ats_check.py ~/Documents/Resume/{variant}.docx keywords.json
```

`keywords.json` — the agent writes this from the JD:

```json
[
  {"term": "authentication", "priority": "required", "synonyms": ["authn"]},
  {"term": "A/B testing", "priority": "preferred", "synonyms": ["experimentation"]}
]
```

Output classifies each term: **covered** (verbatim) · **synonym-only** (concept present, prefer the posting's word if truthful) · **missing**.

## The four verdicts on a missing keyword

| Verdict | Action |
|---|---|
| **missing (have it)** | Profile shows the candidate genuinely has it; resume never says it → **add it**, preferring an experience bullet over the summary. Highest-value case. |
| **synonym-only** | Concept is there under another word → swap to the posting's exact term **if truthful** (ATS matches are often literal). |
| **missing (gap)** | A real gap → **leave it.** Acknowledge in the cover note's framing, never in the resume. |
| **never-claim** | On the `never_claim` list → **leave it**, even though the tool flags it and the JD wants it. The honesty rule overrides the keyword. |

## The rule that makes this safe

**Never keyword-stuff.** Adding a term the candidate doesn't own is the exact move that fails a final-round interview — the place the losses have been. The tool surfaces gaps; it does not license filling them. OAuth on the ID.me run is the canonical example: required-adjacent, wanted by the JD 24×, flagged missing — and correctly left off because it's confirmed false.

## Worked example — 2026-07-22, ID.me / Fraud variant

First run: **2/4 required covered.** `security platform` missing, `product management` synonym-only.

Classification: both **have-it** — the candidate closed a "critical post-acquisition security gap" and built trust & safety infrastructure (security-platform work, phrase absent), and the title is Product Manager (exact phrase "product management" absent). Added both truthfully.

`OAuth`, `wallet`, `credential` → left as gaps. OAuth is on never_claim.

Second run: **4/4 required covered.** Two real keywords recovered, nothing fabricated.
