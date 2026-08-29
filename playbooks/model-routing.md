# Model routing (optional, for token/cost)

Load this only when you want to run a tiered pass for cost. It does not change *what*
gets filled or any safety rule — only *which model* does each step. Validated by the
fixture A/B + live check in `docs/token-optimization-proposal.md` (n=4 per model, 12/12
runs with zero missed-safety escalations and zero fabrications).

## The one mechanism that is safe for live form-fill: manual `/model`

**Apply the fill tier by switching `/model` in the MAIN session — never by handing the
live browser to a subagent.** Entering PII into a form is permission-gated; the user's
consent lives in this chat, and a subagent cannot see it (a correct Sonnet subagent will
*refuse* to type PII on an orchestrator's say-so — verified 2026-08-04). So:

- `/model sonnet` for the mechanical fill (text fields, yes/no toggles, dropdowns).
- `/model opus` before any judgment/essay/eligibility/comp/never-claim decision.
- Keep the switch in the main loop: consent is visible, and the context cache stays warm
  (no cold-start reload).

Subagents are fine for **offline** stages only — decision planning, essay drafting from
supplied facts, dedup, ATS/keyword checks — anything that does not enter PII into a live
form.

## Who does what

| Task | Model | Notes |
|---|---|---|
| find / dedup / `ats_check` / `presubmit_gate` / `claim_trace` | none (scripts) | already token-free |
| mechanical text-field + toggle + dropdown fill | **Sonnet** | fail-closed contract below; ~40% of Opus cost |
| field-label → profile-key mapping (sub-step) | Haiku (optional) | mechanics only; fail-closed |
| essays / "why company" / cover letter | **Opus** | judgment + voice |
| résumé routing + tailoring + vocabulary | **Opus** | truthfulness-critical |
| independent factual-audit reviewer | **Opus** | must not share the drafter's blind spots |
| every ask-on-uncertain / injection / comp / sponsorship / eligibility / never-claim call | **Opus** | safety judgment, never delegated down |

**Haiku is mechanics-only.** It plans Ashby widget mechanics correctly (0 dropdown-method
errors) but missed a cross-field eligibility contradiction that Opus caught. Do not let
Haiku (or Sonnet) resolve judgment/eligibility.

## Fail-closed escalation contract (for the cheaper tier)

While on Sonnet/Haiku, **stop and hand back to Opus / ask the user** the moment a field:
- touches **compensation / salary** in any form (free text, required number, published range);
- touches **sponsorship / work-authorization nuance** beyond the two standard yes/no questions;
- is an **eligibility / residency-screen** question (e.g. "are you located in an ineligible state?") — these can self-DQ; see [[application-form-standing-answers]] location caveat;
- is any **free-text essay** / "why this company" / "describe your…";
- touches a **never_claim** topic (OAuth; hands-on legal-tech-platform ownership);
- is an **ambiguous dropdown** whose correct option is unclear.

A cheaper tier may fill known values and verify; it may **never** resolve a safety call to
save a round-trip. Submit is always the user's click, on any tier.

## When it's worth it

Reduction work (caching, structured browser reads, script-based dedup) comes first —
tiering is a multiplier on what's left, ~20–25% additional cost saving once browser reads
are already reduced. For a single supervised form the `/model` switch is near-free; for a
batch, fan out the *offline* stages to subagents and keep the live fill in the main loop.
