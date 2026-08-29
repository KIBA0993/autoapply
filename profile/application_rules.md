# Application Rules

Edit this file before the first run. Everything marked `TBD` blocks automation by design.

## Mode

- **Volume** — stable resume variants, prioritize speed
- **Precision** — tailored materials, user reviews before submit

Selected: **Volume** (promote individual high-fit roles to Precision case by case)

## Boundary for the first runs

- [ ] Lead finding only — find, screen, classify, log. Do not open application flows.
- [x] **Review before every apply** — set 2026-07-22 after the first lead-finding pass validated the screening rules.
- [ ] Limited low-risk apply (1–3 roles, only after the profile is complete)

Scope of the current setting: the agent may open application forms and fill them from the profile. It stops at the review step every time. Submit is always the user's click.

## Search window

How far back a search run looks, by first-posted date. For a **daily / regular refresh**, narrow this so each run surfaces only what's *new* since the last one — you don't re-screen the whole board every day.

- **Selected: `3d`** (last 3 days).
- Options: `24h` · `3d` · `7d` · `all` (no window — use for the first/backfill run or an occasional full sweep).

Applied in Phase 1 via `tools/filter_recent.py` on the true first-posted date each ATS exposes (`first_published` / `publishedAt` / `createdAt`; Workday via `posted_days`). This is a **window, not a fit filter** — it only bounds recency; fit/dedup/liveness still decide in-or-out. A role older than the window isn't rejected on merit, just not re-surfaced this run (it's already in `job_pool.csv` from when it first appeared).

## ATS priority

Derived from `playbooks/`. This ordering is the main lever on throughput.

| Tier | ATS | Why |
|---|---|---|
| 1 | Greenhouse, Lever | Short forms, no account, stable |
| 2 | Ashby, Workable, SmartRecruiters | No account, fussier DOM |
| 3 | LinkedIn Easy Apply | ToS + account risk; discovery only by default |
| 4 | Workday, Oracle/Taleo, iCIMS | Account per tenant → user hand-off |

## Prioritize

Apply quickly when:

- Role families: Product Manager · Technical PM · Platform PM (secondary: Technical Program Manager)
- Titles: any containing **"Product Manager"** or **"Program Manager"**, with Senior / Sr. / Principal / Staff / Lead / Group / II / III
- Level: **Senior through Principal.** Experienced (set specifics in candidate_profile.json) — Principal is in range, not a stretch. Do not skip Principal as overleveled.
- Domain bonus: fintech · insurance · payments · identity & fraud · API platforms · regulated financial services
- Freshness: posted within 48h
- Locations: **Remote (home-state-eligible)** · Hybrid/onsite in **your home metro or approved target metros**. **Apply-order preference: Remote or home-metro first** (no relocation), then the other target metros — this is the location band in Phase 2 ordering, applied *within* fit tier, not as a filter.
- Work authorization: US-authorized, no sponsorship — never a blocker, and never answer "yes" to the sponsorship question
- Form length: ≤ 1 custom question

## Consider

Review before applying when: stretch level, ambiguous location or comp, uncertain resume variant, > 1 custom question.

## Positioning — the actual constraint

Observed pattern: multiple interviews and **several final rounds**, lost to candidates with "closer experience."

That diagnosis matters more than anything else in this file. It means:

- The resume clears ATS keyword screens. Not a problem.
- Phone screens and interview performance are fine. Not a problem.
- **The loss happens at the comparison stage, against a specialist.**

A generalist PM at a consumer marketplace always loses the final round to someone who did that exact thing. The history shows heavy repeat application to a handful of consumer-marketplace companies — at each, somebody in the final round had closer consumer-marketplace experience. That is structural, not bad luck.

**The fix is to compete where the closer experience is the candidate's.** A deep background in risk, identity, fraud, authentication, and pricing inside regulated financial services is unusually specific. At Socure, SentiLink, Fingerprint, ID.me, Alloy, Unit21, Sift, Coalition — the candidate is the specialist and the generalist PM loses to *them*.

Rules that follow:

- **Prioritize by domain specificity, not by company prestige or role count.** A Series-B identity company beats a FAANG consumer req every time, because the final-round comparison is winnable.
- Route the **specialist** resume variant (Fraud, Platform, Finance), never MASTER, wherever a domain variant applies. Generic framing is what loses the comparison.
- Skip roles where the winning candidate would obviously be a domain specialist in something he is not — consumer social, marketplace, gaming, adtech, devtools.
- When a posting names a domain he owns (KYC, AML, sanctions, fraud, identity, authentication, underwriting, pricing), treat it as High regardless of company size.

## Company saturation — the secondary constraint

From the prior application export: a large application history spanning hundreds of companies, nearly half of them repeat submissions to a company+title already applied to, concentrated in a handful of companies.

Why this matters more than any other rule here: an ATS shows a recruiter *every* application tied to your email. A recruiter opening the profile sees dozens of applications to "Product Manager." That does not read as enthusiasm, it reads as indiscriminate, and it suppresses the odds on all of them at once. Volume at one company is negatively correlated with getting a call from that company.

**Rules:**

- **Saturation skip is OFF (user decision 2026-08-05).** `SATURATED` (≥10) is still *surfaced* — the count and dates are shown so you can see the exposure — but it no longer skips the row. Re-enable by setting `SATURATION_BLOCKS = True` in `tools/dedupe_check.py`. The duplicate guard below is unaffected and still stands.
- Never apply to the same company + title twice. Check `dashboard/applied_history.csv`.
- **No per-company cap** (user decision 2026-07-22). Apply to every genuinely distinct, well-fit role at a company. Distinct = different org/scope, not the same title reposted. Airwallex having 16 PM roles across fraud, lending, and agentic-finance orgs is 16 real openings; Stripe "Product Manager" ×31 was one posting re-applied to.
- The saturation guard still stands: the concern was never breadth at one company, it was *duplicate* applications to the *same* role, which recruiters see as indiscriminate. Distinct roles don't trigger that.

## Skip

- Level mismatch — Staff/Principal/Director, or Entry/Junior
- Required years exceed profile by > 2
- **Hybrid or onsite outside your home metro or approved target metros** — hard skip
- **"Remote" that is region-locked to a metro or state excluding your home state** — read the body text, not the header; this is the most common false positive in remote searches
- Agency / contract / internship listings, unless targets say otherwise
- Duplicate of an existing `job_pool.csv` row
- Posting closed or reposted > 30 days

## Hand off to the user — always

- CAPTCHA, Cloudflare, login, 2FA, or any anti-bot challenge
- Account creation or password entry, anywhere, for any reason
- Work authorization / sponsorship / compensation wording not covered exactly by the profile
- Portfolio, video, writing sample, or references required
- Resume upload that cannot be visually confirmed
- **Final submit on every single application**

That last one is not a training-wheels setting. A submitted application cannot be recalled, and a wrong answer on authorization or comp is worse than a missed application. The agent prepares and summarizes; the user submits.

## Status values

`Pending` · `Needs user` · `Skipped` · `Blocked` · `Ready to submit` · `Submitted`

`Ready to submit` requires a **GO** from the pre-submit gate (`python tools/presubmit_gate.py <variant.docx> [keywords.json]` — voice + truth + fit). A BLOCK or an unresolved REVIEW cannot be marked `Ready to submit`. The gate clears the résumé only; the final submit is still the user's click.

`Submitted` requires observed confirmation evidence (confirmation text or URL) recorded in `application_log.csv`. No evidence, no `Submitted`.

## Account policy

Use only these accounts. If a different one appears, stop and ask.

- LinkedIn and application email: see `candidate_profile.json` (gitignored). Do not duplicate them here — this file is committed.
- Job boards: no account creation. Greenhouse, Lever, and Ashby need none — that is why they are tier 1–2.
