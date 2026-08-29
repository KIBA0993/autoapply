# AutoApply intake questionnaire — first-time setup

Fill this out **once** and AutoApply stops cold-starting: every answer here becomes a *standing
answer* the skill reuses on real applications, so it never has to stop and ask you the same
question form after form. You can fill it in plain language — a person or the skill itself then
turns it into the two files the skill reads (`profile/answer_bank.md`,
`profile/candidate_profile.json`).

**Three rules before you start:**
1. **Everything you enter goes out on real applications under your legal name.** Accuracy is not
   optional — a wrong answer here is a wrong answer on every form. If you're unsure, leave it
   blank.
2. **Blank = the skill will ask you, not guess.** Anything you leave empty simply becomes a
   "stop and ask me" the first time it's needed. You lose nothing by skipping — you only lose
   the warm-start for that one field. Never put a guess here to fill a gap.
3. **Recommended defaults are marked `▶ default:`.** Those are the skill's standing behavior for
   most users. Keep them unless you have a reason to change them. Items with no default are
   personal facts only you can supply.

Your answers stay **local** — `answer_bank.md` and `candidate_profile.json` are gitignored and
never published. This blank questionnaire is the only part that ships with the skill.

---

## A. Identity & contact
*(Straight facts. These fill the name/email/phone/link fields on every form.)*

- Legal first name / last name (used on legal-name & background-check fields): ____ / ____
- Preferred name (only where a form has its own field): ____
- Email: ____
- Phone: ____
- LinkedIn URL: ____
- Website / portfolio URL (goes in any Website/Portfolio field): ____
- GitHub URL (only where a separate GitHub field exists): ____
- Pronouns: ____
- Street address: ____
- Zip / postal code: ____
- City of residence: ____  *(note if your municipal city differs from the metro you'd write on open-text "city" fields)*
- State / region: ____
- Country: ____
- Time zone: ____

## B. Work authorization
*(Two **different** questions that both usually appear — never map one onto the other.)*

- "Are you legally authorized to work in [country]?" → ____
- "Will you now or in the future require visa sponsorship?" → ____
- Citizenship status, if a form asks (Citizen / Permanent resident / Temporary visa – employer-specific / Temporary visa – open/transferable / Not authorized): ____
- ⚠️ Work authorization is a hard **gate**: a posting that conflicts with your status fails
  screening regardless of fit. Answer both lines exactly as they apply to you.

## C. Compensation
*(The skill separates **two** uses of your comp number — read both.)*

- **Screening floor** — a posting is only worth applying to if its published **upper** band is at
  or above this number; a ceiling below it is a hard skip. Your floor: $____
- **What to enter on a form** when a salary number is required: ____
  ▶ default: prefer to **defer** wherever the field accepts text ("open / flexible / market"),
  and enter your target number only where a number is mandatory.
- Your target / desired number (used when a number is forced): $____
- Note: your *screening floor* and the *number you enter* are different questions — the floor
  decides whether to apply at all; the entered number is what a mandatory field gets.

## D. Location & relocation
- Home metro: ____
- Eligible work locations — the list you'd accept without relocating (e.g. remote-in-[state],
  plus named metros): ____
- Remote / hybrid / onsite preference: ____
- Relocation rule ▶ default: on a multi-select "which of these locations work for you?" answer
  **Yes if ANY location on your eligible list appears** — don't require all of them.

## E. Screening & logistics
*(Common one-line screening questions. Set them once.)*

- Current / most-recent salary (if you're willing to state it; else leave blank to be asked): ____
- Security clearance (None / Active / Eligible + type): ____
- Are you 18 or older? ▶ default: Yes → ____
- Reason for leaving / seeking a new role (one standing sentence): ____
- Available start date: ____
- Notice period: ____
- Were you referred? ▶ default: No → ____
- Have you previously applied to / worked for this company? ▶ default: No (the skill's dedupe
  tracks real history separately) → ____
- Any government / political-office / conflict-of-interest disclosures? ▶ default: No → ____
- Do you require accommodation for the hiring process? ▶ default: No → ____

## F. Restrictive covenants
- Are you subject to a non-compete or non-solicit agreement? ▶ default: No → ____

## G. Background check / consumer report consent
*(Kept deliberately conservative — this authorizes someone to pull records on you.)*

- ▶ default: **do not auto-consent.** When a form bundles a background-check / credit /
  consumer-report authorization, the skill **parks it for you** rather than ticking it. Override
  only if you want it auto-authorized (state that here): ____

## H. Consents *(standing checkboxes)*
*(These recur on almost every form. Recommended standing answer is Yes for the routine ones.)*

- SMS / text-updates consent ▶ default: Yes → ____
- Privacy policy / data-processing notice ▶ default: Yes → ____
- Arbitration agreement ▶ default: Yes → ____
- Accuracy certification ("I certify the information is true and complete") ▶ default: Yes → ____
- ⚠️ **Scope caveat (always on):** if a consent **bundles extra scope** — marketing, third-party
  data-sharing, a background/credit-check authorization, or broad legal terms beyond the
  application — that extra scope is **never** covered by the defaults above. The skill parks it
  for you regardless of what you set here.

## I. AI-tool-use questions
*(Some forms ask whether you'll use AI tools. What the question **governs** decides the answer.)*

- ▶ default stance: read the **scope**. If a policy bans AI tools **in the application itself**
  (or asks you to certify a human filled the form), the skill **declines/parks** — it will not
  falsely attest. If the restriction applies only to the **interview or the job**, that's a
  normal question you can answer. Any "type X if you are AI / certify a human completed this"
  trap is always left for you. Adjust only if you want a different stance: ____

## J. Voluntary self-identification / demographics
- ▶ default: **decline / "prefer not to say" / leave blank** on all of: gender, gender identity,
  race/ethnicity, veteran status, disability status, LGBTQ+. Override only if you want these
  filled: ____

## K. Experience & employment framing
- Total years of relevant experience (and the basis, e.g. "PM since 2018"): ____
- Anything about how to frame your current employment (e.g. still employed, title nuances): ____

## L. Education
*(Exact dates matter — background checks verify them.)*

- Degree(s), institution(s), and start/end dates: ____

## M. Reusable long answers *(optional — these accumulate over time)*
*(Leave blank now. The skill saves each essay-style answer you approve so the next matching
question reuses it. If you already have polished STAR stories, seed them here:)*

- ____

## N. NEVER-CLAIM list *(important)*
*(Skills, tools, domains, or titles you must **never** be described as having — even if a résumé
draft or a form answer drifts toward implying them. This is a safety guard: the skill refuses to
submit anything asserting these.)*

- ____

## O. Résumé variants
- Which résumé files / domain variants do you have, and where do they live? (drives
  `resume_routing.md`): ____
- If you only have one résumé, that's fine — it becomes the default for everything.

---

### When you're done
Hand this back to the skill (or to Claude) and say **"set up my profile from this intake."** It
will populate `profile/answer_bank.md` and `profile/candidate_profile.json` from your answers,
leave every blank as a "stop and ask," and confirm the result — no application is ever submitted
during setup.
