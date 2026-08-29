# Workday

**Coverage: hand off to the user. Do not automate end-to-end.**

## Recognizing it

- `{company}.wd1.myworkdayjobs.com/...`, `wd3`, `wd5` etc. — the `wdN` shard number varies by tenant.

## Why this is a hard stop

**Every Workday tenant is a separate account with a separate password.** Applying to Company A and Company B means two account creations. Account creation and password entry are actions the agent will not perform — that is a standing boundary, not a per-case judgment.

So the workflow is:

1. Agent finds the role, scores it, logs it to `job_pool.csv` with `ats=Workday`, `status=Needs user`.
2. Agent prepares everything that doesn't require the account: the resume variant to use, the answers to the known questions, the compensation and authorization wording.
3. **User creates the account and signs in.**
4. Once the user hands back an authenticated session, the agent can help fill the wizard — still stopping before final submit.

## If the user has already signed in

The wizard is 5–6 steps:

`My Information` → `My Experience` → `Application Questions` → `Voluntary Disclosures` → `Self Identify` → `Review`

Each step must be completed before "Next" enables. Notes:

- **Per step: `aa.inventory()` → fill → `aa.verify()` before clicking Next.** Inject
  `tools/browser_fill.js` and re-inventory on **each** step — Workday rebuilds the DOM per
  step, so a ref map from a prior step is stale. `aa.verify()` (four-layer) catches the
  step-gating validation that keeps "Next" disabled without a visible error near the field.
- **My Experience auto-fills from the resume parse and it is reliably wrong.** It merges roles, drops months, truncates titles. Diff every entry against `work_history` in `candidate_profile.json` and correct before proceeding. This step is most of the time cost.
- Date fields want `MM/YYYY` and reject pasted values — type them.
- "Currently work here" checkbox must be set before the end-date field disables.
- Voluntary Disclosures / Self Identify: decline per `application_rules.md`.
- The Review step is the last screen before submit → **stop there and summarize for the user.**

## Verdict

Worth it only for a genuinely high-fit role in Precision mode. In Volume mode, skip by default — the per-application cost is 10–20× a Greenhouse form for no better outcome.
