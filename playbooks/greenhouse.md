# Greenhouse

**Coverage: good.** Short forms, no account required, stable DOM. Highest-yield target.

## Recognizing it

- `job-boards.greenhouse.io/{company}/jobs/{id}` — current
- `boards.greenhouse.io/{company}/jobs/{id}` — legacy, still live
- Embedded on company career pages inside `#grnhse_app` (an iframe). If the apply form is in an iframe, operate on the iframe URL directly — open `job-boards.greenhouse.io/{company}/jobs/{id}` in its own tab instead of fighting the frame.

## Enumerating a board

The rendered board page lazy-loads — a DOM scrape of `job-boards.greenhouse.io/{company}` returns only the first chunk. Affirm's 175-role board yielded zero Product hits by DOM scrape and six by this method:

```js
fetch(`/embed/job_board?for={company}&page=${n}`)  // loop n until non-OK or empty
```

Parse each page with `DOMParser` and match on link text. Run it from the board's own origin so it's same-origin.

Stale job IDs redirect to the board index (sometimes with `?error=true`) rather than 404ing — so **always check `location.href` after navigating.** A page that looks like a board listing when you expected a posting means that posting is gone.

## Field map

| Field | Selector |
|---|---|
| First name | `#first_name` |
| Last name | `#last_name` |
| Email | `#email` |
| Phone | `#phone` |
| Resume | `input[type=file]` behind the "Attach" button |
| Custom questions | `#question_{id}` |
| Submit | `#submit_app`, label "Submit Application" |

## Filling react-select dropdowns — the method that works

**Solved 2026-07-22 after failing every other way.** Requires real Chrome with a live viewport (`mcp__claude-in-chrome__*`), not the in-app browser.

```
1. JS: document.getElementById(fieldId).focus()      ← focus programmatically
2. computer{action:"type", text:"Yes"}               ← REAL keystrokes, not synthetic
3. computer{action:"key", text:"Return"}             ← commits the highlighted option
4. JS: read .select__single-value to verify          ← always verify; silent no-op is the failure mode
```

Why it works: react-select ignores programmatic `.value` and synthetic events, but responds to real key events once the input has focus. JS handles focus (reliable), the computer tool handles typing (trusted events).

**When the option wording is unpredictable, click instead of typing.** Decline options are worded differently on the same form:

| Field | Decline wording |
|---|---|
| Gender / Hispanic-Latino | "Decline To Self Identify" |
| Veteran Status | "I don't wish to answer" |
| Disability Status | "I do not want to answer" |

Typing a guess fails silently. Open the menu, then **read the real option text with a scoped `javascript_tool` query — not a screenshot.** A screenshot is an image that persists in context and is re-billed as image tokens on every later turn of the form (the costliest thing to leave resident); the option strings are plain DOM text:

```js
// scoped to THIS field's menu — avoids the 246-option phone-selector swamp below
[...document.querySelectorAll('.select__container .select__option, [role=option]')]
  .map(o => o.textContent.trim())
```

Match the decline string from the table, then click that option by its `ref` (`find` → `computer{left_click, ref}`), not by coordinate. Reserve `screenshot` for genuine non-DOM visual state only. If the scoped query returns nothing (menu rendered outside the container), fall back to a screenshot for that one field.

**Two traps:**

- A stale open menu poisons `document.querySelectorAll('[role=option]')` — the phone-country selector has ~246 options and will swamp your query. Scope to the field's own `.select__container`, or press Escape first.
- Do the fields **one per tool call**. Batching several opens leaves multiple menus mounted and the wrong option gets selected.

## Custom-question dropdowns need a visible viewport

Greenhouse renders `question_*` selects as React comboboxes, not `<select>`. Options live in a portal that mounts **only after a click, and only when the page has real layout.**

If the browser pane is collapsed (`window.innerWidth === 0`), the popover never mounts: the click fires, `[role=option]` stays empty, and nothing errors. Setting `.value` directly does nothing either — React ignores it and the form submits blank.

Check the viewport before attempting any dropdown:

```js
window.innerWidth === 0  // → dropdowns are unfillable; ask the user to open the pane
```

Options also render asynchronously — poll or wait ~400ms after the click before querying. And fill **one dropdown per tool call**; chaining several opens in one async batch leaves multiple listboxes mounted at once, and `[role=option]` then returns a merged set from all of them, which silently selects the wrong value.

Plain text inputs (`first_name`, `email`, `phone`, and text-type `question_*`) have none of these problems — the native-setter + `input`/`change` dispatch works with the pane collapsed.

## The location trap

The location field is an **autocomplete, not a text input**. Typing a value that looks correct leaves the underlying hidden field empty, and submit fails validation with no visible error near the field.

Always: type 2–3 characters → wait for the dropdown → click an actual option → verify the input shows the canonical string (e.g. `New York, NY, United States`).

This is the single most common silent failure on Greenhouse. If a submit "does nothing," check this first.

## Resume upload

Three tabs: **Attach / Dropbox / Enter manually**. Use Attach. The visible button is a label; the real `input[type=file]` is hidden. After upload, confirm the filename renders next to the field before continuing — a failed upload shows no error.

## Demographic questions

Rendered as a separate block near the bottom, usually optional. Every select has a decline option ("Decline to self identify", "I don't wish to answer"). Per `application_rules.md`, choose decline unless the profile says otherwise.

## Token-cheap verification — four layers, one read

Greenhouse has stable ids, so you never need a full-tree `read_page` (up to ~12.5k
tokens) to check your work. Inject `tools/browser_fill.js` **once per tab** (it defines
`window.aa` and returns a readiness line), then verify with one call that checks all four
silent-failure modes at once — value readback, HTML5 `checkValidity()`, ARIA
`aria-invalid`, and any adjacent error banner — and returns **only the problems**:

```js
JSON.stringify(aa.verify())
// → {ok: N, problems: [{ref, label, value, issues:["required-empty"|"invalid:…"|"aria-invalid"|"error:…"]}], formValid, banners}
```

An empty `problems` array with `formValid: true` is the green light. Any issue is the
silent no-op — fix that one field and re-run only this check. This beats reading values
back by hand: it reads react-select display values (not the empty inner input), and its
`invalid`/`error` layers catch the **location-autocomplete** and **viewport-collapse**
traps below, which a value-only read misses. Do **not** screenshot or re-`read_page` the
whole form to verify.

## The Country/Phone stale-validation trap — root cause of "silent" submit failures

Confirmed 2026-08-16 (Apollo.io, BitGo, Customer.io — all showed the identical symptom).
When the phone-number widget's Country combobox is filled programmatically (native-setter
`fill()`, or a fill that happened long enough ago that the tab's React state drifted),
`aa.verify()` shows both the Country combobox and the Phone field with `aria-invalid` plus
a visible red error (`"Select a country"` / `"Phone is required."`) **even though the
displayed values are correct** (`+1`, the full phone number) and `formValid: true`. The
Submit button stays enabled and clickable — but clicking it produces **zero network
activity, no banner, no navigation.** This is exactly the "silent no-op" failure mode
`aa.verify()`'s four layers exist to catch, but it only shows up on fields that were
*already* filled — always re-run `aa.verify()` right before Submit, not just after the
initial fill pass.

Fix: real-keyboard retype, same recipe as the Ashby stale-error pattern —
1. Click the Country combobox, `cmd+a`, type `United States`, then click the dropdown
   option that appears (`United States +1`) — do not press Enter blind; take a screenshot
   first if unsure of the option's position, since a same-frame `find()` ref race can
   click the wrong row.
2. Click the Phone field, `cmd+a`, retype the digits (the candidate's phone, no country code —
   the widget prepends it).
3. Re-run `aa.verify()`. The Country error clears immediately. The Phone `aria-invalid`
   error can persist **visually** even after a correct retype and blur — this is now known
   to be cosmetic (the same class of stale-UI-text bug seen on Ashby): Submit anyway and
   confirm via `document.title`/`location.href` turning into `/confirmation` +
   "Thank you for applying". Don't loop trying to clear it further.

If a Greenhouse form has sat open across multiple earlier submit attempts in one session,
check this **before** re-clicking Submit — it is cheaper than another blind retry.

## Notes

- Some boards run invisible reCAPTCHA v3 (no interaction). If a visible challenge appears → hand off, don't solve.
- No account creation. No login. This is why Greenhouse is the priority board.
- Cover letter is usually optional; skip in Volume mode.
