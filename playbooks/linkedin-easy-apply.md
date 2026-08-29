# LinkedIn Easy Apply

**Coverage: use for discovery. Be deliberate about automating submission.**

## The honest framing

LinkedIn's User Agreement prohibits automated access, scraping, and bots. That is what `Auto_job_applier_linkedIn` does with `undetected-chromedriver` — it is explicitly built to evade detection, and the tradeoff is your account.

Account restriction on LinkedIn is not a slap on the wrist while you are job hunting: it takes down your profile, your recruiter messages, and your network at exactly the moment you need them. Weigh that against ~100 low-signal Easy Apply submissions.

**Recommended split:**
- **Discovery via LinkedIn** — searching and reading postings at human pace is normal product use. Harvest leads into `job_pool.csv`.
- **Application via the company's ATS** — most Easy Apply postings also exist on the company's Greenhouse/Lever board, where there is no ToS problem, no account risk, and the form carries more signal.

Where a role is Easy Apply *only* and worth it, apply manually or drive it at human pace with a hard stop before submit.

## If you do drive Easy Apply

- Requires an authenticated session. Never automate the login.
- The form is a modal, 1–5 steps: `Next` → `Review` → `Submit application`.
- Step 1 is usually pre-filled contact info from the profile — verify the phone country code, which resets often.
- Resume: choose an existing upload or add new. Uploads persist per-account; reuse rather than re-uploading each time.
- Screening questions are frequently numeric ("years of experience with X"). Never invent one — these come from the answer bank or the user.
- Some postings show a "Follow company" checkbox pre-checked; uncheck unless the user wants it.
- `Submit application` is irreversible with no confirmation dialog. Stop before it.

## Signal quality

Easy Apply is a minority of LinkedIn postings and skews toward high-volume, low-conversion listings — recruiters receive hundreds per role. Treat it as the low-priority tier, not the core of the strategy.
