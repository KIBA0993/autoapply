# Ashby

**Coverage: moderate.** No account required, but the DOM is hostile to selectors.

## Recognizing it

- `jobs.ashbyhq.com/{company}/{uuid}`
- Also embedded on company sites; the embedded version behaves the same.

## Why it's harder

Ashby is a React app with generated class names and **no stable ids or `name` attributes**. Selector-based automation breaks constantly.

**Enumerate with `tools/browser_fill.js`, not a selector map.** Inject it once after the form expands (it defines `window.aa`); `aa.inventory()` returns `{ref, label, type, required, value}` for every field — traversing shadow DOM and stamping a stable `data-aa-ref` on each — for ~300 tokens instead of a ~12.5k full-tree `read_page`. Drive plain fields with `aa.fill(ref, value)` and verify with `aa.verify()`. The stamped ref is a durable handle even though Ashby has no ids of its own. (Its comboboxes still need the documented open→click method — see below — and `read_page`/`find` remains the fallback if `inventory()` misses a control.)

## Flow

1. The posting page shows an **"Apply for this Job"** button that expands the form inline (or routes to `/application`). The form is not present in the DOM until then — read the page again after clicking.
2. Fields render as label + control pairs. Match on the label string.
3. Resume upload accepts drag-drop or a file picker button. After upload Ashby may parse and pre-fill — diff against `candidate_profile.json` as with Lever.
4. Submit button is at the form's end, label "Submit Application".

## Known friction

- **Custom dropdowns are not `<select>`.** They are div-based comboboxes. Setting a value programmatically does nothing. Click to open → click the option.
- Multi-select fields (e.g. "How did you hear about us") need one click per value plus a click outside to close.
- Some fields validate only on blur — after typing, move focus before reading the error state.
- File upload confirmation is a small filename chip; verify it before submitting.

## Token discipline — inventory once, verify targeted

- **`aa.inventory()` once, after the form expands.** That single call is the enumeration —
  cache the returned `ref`s; don't re-run it or `read_page` the whole form between fields.
  It won't silently truncate the way a `max_chars`-capped tree read does (the old
  "submits blank" failure), because it returns structured records, not a token-bounded dump.
- **Verify with `aa.verify()`** — four-layer, problems-only, ~300 tokens. If you must fall
  back to `read_page` for a control inventory missed, read only that field's `ref_id`, never
  a full re-dump.
- Résumé pre-fill parsing: diff against `profile_get.py` fields, not a reload of the
  whole `candidate_profile.json`.

## Notes

- Low but nonzero rate of Cloudflare interstitials on high-traffic postings → hand off, don't attempt.
- No account creation.
