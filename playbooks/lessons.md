# Lessons — post-mortems behind the rules

**Not loaded during a normal run.** SKILL.md sits in the cached context prefix and is
re-billed on every tool-call round-trip, so the *rules* live there but their dated
*evidence* lives here. Open this only when questioning or refining a rule — never needed
to execute one. Each rule in SKILL.md that trades on a past failure points here by anchor.

If you change a rule because you think its post-mortem no longer applies, read the entry
first — several of these are the reason a specific bug does not recur.

## web-search-is-stale
Rule: *scan live ATS boards; do not source leads from web search.* On the 2026-07-22 pass,
**5 of 5** postings sourced from web search were dead — removed, redirected with
`?error=true`, or closed months earlier. Search engines index job postings and never
re-crawl them when they close, so a search result is evidence a role *existed*, not that it
is open. Every lead that survived came from scanning a company's live board. Search is only
for discovering *which companies* are hiring.

## affirm-exact-match-miss
Rule: *never dedupe on exact title match; use prefix + normalized seniority/family.* 67% of
`applied_history.csv` uses bare generic titles ("Senior Product Manager" ×286), while live
postings are qualified ("Senior Product Manager, Credit & Pricing"), so exact match almost
never fires. Measured failure: Affirm's *Credit & Pricing* role **was** in the history,
dated 2026-07-07, and the exact-match check cleared it as new. Only a browser-extension
(Simplify) banner caught the duplicate. This is why `dedupe_check.py` exists and `grep`
is not sufficient.

## marqeta-stale-export
Rule: *check the newest `applied_date` before trusting the history; the Simplify banner
wins.* `applied_history.csv` is a point-in-time Simplify export, not a live feed — anything
applied after the export date is invisible. Marqeta was applied 2026-07-23 while the
export's latest row was 2026-07-14, so it read as 0 prior and got ranked #1. Saturation did
not catch it either (2 prior) — saturation and duplication are different failures.

## saturation-diagnosis
Rule: *the pipeline's job is to find unsaturated roles, not more roles.* The diagnosis
behind it: a large volume of prior applications produced no tracked interviews, and nearly half were repeat submissions
to a company+title already applied to. Attribute targeting was fine — 78% Product Manager,
68% at the right level, 87% inside the location gate. What was broken was depth per company:
an ATS shows a recruiter every application tied to one email, so 31 applications to Stripe
reads as indiscriminate and suppresses all of them at once. A run that surfaces 5 roles at 5
new companies beats one that surfaces 30 at companies already applied to 40 times.
(Saturation *skip* is currently OFF per the user — surfaced only; see `application_rules.md`.)

## titles-lie
Rule: *read the full JD body first; never score or tailor from a title.* On 2026-07-22,
"Staff PM, App Platform" read as API-platform work and turned out to be consumer-app design
systems; the same day "Staff PM, Claims Experience" read as a domain mismatch and turned out
to be operational tooling — a direct hit. Titles mislead in both directions.

## oauth-self-check
Rule: *a separate reviewer agent (not the drafter) runs the factual audit.* Self-checking is
what let an OAuth claim cross-contaminate a résumé variant on 2026-07-22 — the drafter shares
the blind spot that produced the error. The independent reviewer, refuting each claim against
MASTER + profile + JD, is the fix. (OAuth is on the never_claim list.)

## greenhouse-fully-fillable
Context for "a complete Greenhouse form is fillable except the résumé": the ID.me form on
2026-07-22 reached 7 text fields + 7 dropdowns with 0 required fields remaining, entirely via
stable IDs + the react-select method. The résumé upload is the only step needing the user.

## marqeta-dropdown-batching
Rule: *fill dropdowns one per tool call.* Batching several opens leaves multiple react-select
menus mounted and the wrong option gets selected — worked on ID.me, then failed on Marqeta
when batched.

## textutil-spacing-artifacts
Rule: *read exact résumé text from `word/document.xml` in the .docx zip, not `textutil`.*
`textutil` renders rather than extracts and introduces spacing artifacts; trusting it
produced three false typo reports on 2026-07-22.
