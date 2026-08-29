# Resume Routing

## ⚠️ `~/Documents/Resume/` is iCloud-synced

Confirmed 2026-07-22. Files change under you mid-session: during this session all twelve `.docx` files were replaced by a sync, and text that was present at 15:30 (a duplicated prior-employer block, `governing for`, `operation efficiency`) was gone by 20:34.

Consequences:

- **Re-read a resume immediately before using it.** Never trust content read earlier in a session.
- **`textutil` is not authoritative** — it inserts spacing artifacts. Read `word/document.xml` from the `.docx` zip when verifying exact text. An audit built on `textutil` output produced three false typo reports this session.
- **Don't write backups into this folder** — they sync too. Use the scratchpad.
- After building a variant, diff its bullets against the current MASTER to confirm it isn't stale.

## Source format

Keep an **editable** source (DOCX or Markdown). A PDF-only setup means no reliable tailoring — the agent can review a PDF and draft a replacement, but not edit it in place.

Store sources in `resumes/`. Never overwrite a source; tailored outputs get new filenames and are recorded in `job_pool.csv` under `resume_variant`.

## Variants

Sources live in `~/Documents/Resume/`. **DOCX only** — the PDFs are exports, not sources.

**12 domain variants, rebuilt 2026-08-03** from a broad ATS corpus (258 PM roles) with the de-AI voice pass, and each cleared both gates (`tools/deai_lint.py` + `tools/claim_trace.py`). PDFs are kept in sync via `tools/make_pdfs.py`.

| Role family | File | Use for |
|---|---|---|
| General PM | `Candidate_Resume_MASTER.docx` | Default when no domain signal dominates |
| Fraud | `Candidate_Resume_Fraud.docx` | Fraud, abuse, trust & safety, behavioral risk |
| Risk | `Candidate_Resume_Risk.docx` | Risk decisioning, underwriting, loss-ratio, portfolio risk |
| Identity | `Candidate_Resume_Identity.docx` | Identity, authentication, SSO, access, account security (**not** KYC/AML — hard gap) |
| Fintech | `Candidate_Resume_Fintech.docx` | Regulated fintech, FS platforms, financial products (reframed from the old Payments variant) |
| Finance | `Candidate_Resume_Finance.docx` | Brokerage, retirement, wealth, investing |
| Insurance | `Candidate_Resume_Insurance.docx` | Insurtech, carriers — underwriting, pricing, portfolio, risk platform |
| Lending | `Candidate_Resume_Lending.docx` | Credit risk, underwriting, risk-based pricing, automated decisioning |
| Pricing | `Candidate_Resume_Pricing.docx` | Pricing strategy, margin, dynamic pricing |
| Monetization | `Candidate_Resume_Monetization.docx` | Revenue growth, upsell, conversion, retention |
| Analytics | `Candidate_Resume_Analytics.docx` | Product analytics, experimentation, predictive analytics |
| Platform | `Candidate_Resume_Platform.docx` | API platforms, integrations, developer infra |
| AI/ML | `Candidate_Resume_AI_ML.docx` | ML products, automated decisioning, recommendation, applied LLMs |

**Not routing targets:** `_Intuit`, `_Stripe`, `_SoFi`, `_Netflix`, `_NerdWallet`, `_Quanata`, `_Banking`, `_Financial_data`, `_Airbnb_Wallet` are past per-company tailored outputs. Read them for reusable phrasing; never send one to a different company.

**Not built (scan showed volume but no fit):** Crypto/Web3 (no crypto experience — would be all faked gaps); RegTech/Compliance folds into **Risk** (hands-on legal-tech is a never-claim).

## Routing order

Match on domain first, then role shape:

1. Fraud / abuse / trust & safety → **Fraud**
2. Risk decisioning / underwriting / loss-ratio → **Risk** (credit / lending → **Lending**)
3. Identity / authentication / SSO / access → **Identity** (KYC/AML is a hard gap — acknowledge, never claim)
4. Insurance / insurtech / claims / underwriting → **Insurance**
5. API / platform / developer / integrations → **Platform**
6. Regulated fintech / financial-services platforms / financial products → **Fintech**
7. Brokerage / retirement / wealth / investing → **Finance**
8. Pricing / margin → **Pricing**; revenue / upsell / retention → **Monetization**
9. Analytics / experimentation / predictive analytics → **Analytics**
10. ML / automated decisioning / recommendation / LLM → **AI/ML**
11. Anything else → **MASTER**

Where two match (e.g. a fraud platform role at a fintech), prefer the one matching the *core responsibility* in the posting's first three bullets, not the company's industry.

## Fit scoring

No external score needed. Qualitative, scored per posting:

| Signal | Weight |
|---|---|
| Title / role-family match | high |
| Level and years match | high |
| Work authorization feasibility | gate — fails the whole row |
| Skill / keyword overlap | medium |
| Domain / industry match | medium |
| Form cost vs. value | medium |

Labels: `High` · `Medium` · `Low` · `Stretch`

## Domain variants, not per-posting files

Route to one of the standing variants. **Do not create a file per application.**

The 12 variants were rebuilt 2026-08-03 from a broad ATS corpus, so each already leads with the vocabulary its domain actually uses — see `playbooks/tailoring.md` for the method (incl. the De-AI voice pass) and the refresh procedure.

| If the posting is about | Send |
|---|---|
| Fraud, abuse, trust & safety, behavioral risk | **Fraud** |
| Risk decisioning, underwriting, loss-ratio, portfolio risk | **Risk** |
| Credit risk, lending, risk-based pricing, origination | **Lending** |
| Identity, authentication, SSO, access, account security | **Identity** (KYC/AML/sanctions = hard gap) |
| Insurance, insurtech, claims, underwriting | **Insurance** |
| Regulated fintech, financial-services platforms, financial products | **Fintech** |
| Brokerage, retirement, wealth, investing | **Finance** |
| API, developer platform, integrations, migrations | **Platform** |
| ML products, automated decisioning, recommendation, LLM | **AI/ML** |
| Pricing / margin; revenue, upsell, retention | **Pricing** / **Monetization** |
| Analytics, experimentation, predictive analytics | **Analytics** |
| Banking, brokerage, wealth | **Finance** |
| Anything else | **MASTER** |

Refresh a variant when ~5+ new JDs accumulate in its domain, not per application.

## When to tailor

Tailor when fit is High **and** the ATS is tier 1–2 (a tailored resume behind a Workday account wall is wasted effort).

Do not tailor for: Low fit, tier 3–4 ATS in Volume mode, or when an existing variant already matches the title closely.

## Truthfulness gate

Rewriting is reordering, tightening, and keyword alignment on facts the user has confirmed. It is never:

- inventing metrics, tools, employers, degrees, dates, or authorization
- upgrading a title beyond what was held
- claiming domain experience the user hasn't confirmed

Any generated bullet containing a number the user has not confirmed gets flagged for review before it goes into a submitted resume.

## Pre-submit verification

- Correct variant selected for this role family
- Upload succeeded — filename visible on the page
- Displayed filename matches the intended variant (not a stale prior upload)
