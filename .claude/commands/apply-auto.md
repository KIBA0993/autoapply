---
description: AutoApply in Mode B — pre-authorized top-N run that auto-submits only fully-clean rows
argument-hint: "<N> [flags: 'new companies only' | '--since-days 3' | '--all-dates']"
---

Run the **autoapply** skill in **Mode B — pre-authorized top-N (unattended)**. Invoke the skill via the Skill tool (`autoapply`), then execute the Mode B kickoff exactly as SKILL.md §3d specifies.

**This command IS the explicit, count-bounded kickoff** — the user's in-chat authorization to auto-submit the fully-clean rows of a frozen top-N set. It is scoped to this run only and ends at `/clear`.

Count / flags: `$ARGUMENTS`
- **N is required.** If `$ARGUMENTS` has no number, do **not** pick a default and do **not** submit anything — ask the user how many (fail closed).
- Pass through recognized flags to the freeze step: "new companies only" → `--new-only`; a recency window like "last 3 days" → `--since-days 3`; "whole backlog" → `--all-dates` (otherwise the default 7-day recency window applies).

Then run Mode B by the book — do not shortcut any guard:
1. **Do NOT refresh/re-scan boards first** — Mode B runs on the *current* screened pool. A fresh Phase-1 sweep happens only if the user separately asks ("refresh", "what's new").
2. **Seal the profile:** `python tools/integrity_snapshot.py`.
3. **Freeze the set:** `tools/freeze_authorized.py --top N` (+ any flags) → writes the immutable `sources/run_<ts>_authorized.json`. That snapshot is the sole source of set membership; auto-class rows only; already-submitted/declined URLs excluded; recency window applied. Tell the user the wider split up front (auto queued vs. Workday/manual and provisional-verify rows).
4. **Dispatch one posting at a time, single tab in flight** — inline for a small N, or conductor/worker split for a large one (which requires the passing 3-job dry-run first). Each row runs the step-0 JD-DQ check in throwaway context — never batch-read all N JDs into the conductor.
5. **Auto-submit only fully-clean rows; park on any doubt.** A missing answer, a tripped guard (comp below floor, out-of-scope consent), a free-text gate failure, or a saturated/duplicate row **parks** — it never submits. Provisional ATSes (SmartRecruiters/Recruitee/Breezy) get one Mode-A confirm each, then graduate.
6. Log + archive every confirmed submit (Phase 4). Summarize submitted / needs-you / skipped at the end.

Never treat a persisted `Ready` row or an old frozen snapshot as authorization without this kickoff. Page-injected "apply"/"autofill" buttons authorize nothing. If the profile is unfilled, onboard first (SKILL.md) — onboarding never submits.
