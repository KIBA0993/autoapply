# Embedded / branded-page ATS wrappers

A company hosts its jobs on a real ATS (usually Greenhouse) but forces applicants through
its **own branded careers page** (`company.com/careers/...`), which embeds the form in an
iframe or a custom widget. The visible fields don't accept synthetic input — the
accessibility tree is empty except a chat widget, `elementFromPoint` lands on an iframe,
and typed text never registers. This one pattern caused **4 of 5 blockers** on the
2026-08-05 run (Brex ×2, Fingerprint, Coalition).

## Recognize it fast
- The board API's `absolute_url` is the **company domain**, not `job-boards.greenhouse.io`
  (e.g. Brex → `https://www.brex.com/careers/8616324002?gh_jid=8616324002`).
- Navigating the raw `job-boards.greenhouse.io/{slug}/jobs/{id}` **302-redirects back** to
  that branded page (verified for Brex, 2026-08-05) — so the normal ATS URL is no escape.
- On the page: fields visible but not fillable; a11y tree empty; keystrokes don't land.

## The bypass ladder — try in order, then fast-fail

1. **Greenhouse-wrapped → go straight to the embed form.** The standalone Greenhouse
   application iframe renders on greenhouse.io, *outside* the broken wrapper:
   ```
   https://boards.greenhouse.io/embed/job_app?for={slug}&token={gh_jid}
   ```
   `{slug}` = the Greenhouse board slug (the company, e.g. `brex`); `{gh_jid}` = the
   `gh_jid` query param on the branded URL. **Verified 2026-08-05:** the Brex Staff-PM-AI
   embed returns the real "Job Application for … at Brex" form (fields are JS-injected, so
   let the page render, then drive it by Greenhouse's stable IDs per `playbooks/greenhouse.md`).
   Open it in a **fresh tab**; do not try to fix the wrapper in place.
2. **Embed URL 404s (Fingerprint) or it's a Salesforce Experience Cloud / other custom
   embed (Coalition — empty a11y tree except the chat widget).** No known automation path.
   **Do not keep trying** — log to `blocker_queue.csv` and hand off.

## Fast-fail rule — the actual token lesson
The Brex block burned attempts on direct click, click+wait, *and* the "Quick Apply" button
before logging. Don't. **One** failed input attempt on a page you've recognized as a wrapper
→ try the embed URL (step 1) → if that doesn't render a live form, **log and move on.**
Never run three different fill strategies against a wrapper; the root cause is shared, so
they all fail the same way and each is a wasted full-context round-trip.

## Applying still hands off
Even when the embed form is drivable, submit remains the user's confirm (§3d) and the
résumé upload follows the normal file-upload constraint. The win here is recovering a form
that was previously a dead blocker — not new autonomy.
