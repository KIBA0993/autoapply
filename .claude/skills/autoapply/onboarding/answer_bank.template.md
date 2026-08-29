# Answer Bank

**Every answer confirmed by the user, in one place.** Read this before filling any form. If a
question isn't here, ask — don't infer.

<!-- STARTER TEMPLATE. Copy to profile/answer_bank.md and fill from onboarding/intake.md.
     Replace every <…> placeholder. Delete a row you can't answer yet — a missing row becomes a
     "stop and ask", which is the safe default. Never put a guess here. -->

## Identity & contact
| Question | Answer |
|---|---|
| First / Last name *(legal — use on legal-name & background-check fields)* | **<first>** / **<last>** |
| Preferred name *(only where the form has its own field)* | **<preferred, or same as legal>** |
| Email | `<email>` |
| Phone | `<phone>` |
| LinkedIn | `<url>` |
| Website / Portfolio | `<url>` |
| GitHub *(only where a separate GitHub field exists)* | `<url or "none">` |
| Pronouns | **<pronouns>** |
| Street address | **<street>** |
| Zip code | **<zip>** |
| City of residence | **<city>** |
| State | **<state>** |
| Country | **<country>** |
| US time zone | **<tz>** |

## Work authorization — both questions, both clean
| Question | Answer |
|---|---|
| "Are you legally authorized to work in the United States?" | **<Yes/No>** |
| "Will you now or in the future require visa sponsorship?" | **<No/Yes>** |
| Citizenship status | **<Citizen / Permanent resident / Temporary visa / …>** |

Free-text variant: *"<one-sentence authorization statement>"*
⚠️ These are **different questions** and both usually appear. Never map one onto the other.

## Restrictive covenants — non-compete / non-solicit
| Question | Answer |
|---|---|
| Subject to a non-compete or non-solicit? | **<No/Yes + detail>** |

## Background check / consumer report / employer contact
Standing default: **do not auto-authorize** a background/credit/consumer-report check — park it
for the user. *(Change this line only if the user opts into auto-authorization.)*

## Compensation
**Screening a posting:** qualifies if the published **upper** band ≥ **$<floor>**. Ignore the lower band.

**Answering a form:** ▶ defer wherever the field takes text ("open / flexible / market"); enter
**$<target>** only where a number is mandatory.

**Screening threshold is separate from the fill number:** a posting qualifies to apply once its
ceiling ≥ $<floor> (the screening minimum) — only a ceiling **< $<floor>** is a hard skip.
Qualifying-to-apply and what-number-to-enter are two different questions.

## Location & relocation
Home metro: **<metro>**. Eligible locations: **<list>**. Remote/hybrid/onsite: **<pref>**.
**Answer Yes if ANY listed location is on the eligible list** on a multi-select location question.

## Screening & logistics
| Question | Answer |
|---|---|
| Current / most-recent salary | **<amount or "prefer to ask">** |
| Security clearance | **<None/Active + type>** |
| 18 or older? | **<Yes>** |
| Reason for leaving / seeking new role | *<one standing sentence>* |
| Available start date | **<date/notice>** |
| Referred? | **<No/Yes>** |
| Previously applied / worked here? | **<No>** |
| Government / COI disclosures? | **<No>** |
| Accommodation needed? | **<No>** |

### Degree dates
<Degree — Institution — start → end>, one line each. *(Exact dates; background checks verify.)*

## Voluntary self-identification
**Decline / "Prefer not to say" / leave blank** on all: gender, gender identity, race/ethnicity,
Hispanic-Latino, veteran status, disability status, LGBTQ+. *(Change only if the user opts in.)*

## AI tool use
Read *what* the AI policy governs. **Application-level ban** (or "certify a human filled this") →
decline/park, never falsely attest. **Interview-/job-level only** → answerable normally. Any
AI-vs-human trap field → leave for the user.

## Consents
Standing default **Yes / Confirmed** for the routine, recurring ones: **SMS**, **privacy policy /
data-processing notice**, **arbitration agreement**, **accuracy certification**.
**Scope caveat:** if a consent bundles extra scope (marketing, third-party data-sharing, a
background/credit-check authorization, broad legal terms beyond the application), that extra
scope is **not** covered — stop and park it.

# Reusable long answers
*(Empty at start. Each essay-style answer the user approves is saved here so the next matching
question reuses it verbatim. Add a `## "<the question>"` heading + the approved answer as they
accumulate.)*

## "Why [company]?"
**Never reuse verbatim.** Generate per company via `playbooks/why-this-company.md`, then gate
with `tools/check_freetext.py` (clean → may auto-send; any hit → park).

# ⚠️ NEVER CLAIM — confirmed false
*(Skills, tools, domains, or titles the candidate must never be described as having. The skill
refuses to submit anything asserting these. One per line.)*
- <term>

# Still unanswered
*(Questions seen on forms but not yet confirmed by the user — surfaced here so they get resolved,
never guessed.)*
