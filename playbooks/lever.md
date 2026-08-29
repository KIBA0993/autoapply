# Lever

**Coverage: good.** Single-page form, no account required.

## Recognizing it

- `jobs.lever.co/{company}/{uuid}` — posting
- `jobs.lever.co/{company}/{uuid}/apply` — form (navigate straight here)

## Field map

Lever uses `name` attributes, not ids.

| Field | Selector |
|---|---|
| Full name | `input[name="name"]` (one field, not first/last) |
| Email | `input[name="email"]` |
| Phone | `input[name="phone"]` |
| Current company | `input[name="org"]` |
| LinkedIn | `input[name="urls[LinkedIn]"]` |
| GitHub | `input[name="urls[GitHub]"]` |
| Portfolio | `input[name="urls[Portfolio]"]` |
| Resume | `input[name="resume"]` |
| Custom questions | `cards[{uuid}][{field}]` |
| Submit | `button[type=submit]`, "Submit application" |

## Upload resume FIRST — ordering matters

Lever parses the uploaded resume server-side and **auto-fills name, email, phone, and company from it**. If you fill those fields first and then upload, the parse overwrites your values several seconds later, silently.

Correct order:
1. Upload resume
2. Wait for the parse to settle (spinner clears, fields populate)
3. Diff every populated field against `candidate_profile.json`
4. Correct anything the parser got wrong
5. Fill the remainder

Parse errors are common with multi-column resume layouts — phone numbers pick up stray characters, company picks up the wrong employer.

## Notes

- Custom question `name` attributes contain per-posting UUIDs, so they can't be hardcoded. Locate by visible label text.
- Some postings gate on a "Additional information" textarea — treat as a custom question, draft from the answer bank.
- No account creation. No CAPTCHA in the common path.
