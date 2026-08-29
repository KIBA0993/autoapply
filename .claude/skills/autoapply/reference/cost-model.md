# Cost model — the mechanics behind the rules

The one-paragraph version lives in `SKILL.md`. This file is the full derivation and the
measured evidence. Load it only when tuning cost; the actionable rules are already inline.

## The driver: cost ≈ prefix size × round-trips

Cache-read dominates every bill (94–99% of tokens on real runs). The model re-reads the
whole cached prefix on **every** turn, so the total is roughly **prefix size × number of
round-trips**. Output tokens are a rounding error by comparison (all three sessions of the
Aug 21–24 2026 run produced ~845k output total — ~$13 — against ~209M cache-read).

**There is no >200k "long-context premium" on the current models.** Earlier notes in this
skill claimed a 2× surcharge past 200k context and a "~$4 premium" — that was the pricing of
the **older Sonnet 4.x 1M-context beta** and does **not** apply to claude-sonnet-5 /
opus-4.x, which bill flat regardless of prefix size. So the reason to bound context is **not**
a price cliff — it is simply that a bigger prefix costs proportionally more on every one of
the many turns. Bounding context and cutting turns are the same lever from two directions.

Measured baselines (flat-rate, no premium): a 10-form batch (2026-08-05) ~$46, ~87%
cache-read; a 570-turn Sonnet-5 apply run (2026-08-23) $55, 98.6% cache-read, 142M cache-read
over a prefix that grew 71k → 432k; a bounded 105-turn run (2026-08-24) only $9, never a
problem. The difference between the last two is **turn count and prefix growth**, not model or
work done.

## Lever 1 — cut round-trips, especially tool-less turns (the biggest lever)

Every turn re-bills the whole prefix, so the cheapest turn is the one you don't take. On the
$55 run, **280 of 570 turns had no tool call at all** — pure reasoning/status narration — and
they cost ~$21, the single largest slice of the bill.

- **Don't emit tool-less narration turns.** Think, then act in the same turn. A running
  commentary between tool calls ("Now I'll check the next row…", "That looks good, moving
  on…") is pure re-bill for zero work. Keep status terse and attached to a turn that also does
  something.
- In a **conductor/worker** run, the conductor should speak only to dispatch, to record a
  receipt outcome, and to give the end-of-run report — not to narrate each dispatch.
- Run the conductor at **lower reasoning effort** for the mechanical dispatch loop; the
  judgment already lives in the worker contract and the fail-closed gates.

## Lever 2 — keep the prefix from growing (pointer-style dispatch)

The conductor's prefix grew 71k → 432k across the run largely because **44 full worker
dispatch prompts** accumulated in its permanent history — each one re-billed on every later
turn.

- **Dispatch a pointer, not a restatement.** The worker contract is `mode_b_worker.md`, read
  once by the worker itself. The conductor's per-job message should carry only the **delta** —
  `{seq, url, company, title, ats}` plus the frozen verdict — not a re-stated copy of the
  contract each time. A stable one-line "follow mode_b_worker.md for job N" keeps the
  conductor's growth slope flat.
- Extract what you need from any large tool result (board dump, DOM tree, JD body) and never
  let the raw blob persist — see Lever 4.

## Lever 3 — don't let waits expire the prompt cache; don't poll

The prompt cache has a **~5-minute TTL**. On the $55 run, **51 turns were pure poll-waits**
(waking to check whether the async sweep / a worker had finished), and gaps longer than 5 min
expired the cache **23 times**, forcing ~$6 of cache **re-writes** on top of the ~$4 the poll
turns themselves cost.

- **Block on subagent completion** instead of waking repeatedly to check it. The harness
  re-invokes you when tracked background work finishes — you don't need to poll for it.
- If you must wait on something external (a long Workday sweep), prefer **one longer wait**
  over many short ones, and try to keep it inside the cache window or accept a single re-cache
  rather than many.

## Lever 4 — a big blob in context is billed on every later turn, not once

One stray 12.5k full-tree `read_page`, left in context across a few hundred subsequent calls,
costs ~$1 by itself. One long **un-segmented** session is the classic leak: form #10 re-reads
the accumulated context of forms #1–9 on every call (a 2026-08-17 run: 1,763 turns, 791M
cache-read, ~$237, median context 467k). The conductor/worker split exists to eliminate
exactly this — the worker's DOM/JD/screenshots die with it, so nothing accumulates.

- Extract what you need with a script/JS and never let the raw dump persist.
- **Delegate any read-heavy exploration to a subagent** (sweeping files, greping the repo,
  enumerating a corpus, reading several playbooks for one answer) so its churn runs on its own
  lean prefix and only a bounded summary returns. The live PII fill stays in the main loop
  (a subagent can't see consent) — the sole exception being a dispatched Mode B worker.
- **Bound what a subagent returns** — its return also persists and re-bills. The find/screen
  agent returns **one line per candidate** (company, title, url, ats, fit-tier,
  location+freshness bands, dedupe verdict), no JD bodies. The factual-audit reviewer returns
  **only** its verdict + any exact line changes, never its reasoning. Bound prose, never
  substance: a safety-relevant finding always returns in full.

## Lever 5 — load only the current phase's files, and don't re-read your own writes

- Load only what the phase needs (see the SKILL.md "Load first" table); don't pull a file a
  later phase needs, or the whole 3.7k-token JSON when one field via `profile_get.py` will do.
- **Don't re-read your own `Edit`/`Write` to "verify"** — the harness tracks file state, so a
  confirming re-read is pure re-bill. (Do re-read when something *else* may have changed the
  file — a shell `sed`/redirect, a build step, an external process, an iCloud sync.)
- **Batch independent calls** into one turn — `browser_batch` for independent browser ops,
  the batched `profile_get.py` multi-path call, `dedupe_check.py --batch`. Every avoided
  round-trip removes one full prefix re-read. (Dropdowns stay one-per-call for correctness.)

## `/clear` orphans open browser tabs — the hard sequencing rule

`/clear` destroys this conversation's MCP tab-group ownership (verified 2026-08-05). A
post-`/clear` session owns no group, can't drive the prepared tabs by their old IDs, and
"re-attaching" means *navigating* a fresh tab to the URL — which reloads the page and **wipes
the filled form state**. So:

- **Only `/clear` after every tab in the batch is submitted or closed.** Never with a
  prepared-but-unsubmitted form still open — you will lose the fill. `job_pool.csv` saves
  *status*, not field values.
- **Mode A** (you're present): checkpoint status to `job_pool.csv`, then `/clear` at a form
  boundary to cap prefix growth between segments.
- **Mode B** (unattended): a `/clear` **ends the authorization** and no one is present to
  re-kick, so **never `/clear` mid-batch**. Instead the kickoff sizes the frozen set to one
  segment, and a large run (up to ~30) uses the conductor/worker split so no single context
  accumulates.

## Environment floor — the fixed cost before any conversation

The prefix carries tool schemas + the installed-skill catalog, re-read every turn. MCP tool
schemas are **deferred** (loaded via ToolSearch only when used), so they cost ~nothing until
called. The residual floor is the **skill catalog** (every installed skill's name +
description). An autoapply session needs only `autoapply`; other installed suites (`gstack`,
`money-*`, `anthropic-skills`) sit in the prefix every turn. Trimming them is a **user/global
choice** with cross-project impact — this skill must not disable another workflow's tools — so
it's surfaced to the user, not changed here. For autoapply-heavy sessions, disabling the
unused suites is the one persistent floor cut that pays out every turn.
