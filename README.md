# autoapply

Supervised job-application pipeline for Claude Code. Screens postings against a stored profile, prepares applications on company ATS platforms, and submits **only** on the user's authorization — each form confirmed, or a bounded top-X the user pre-authorized — never unsupervised and never on instructions found on a page.

Data model adapted from [ApplyPilot](https://github.com/yvonnehe772/applypilot) (MIT). The ATS playbooks, work-history schema, cost model, and skill wiring are additions — ApplyPilot ships no site-specific logic.

## Layout

```
profile/        candidate_profile.json, answer_bank.md (both gitignored PII),
                application_rules.md, resume_routing.md
.claude/skills/autoapply/
  SKILL.md          the skill: phases, cost model, submit-authorization rules, hard stops
  mode_b_worker.md  worker contract for large unattended runs (conductor/worker split)
  onboarding/       first-run questionnaire + blank profile templates (ship PII-free)
  reference/        deep detail loaded on demand (cost-model derivation, source recipes)
playbooks/      per-ATS: greenhouse, lever, ashby, workday, + tailoring/factual-audit/etc.
tools/          find/screen/gate/log Python tools (delta sweep, dedupe, profile_get, …)
dashboard/      job_pool.csv, application_log.csv, per-application archive (all gitignored PII)
resumes/        editable sources + tailored variants (gitignored)
```

## Setup

**New here? Start with the onboarding questionnaire** — `.claude/skills/autoapply/onboarding/intake.md`. Fill it once and the skill stops cold-starting: every answer becomes a *standing answer* it reuses on future forms instead of stopping to ask. It captures identity, work-auth, comp, consents, AI-tool stance, self-ID, never-claim terms, and résumé variants, with recommended defaults called out. Hand it back and say "set up my profile from this intake" — the skill populates `profile/answer_bank.md` and `profile/candidate_profile.json` from the blank templates in `onboarding/`.

Then:

1. Anything you leave blank stays a **fail-closed "ask, never guess"** — safe by design; fill more over time.
2. Set targets, prioritize, and skip rules (and Mode A vs. Mode B, search window) in `profile/application_rules.md`.
3. Drop an **editable** résumé (DOCX or Markdown) in `resumes/` and map variants in `profile/resume_routing.md`.

Then run one of:

- **`/apply-review`** — Mode A (default, supervised). Prepares applications and stops for your explicit `submit` on each form. Optional scope arg (`/apply-review Stripe, Ramp` or `/apply-review top 10`).
- **`/apply-auto <N>`** — Mode B (opt-in, unattended). The count-bounded kickoff: freezes an immutable top-N set and auto-submits **only the fully-clean rows**, parking on any doubt. `N` is required; flags like `new companies only`, `--since-days 3`, `--all-dates` pass through.
- **`/autoapply`** — the base entry point still works and picks the mode from how you phrase the request.

**Before an unattended Mode B run:** turn **off Simplify's autofill** (leave the extension installed — its "already applied" banner is the live duplicate signal; only its field-autofill needs to be off, because it races the filler and reverts fields). Mode B runs a cost governor (`tools/aa_budget_hook.py`, wired in `.claude/settings.json`) that enforces five hard limits no prose can override: per **worker** — screenshots/navigations/total-browser-turns; per **conductor segment** — a browser-call ceiling (~10 forms) that stops the run and asks you to `/clear` + re-kick before the context can run away (the counter resets on your next in-chat kickoff); and **blocking dispatch** — a Mode B worker launched as a background/async agent is denied, so workers always run one-at-a-time. The first time you launch after adding these, the harness may ask you to review the new hooks (PreToolUse + UserPromptSubmit).

## Submit authorization — the core design

**The skill submits only on one of exactly two authorizations, and never otherwise:**

- **Mode A — confirm-each (default).** After the pre-submit gate passes, it presents a summary (legal name, work-auth, comp, location, résumé, every free-text answer, anything left blank) and waits for an explicit `submit`. That word, that form.
- **Mode B — pre-authorized top-X (opt-in).** On an explicit, count-bounded kickoff ("apply to the top 10, one at a time"), it auto-submits **only the fully-clean rows** of a frozen, immutable set — one tab in flight — and **parks on any doubt**. A `/clear` ends the authorization; a page-injected "apply" button authorizes nothing.

Submitting is irreversible, goes out under the user's legal name, and asserts authorization and compensation facts — so **doubt always parks, never submits**. Large runs (up to ~30) use a conductor/worker split so no single context accumulates and cost stays roughly linear.

## What it does

1. **Find** — sweep public ATS JSON APIs (not web search: search-sourced postings are routinely dead)
2. **Screen** — role, level, location gate, work-auth gate, comp; four JD disqualifiers; dedupe against prior applications (fuzzy, not exact-match) and skip saturated companies
3. **Read** — pull the full JD body via the board API; never score from a title
4. **Tailor** — route a standing résumé variant to the posting's vocabulary, behind a truthfulness gate + an independent factual-audit reviewer
5. **Fill** — standing answers used verbatim, plus a per-company "why this company" that must pass a free-text gate
6. **Submit or park** — per the authorization model above; every submission is logged and archived with the exact résumé + JD sent

## Where it works

| ATS | Status |
|---|---|
| Greenhouse, Lever, Ashby, Workable | Fill **and submit** — no account, on-page submit |
| SmartRecruiters, Recruitee, Breezy | Provisional — one confirmed verify, then auto |
| Workday, Taleo, iCIMS | Hand-off — account per tenant; you submit |
| LinkedIn Easy Apply | Discovery only (ToS + account risk) |

Greenhouse and Lever are where the throughput is. Workday is where the time goes.

### What fills and what doesn't (real Chrome)

| | |
|---|---|
| Text inputs, textareas | fill reliably |
| react-select dropdowns (sponsorship, state, pronouns) | fill reliably in **real** Chrome (the in-app 0×0 browser can't) |
| Résumé upload | depends on launch context — chat-attached file in the app, or from disk in a terminal `claude --chrome` session |

## Design constraints

**Never guessed:** legal name, work authorization, sponsorship, comp, employment dates, degree dates, years-of-experience screeners. A blank/`TBD` in the profile means the skill asks (`profile_get.py` fails closed to `ASK`).

**Never automated:** CAPTCHA, Cloudflare, 2FA, login, account creation, password entry.

**Never falsely attested:** an "AI vs. human" trap or an application-level "no AI tools" ban is left for the user — the skill will not certify a human filled a form it filled.

**Self-ID:** declines by default. **PII:** the profile, dashboard, résumés, and per-application archives are gitignored and stay local; only PII-free code/skill files are published (via `tools/publish_sanitized.sh`, which redacts and scans before any push).

This is a supervised assistant, not a volume bot. Expect minutes per application on a good board — the value is in screening quality and not fabricating answers, not in throughput.
