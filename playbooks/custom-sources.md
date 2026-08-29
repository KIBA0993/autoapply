# Custom lead sources — companies not on Greenhouse / Ashby / Lever

Phase 1's default sources are the three public ATS APIs. Many prestige/big-tech firms and
some unicorns run their own careers backend instead. This playbook adds them as **lead
sources**. For every source here the **apply is account-gated (Tier 4 → user hand-off)** —
surface the role, prepare what doesn't need the account, hand the submit to the user. See
`playbooks/workday.md` for the apply wizard.

The registry `sources/registry.json` is the source of truth. Two adapter types.

## Type 1 — Workday (curl-friendly, one adapter for all tenants)

A huge share of enterprises run Workday, and every tenant exposes the same JSON search
endpoint. Driven by `tools/fetch_workday.py`:

```bash
python tools/fetch_workday.py --host {tenant}.{wdN}.myworkdayjobs.com \
    --tenant {tenant} --site {SiteName} --q "product manager" --limit 50
```

Emits JSONL: `company, title, location, posted_days, req_id, url`. `posted_days` feeds the
Phase-2 freshness banding directly. Verified live 2026-08-05 against NVIDIA.

**Discovering host / tenant / site (never guess — the shard and site name are per-company).**
Open the company's careers page and read the URL:

```
https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/...
        └tenant┘ └dc┘                  └──── site ────────┘
```

`host = nvidia.wd5.myworkdayjobs.com`, `tenant = nvidia`, `site = NVIDIAExternalCareerSite`.
The `wdN` datacenter (wd1/wd3/wd5/wd12…) is fixed per tenant — take it from the real URL,
do not try shards blindly. Add the verified triple to `registry.json` with `"apply":"handoff"`.

## Type 1b — SmartRecruiters (public postings API, one adapter for all)

Another public JSON ATS, driven by `tools/fetch_smartrecruiters.py`:

```bash
python tools/fetch_smartrecruiters.py --company {Company} --q "Product Manager|Program Manager" --days 3
```

`--company` is the case-sensitive company id straight from the careers URL
(`jobs.smartrecruiters.com/{Company}/{id}`). Emits `company, title, location, posted_days,
req_id, url` as JSONL; `--days` applies the recency window inline (on `releasedDate`, the
true post date). Verified live 2026-08-05 against Visa. SmartRecruiters skews to large
regulated-finance/payments enterprises — good for the specialist risk/identity roles there,
but mind the positioning caveat on big-company generalist reqs. Apply is the
SmartRecruiters-hosted page → drive in browser, submit stays the user's (`"apply":"browser"`).

## Type 1c — Recruitee & Breezy HR (public board JSON, discovery-seeded)

Two more no-auth public JSON boards, one request each, one adapter per platform:

```bash
python tools/fetch_recruitee.py --slug {slug} --q "Product Manager|Program Manager" --days 7  # {slug}.recruitee.com/api/offers/
python tools/fetch_breezy.py    --slug {slug} --q "Product Manager|Program Manager" --days 7  # {slug}.breezy.hr/json
```

Both emit the standard `ats, company, title, location, posted_days, req_id, url` JSONL.
Recruitee (`published_at`, verified 2026-08-06 against channable) skews SMB / European
scaleups and emits only `status==published`. Breezy (`published_date`, verified 2026-08-06)
skews SMB / early-stage startups; its documented API needs a token but the public
`{slug}.breezy.hr/json` board is unauthenticated. **Neither has an open slug corpus**, so
both are discovery-seeded like SmartRecruiters — take the slug from the company's careers
subdomain, run once, verify real rows before adding to the registry. No ETag on either, so
they don't get the `delta_sweep.py` 304 shortcut. Apply pages are platform-hosted → drive
in browser, submit stays the user's.

## Type 2 — custom_browser (the company API blocks non-browser clients)

Some custom career APIs reject plain HTTP clients (TLS/anti-bot). **Microsoft is the
verified example**: `gcsservices.careers.microsoft.com/...` returns HTTP 000 to curl, but
`careers.microsoft.com` loads fine in a real browser. So enumerate through **claude-in-chrome**,
never curl. Two ways, cheapest first:

1. **In-page fetch** — from the careers-site tab (correct origin/cookies/TLS), run the site's
   own search API via `javascript_tool`; you get structured JSON back without a full DOM dump:
   ```js
   // executed in the careers.microsoft.com tab context
   const r = await fetch('https://gcsservices.careers.microsoft.com/search/api/v1/search?q=product%20manager&pg=1&pgSz=20&o=Relevance', {headers:{Accept:'application/json'}});
   const d = await r.json();
   const res = d.operationResult.result;
   res.jobs.slice(0,20).map(j => ({title:j.title, loc:(j.properties||{}).primaryLocation, id:j.jobId}));
   ```
   Field names drift — if the shape changed, read one raw record first and adjust.
2. **Rendered read** — open the board URL from `registry.json`, let it render, and read the
   results list (structured browser read, targeted subtree; never blind-cap max_chars).

Detail/apply URL for a Microsoft req id: `https://jobs.careers.microsoft.com/global/en/job/{jobId}`.

## Adding a company to the registry

1. Confirm it is **not** already on Greenhouse/Ashby/Lever (prefer those — no hand-off).
2. Find its live careers URL. Workday URL → Type 1 triple. Otherwise → Type 2 (`board` +
   `api` if it has one).
3. **Verify before writing it down** — run the adapter (or an in-page fetch) once and see
   real rows. A guessed tenant/endpoint becomes a dead link on a real run.
4. Add the entry with `"apply":"handoff"` and a dated `"verified"`.

## Strategy note

Prestige/big-tech reqs (Microsoft, and most FAANG) are **off the positioning strategy** in
`application_rules.md`: the generalist PM loses the final round to a specialist. These
sources exist because the user asked for reach; surface them, but do not let them crowd out
the winnable specialist reqs (identity/fraud/fintech) that fit-first ordering should rank
above them anyway.
