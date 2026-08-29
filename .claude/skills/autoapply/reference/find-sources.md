# Phase 1 — source recipes (the full connector catalog)

`SKILL.md` Phase 1 carries the decision rules (scan boards not web search; any recency-refresh
→ full-corpus delta sweep; background+redirect; enumerate once; dedupe). This file is the
operational detail: the exact APIs, the delta engine, and every connector.

## Best method — public ATS JSON APIs (no browser)

Scanned 83 companies in one pass this way:
```
https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
https://api.ashbyhq.com/posting-api/job-board/{slug}
https://api.lever.co/v0/postings/{slug}?mode=json
```
Slug is usually the lowercase company name, punctuation stripped — try `name`, `nopunct`, and
`hyphenated` variants. Run them concurrently. These return title, location, and URL as
structured JSON, which beats scraping and beats search by a wide margin. Locations a board
index leaves blank come back populated here.

## The delta engine (recency-refresh over the full corpus)

Map the window from `application_rules.md` → Search window: 24h → `--days 1`, 3d → `--days 3`,
7d → `--days 7`, `all` → omit `--days`.
```bash
python tools/delta_sweep.py --companies sources/companies.json --title 'Product Manager|Program Manager' --days 1
```
The **only** time to skip the corpus is when the user names specific companies ("check Stripe
and Ramp") — then scan just those. Also run `tools/sweep_workday.py --companies
sources/workday_companies.json --days N` for the enterprise (Workday) slice the delta engine
can't reach.

**Run a corpus-scale sweep in the background, redirected to a file** — two mandatory rules for
`delta_sweep.py` and `sweep_workday.py`:

- **Background, not foreground.** The full Workday sweep runs 15–30 min and the delta sweep
  minutes — longer than a foreground command may run before it's killed (a killed foreground
  run *looks like the tool "stopping by itself"*). Launch it detached (`run_in_background`, or
  `nohup … &`) and poll the log's summary line. The ETag cache flushes incrementally and
  atomically, so even an interrupted run keeps progress — but avoid the kill by backgrounding.
- **Redirect stdout to a file.** Both tools print one JSON line per posting; a baseline or wide
  `--days` run emits thousands (the summary goes to stderr, safe to read). Always `>
  sources/sweep.jsonl`, then pull only the count + a deduped top-N into context.
```bash
nohup python tools/delta_sweep.py --companies sources/companies.json --title 'Product Manager|Program Manager' --days 3 > sources/sweep.jsonl 2> sources/sweep.log &
tail -1 sources/sweep.log                                   # summary prints on completion; do not cat the .jsonl
printf 'greenhouse\tslug\tid\n' | python tools/dedupe_check.py  # feed sweep.jsonl rows through dedupe; keep only NEW, ranked top-N
```

**How the delta engine stays cheap.** `delta_sweep.py` sends each board its stored ETag as
`If-None-Match`; unchanged boards reply **HTTP 304, 0 bytes** and are skipped — so after a
one-time baseline, a daily "scan everything" run is mostly cheap 304s (GH/Ashby/Lever all honor
conditional GETs). It emits `ats/company/title/location/posted_days/req_id/url` JSONL for
postings on **changed** boards only; the job-level "already seen" diff is then `dedupe_check.py`
(vs `job_pool.csv`) and closures are caught by `liveness_check.py`. ETag state persists in
`sources/etag_cache.json` (gitignored). Supports greenhouse/ashby/lever; Workday/SmartRecruiters
use their own `fetch_*` adapters.

## Token discipline for the find phase (a board can return hundreds of postings)

- **Never read a raw board dump into context.** Filter first, in the shell, pull in only the
  matching rows. e.g. Greenhouse:
  ```bash
  curl -s https://boards-api.greenhouse.io/v1/boards/{slug}/jobs \
    | jq -r '.jobs[] | select(.title|test("Product Manager|Program Manager";"i")) | [.title, .location.name, (.absolute_url)] | @tsv'
  ```
  A 200-role board collapses to the ~handful of PM rows (~hundreds of tokens vs. tens of thousands).
- **Apply the search window** (`application_rules.md` → Search window). Unless `all`, filter by
  first-posted date so a daily refresh surfaces only *new* postings — `tools/filter_recent.py`
  does title + recency in one pass on each ATS's true post-date field
  (`first_published`/`publishedAt`/`createdAt`; Workday via `posted_days`):
  ```bash
  curl -s https://boards-api.greenhouse.io/v1/boards/{slug}/jobs \
    | python tools/filter_recent.py --ats greenhouse --days 3 --title 'Product Manager|Program Manager'
  ```
  Emits `title⇥location⇥url⇥posted_date⇥age_days`. Undated rows print with `?` (surfaced, not
  dropped). It's a recency *window*, not a fit filter — older roles aren't rejected, just not
  re-surfaced (they're already in `job_pool.csv`).
- **Enumerate each board once per run.** Persist filtered candidates to `job_pool.csv`
  immediately; Phase 2/3 read from that CSV. **Never re-fetch or re-scan a board already scanned
  this run** — a top token leak on a batch.
- Fetch the per-posting JD + question list (`?questions=true`) **once, up front, concurrently**
  for the whole batch — not interleaved with browser work later.

## Browser fallback, when the API has no data

| ATS | How |
|---|---|
| Greenhouse | `fetch('/embed/job_board?for={company}&page=N')` from the board origin, loop N until empty — the rendered page lazy-loads and a DOM scrape misses most roles |
| Ashby | `jobs.ashbyhq.com/{company}` renders all roles in one list; read `document.body.innerText` |
| Lever | `jobs.lever.co/{company}` is server-rendered and scrapes cleanly |

## Beyond the big three — Workday + a custom registry (`sources/registry.json`)

- **Workday** (huge enterprise share — NVIDIA/Adobe/Salesforce/Cisco/Dell class). Two modes:
  - **Broad sweep** (12,884-tenant corpus) — the Workday analogue of the delta engine:
    ```bash
    python tools/sweep_workday.py --companies sources/workday_companies.json --q manager --title 'product manager|program manager' --days 3
    ```
    Concurrent, **fail-open per tenant** (a dead site name never aborts the run). `--q` is
    Workday's server-side search (keeps each response small); `--title` adds a client-side
    regex; `--days` filters on `postedOn`. **No ETag → no 304 delta**: every run is a full fetch
    (~15–30 min for the full corpus). Recency comes from `posted_days`, not a warm cache.
  - **Single tenant** (targeted, from the registry):
    ```bash
    python tools/fetch_workday.py --host {tenant}.{wdN}.myworkdayjobs.com --tenant {tenant} --site {SiteName} --q "product manager"
    ```
  Both emit JSONL with `posted_days`. For a single tenant not yet in the corpus, discover
  host/site from its real careers URL — never guess the shard.
- **SmartRecruiters** (public postings API, no auth — enterprise regulated-finance/payments:
  Visa, banks, card networks, insurers):
  ```bash
  python tools/fetch_smartrecruiters.py --company {Company} --q "Product Manager|Program Manager" --days 3
  ```
  `--company` is the case-sensitive id from `jobs.smartrecruiters.com/{Company}/...`. Emits JSONL
  with `posted_days`; `--days` applies the recency window inline. Apply page is
  SmartRecruiters-hosted → drive in browser, submit stays the user's.
- **Recruitee** (SMB / European scaleups) and **Breezy HR** (SMB / early startups) — public
  no-auth JSON, one request per board, **discovery-seeded** (no slug corpus, so point them at a
  company slug you've found — not a bulk sweep):
  ```bash
  python tools/fetch_recruitee.py --slug {slug} --q "Product Manager|Program Manager" --days 7   # {slug}.recruitee.com
  python tools/fetch_breezy.py    --slug {slug} --q "Product Manager|Program Manager" --days 7   # {slug}.breezy.hr
  ```
  Both emit the standard JSONL with `posted_days`; no ETag. Recruitee emits only `status==published`.
- **BambooHR** (SMB) — public no-auth careers JSON, **discovery-seeded** (subdomain of
  `{slug}.bamboohr.com`):
  ```bash
  python tools/fetch_bamboohr.py --slug {slug} --q "Product Manager|Program Manager" --days 7
  ```
  `GET /careers/list` has the roles but **no date**, so the tool fetches `/careers/{id}/detail`
  per matched title for `datePosted` (boards are tiny — cheap). Emits standard JSONL with
  `posted_days`. Apply class **provisional** (no account; direct résumé-upload form filled in
  browser → one-time verify, then auto). **Trap:** the vendor BambooHR hosts its *own* jobs on
  Greenhouse (`bamboohr17`), not on a `bamboohr.com` board — don't let the name mislead slug discovery.
- **custom_browser** (e.g. Microsoft) — the company API blocks non-browser clients, so enumerate
  via claude-in-chrome, not curl. See `playbooks/custom-sources.md`.

## Cross-company remote discovery (the only ToS-clean multi-company feeds)

Every source above is per-company. `tools/fetch_remote.py` pulls the five free no-auth remote
boards (RemoteOK, Remotive, Arbeitnow, Himalayas, Jobicy) in one pass — a *discovery* layer,
**not** an apply source:
```bash
python tools/fetch_remote.py --q "Product Manager|Program Manager" --days 3
```
These are **aggregators**, so the anti-middleman rule holds: never apply through them. The tool
resolves each company against `sources/companies.json` and annotates `direct_ats`/`direct_slug`
when we already cover it — **apply via the direct connector for those**. Rows with `direct_ats:
null` are discovery-only leads: surface them, but re-verify liveness on the company's real board
before applying (aggregator listings go stale). Skews dev/remote, so PM volume is modest; value
is reach + auto-routing.

For **every** registry source the apply is account-gated → **Tier 4 hand-off**: surface the
lead, prepare what doesn't need the account, hand the submit to the user. These are also mostly
**off-strategy** (big-tech generalist reqs) — fit-first ordering should rank the winnable
specialist reqs above them; don't let reach crowd out fit. Full recipe:
`playbooks/custom-sources.md`.

Prefer the company's own board over any aggregator. Treat reposter accounts (Jobgether, Lensa,
and similar) as skips — applying through a middleman is strictly worse than applying direct.
