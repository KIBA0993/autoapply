# "Why this company?" — generator

For required free-text fields: *Why Coalition? · Why do you want to work here? · What excites you about this role?*

Draft it from the posting body and the candidate's own bullets, then run the AI-tell audit below — mechanically via `tools/check_freetext.py`, which gates the draft against the NEVER-CLAIM list and the banned vocabulary here. Then, by mode:

- **Mode A (confirm-each):** the user edits/confirms before submitting.
- **Mode B (pre-authorized):** a draft that passes `check_freetext.py` may auto-send; a draft that trips it **parks** for the user.

**The gate catches never-claim terms and AI tells — not genericness.** A clean-but-generic draft can still pass, so the generator itself must clear the specificity test below; a draft that goes in untouched and generic reads like a draft.

---

## The one test that matters

> Could this exact paragraph be sent to ten other companies with only the name swapped?

If yes, it fails. That is the single thing recruiters report noticing — text that is technically correct and describes no one in particular. Everything below is in service of failing that test loudly.

## Banned vocabulary

These are the reported AI tells. Do not use them, in any conjugation:

`passionate` · `excited` / `thrilled` · `dynamic` · `proven track record` · `leveraged` · `synergize` · `spearhead` · `esteemed` · `cutting-edge` · `deeply resonates` · `drawn to your mission` · `I am confident that my skills and experience` · `results-driven` · `perfect fit` · `esteemed organization` · `at the forefront of`

Also banned as an opening move: praising the mission. Every applicant does it, it requires no research, and it signals nothing. If the mission genuinely matters, demonstrate it through a specific fact, never by asserting admiration.

## Structure that works (3–5 sentences, ~90–130 words)

1. **A specific fact about the company that required actual research.** A number from their own report, a product mechanic, a public engineering decision. Not the mission statement, not the About page's first line. This sentence proves the letter was written for them.
2. **The concrete link to work the candidate has actually done.** Name the employer and the metric. This is where the résumé bullet earns its keep.
3. **Something specific about the role itself** — a responsibility from the posting, restated as something the candidate has already done rather than something they'd like to try.
4. **Optional: the honest gap, owned.** Naming what you have not done reads as confidence, and pre-empts the objection the interviewer already has. Only include when the gap is obvious to the reader anyway.
5. **A plain closing line.** No superlatives.

## Voice rules

- Contractions are fine. Perfect formality is itself a tell.
- One idea per sentence. Stacked subordinate clauses read as generated.
- Numbers over adjectives, always: "scaled quote volume 50% while holding loss ratio thresholds" beats "drove significant growth."
- No em-dash pile-ups, no tricolon ("faster, smarter, and more effective"). Marketing cadence is a tell.
- Never assert emotion. Show the reason, let the reader infer the interest.

## Audit before returning a draft

- [ ] Zero banned words
- [ ] At least one company-specific fact that took research
- [ ] At least one number from the candidate's real history
- [ ] Fails the ten-employers test
- [ ] Nothing asserted that is not in `candidate_profile.json` or the résumé
- [ ] Reads aloud like a person talking, not a press release

## Sources

Recruiter-reported tells and structural guidance: [HRLens](https://www.hrlens.io/articles/stop-using-these-chatgpt-cover-letter-prompts) · [The Muse](https://themuse.com/advice/chatgpt-cover-letter) · [BU Careers](https://careers.bu.edu/blog/2025/01/21/how-to-use-chatgpt-to-write-a-cover-letter-that-sounds-like-you/) · [ProductGym](https://productgym.io/how-to-answer-why-do-you-want-to-work-here-in-a-product-manager-interview/)
