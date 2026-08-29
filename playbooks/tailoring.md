# Résumé tailoring

**Domain variants, not per-posting files.** Decision 2026-07-22: maintain a handful of strong variants tuned to the vocabulary of a whole domain, refreshed as the JD corpus grows. Route by domain; fall back to MASTER for anything general.

Per-posting tailoring was tried and dropped — it produces one file per application for marginal gain, and the vocabulary that matters turns out to be stable *across* a domain rather than specific to one posting.

Bounded by one rule: **reorder and re-emphasize what is true; never add what is not.**

## Refreshing a domain variant from the corpus

When enough new postings accumulate in a domain (~5+), re-derive its vocabulary instead of guessing:

1. Pull JD bodies for that domain's roles from the ATS APIs
2. Count recurring terms across the whole set
3. Rewrite the variant's summary and Domain Expertise line to lead with the top terms — **only** where an existing bullet supports them
4. Run the truthfulness gate against MASTER
5. Never touch employers, titles, dates, or metrics

The 2026-07-22 corpus (13 JDs) produced results that contradicted my assumptions:

| Domain | Top terms | Assumption it broke |
|---|---|---|
| Fraud / identity | **data=88**, authentication=24, identity=24, internal=21, API=19, compliance=19 | `fraud` was only 17 — these are data-platform and internal-tooling roles more than fraud roles |
| Fintech / payments | **AI=46**, payments=21, internal=14, automation=11 | AI outranks payments by 2× |
| Insurance | claims=30, data=25, internal=12, automation=8 | Claims roles are operational-tooling roles |

`internal` ranks top-5 in **all three** — internal-facing platform work is the through-line, and every variant now leads with it.

Why it matters here: the candidate reaches final rounds and loses to candidates with "closer experience." Tailoring is how an existing history is made to read as the closer experience — when it genuinely is.

---

## Step 1 — Extract the posting's own vocabulary

From the JD body, pull:

- **Required years + the specific gate** — e.g. ID.me's *"3 years owning authentication, identity, or security platform products"*
- **Repeated nouns** — the terms the JD uses for the work (`claims workflows`, `bot management`, `risk platform`, `underwriting`)
- **Named responsibilities** — verbs the role owns (`lead migrations`, `reduce manual overhead`, `serve internal customers`)
- **Domain words** the company uses for itself (`Active Insurance`, `identity graph`, `device intelligence`)

ATS keyword screens match on these. So do humans skimming for thirty seconds.

## Step 2 — Map, don't invent

Build the mapping explicitly before editing:

| JD term | Candidate's existing bullet | Same thing? |
|---|---|---|

Three outcomes per row:

- **Same thing, different words** → rewrite the bullet in the JD's vocabulary. This is the whole game.
- **Adjacent** → keep the bullet as-is. Do not stretch it. Stretching is what gets exposed in the final round.
- **Absent** → leave it out. A gap named in the cover answer beats a gap faked on the résumé.

## Step 3 — Edit only these three zones

**Summary (highest leverage).** Rewrite to lead with whatever the JD gates on. Six insurance years lead for a carrier; authentication and identity lead for ID.me. Same facts, different first clause.

**Domain Expertise / Skills line.** Reorder so the JD's terms appear first. Add a term only where an existing bullet demonstrates it.

**Bullet phrasing within the matched role.** Re-word to the JD's nouns. Keep every number exactly as it was.

**Do not touch:** employers, titles, dates, metrics, education. Those are facts and they must match `candidate_profile.json` and any background check.

## Step 3b — De-AI voice pass

Added 2026-08-02. The user's résumé must not read as machine-written — a recruiter who smells AI discounts everything on the page. This is a *voice* gate, separate from the truth gate: rewrite for a human ear while every claim still traces.

The rule that makes it safe: **strip the AI connective tissue; keep every ATS-keyword noun.** The domain nouns (fraud, identity, authentication, risk decisioning, trust & safety, behavioral signals, compliance) are what clear the keyword screen, so they stay. Only the filler goes.

Seven rules:

1. **No em dashes.** Restructure into periods or commas. (Grounded in gstack `design-review`, which bans them outright; the press over-blames the em dash alone, but it co-occurring with the tells below is what tips a reader.)
2. **Break the tricolon.** The rule-of-three reflex ("risk, identity, and trust & safety") is the loudest tell. Use two items, or four, or one specific instead of a list.
3. **Kill the clichés.** Banned: *proven ability, deep expertise, at scale, leverage, robust, seamless, spanning, track record, world-class, driving (as a summary gerund), showcase, comprehensive, delve, foster, landscape, underscore*. Full list in `tools/deai_lint.py`.
4. **Vary sentence length.** AI writes uniform medium sentences; add one short, punchy one.
5. **Cut grandiosity.** "protect platform integrity at scale" → say the specific thing it protected.
6. **Lead with a number, not an adjective.** The summary's first concrete claim should be a metric.
7. **Still passes `claim_trace`.** De-AI-ing rephrases; it never invents to fill a gap.

Note: MASTER's own summary fails this pass ("Deep expertise… at scale… Track record of… Proven ability to"). The category variants are *better* than MASTER on voice, not just reworded from it.

While drafting, you can run either linter alone to iterate on one dimension:

```bash
python tools/deai_lint.py <variant.docx>   # voice: em dashes + AI vocabulary
python tools/claim_trace.py <variant.docx> # truth: number drift + never-claim
```

`deai_lint` scans only prose zones (Summary, Domain Expertise, bullets) — it ignores the en dash used as a separator in title lines. Both tools exit non-zero on a hit. **But in the full pre-submit sequence, don't run these standalone** — `presubmit_gate.py` bundles both (and `ats_check`) in one run; see SKILL.md §3c-gate. Standalone here is only for iterating a single dimension mid-draft.

## Never-claim list

Check `candidate_profile.json` → `never_claim` before writing any summary or skills line. It holds terms explicitly confirmed **false**, which is different from terms merely absent.

Currently: **OAuth** — confirmed not true 2026-07-22. It surfaced because it appeared in a duplicated résumé block that iCloud sync later deleted, and because "authentication" is a top term in identity-company JDs. Authentication and SSO *are* accurate for the a prior financial-services employer role; OAuth is not. Do not treat adjacent terms as interchangeable.

The general trap: a high-frequency JD term creates pressure to match it. Matching a term the candidate does not own is exactly what fails in a final-round interview.

## Step 4 — Truthfulness gate

Before saving, every changed line must pass:

- [ ] The claim exists in the source résumé or `candidate_profile.json`
- [ ] No number changed — not rounded, not scaled, not re-attributed
- [ ] No title upgraded beyond what was held
- [ ] No tool, domain, or employer added
- [ ] Every rewritten bullet is defensible for ten minutes of interview questions

**Any new number or claim the user has not confirmed gets flagged, not written.**

## Step 5 — Save as a new version

```
Candidate_Resume_{Variant}_{Company}.docx
```

Never overwrite a source. Record the path in `job_pool.csv` → `resume_variant`.

## Mechanics

`python-docx` is installed. Copy the base variant, edit paragraphs in place, keep the first run's formatting:

```python
def set_text(p, txt):
    p.runs[0].text = txt
    for r in p.runs[1:]:
        r.text = ''
```

Two hazards, both hit on 2026-07-22:

- **`~/Documents/Resume/` is iCloud-synced.** Re-read immediately before editing; files change under you mid-session.
- **Verify by reading `word/document.xml` from the `.docx` zip**, not with `textutil` — textutil renders rather than extracts and introduced spacing artifacts that produced three false typo reports.

## Keep .docx and .pdf in sync

User rule (2026-08-03): **every time a variant's .docx is generated or refreshed, regenerate its .pdf in the same pass** — the two must never drift. Some ATS require a PDF upload; a stale PDF ships old wording.

```bash
python tools/make_pdfs.py                 # all 9 category variants
python tools/make_pdfs.py Fraud Identity  # only specific ones
```

Converter order: LibreOffice `soffice --headless` if installed (reliable), else `docx2pdf` via Microsoft Word. Word's automation bridge wedges intermittently and cascades — `make_pdfs.py` isolates each file in its own subprocess and converts a temp copy (so a variant left open in Word doesn't lock it). If Word is fully wedged, quit Word and re-run, or install LibreOffice (`brew install --cask libreoffice`) for a converter that never wedges.

## When to skip tailoring

- Low fit — the base variant is fine, spend the time on a better-matched posting
- The routed variant already uses the JD's vocabulary
- Tier 3–4 ATS (Workday and friends) where the résumé is re-keyed into a form anyway

## Worked example — Insurance variant, 2026-07-22

Base: `MASTER`, summary opened *"9+ years building API platforms, partner ecosystems, and developer-facing infrastructure."*

For insurance roles that buries the relevant decade. Rewritten to open with six years at prior insurance employers, then risk scoring → quote volume +50%, $100M portfolio, +30pt margin, actuarial/compliance partnership — with a prior financial-services employer repositioned as current risk-and-identity work rather than the headline.

Every claim was already on the résumé. Nothing was added. Domain Expertise was reordered to lead with Underwriting & Risk Scoring, Pricing & Portfolio Strategy, Insurance Operations.
