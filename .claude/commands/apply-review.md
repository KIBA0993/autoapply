---
description: AutoApply in Mode A — prepare applications and confirm each submit (supervised, default)
argument-hint: "[optional: companies / space to scope, e.g. 'Stripe, Ramp' or 'top 10']"
---

Run the **autoapply** skill in **Mode A — confirm-each (supervised)**. Invoke the skill via the Skill tool (`autoapply`), then follow its phases with the submit mode pinned to Mode A.

**Mode A means: never auto-submit.** Find → screen → dedupe → read the JD → tailor → fill → run the pre-submit gate, then for every posting present the exact `READY — <Company> · <Title>` confirmation summary from SKILL.md §3d and **wait for the user's explicit `submit`** (that word, that form) before clicking. A blanket "yes", an earlier approval, or "the last few were fine" is not authorization. If the user changes a value, re-fill, re-gate, re-present. This is the default, safest mode — this command does **not** carry any pre-authorization to submit.

Scope: `$ARGUMENTS`
- If a company list or space is given, restrict finding/screening to it.
- If a count like "top 10" is given, **prepare** that many (screen + fill up to the confirmation summary) — but still confirm each submit individually. Preparing N is not authorizing N sends.
- If empty, run the normal find→screen→prepare flow per `profile/application_rules.md`.

Honor everything in SKILL.md: first-time onboarding if the profile is unfilled, the cost-model levers, hard stops, and Phase-4 logging on each confirmed submit.
