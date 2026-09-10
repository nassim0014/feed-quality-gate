# Improvement Backlog — feed-quality-gate

Ranked, most valuable first. One item per pull request.

Every item below is a **pure check function** plus a rule model plus tests —
the shape is identical each time, so see "Adding a check" in [`CLAUDE.md`](../CLAUDE.md)
before starting. Two standing constraints: never wire a test to real data
(fixtures are invented), and never hardcode a business column name into the
package (names come from the rules file).

Each item names the defect it exists to catch. Those defects are real and were
observed repeatedly in a production scrape pipeline before this repo existed —
they are not hypothetical.

---

## Now

### 1. `checks.per_source_completeness` — catch a single source collapsing

Group the feed by its source column (name it in the rules, don't assume it) and
flag any individual source whose missing-value rate exceeds a per-source
threshold, independently of the global rate. Report the offending source and its
rate, not just a boolean.

**Why:** a global missing-price rate of ~6% can hide one source that is missing
prices on 79% of its own catalogue. The global average is the wrong denominator:
a single collapsed source is invisible in it, and that source's products then
silently vanish from every downstream comparison. This is the highest-value
check remaining because it changes *what you can see*, not just what you reject.

### 2. `checks.stuck_value_cluster` — flag placeholder/fallback values

Within each source, flag when `min_cluster_size` or more rows share an identical
value in a column (e.g. the same price to the cent). Configurable threshold and
an optional allow-list for values that are legitimately common.

**Why:** a real feed had 13 products from one source all priced at exactly
350 TND — the signature of a scraper falling back to a page-level default when
its selector misses. Every one of those rows passes `price > 0`, passes
completeness, and poisons a margin calculation with a fabricated competitor
price. Only the *distribution* reveals it.

### 3. `checks.value_range` — absolute sanity bounds

Flag values `<= 0` and values outside a configurable `[min, max]` band, with an
offending-row sample.

**Why:** cheap, and it catches the whole-batch failures the per-row checks miss —
a currency mix-up or a decimal shift moves every row at once, so nothing looks
anomalous relative to its neighbours. Ranked below #2 because it needs a
human-chosen band per feed; ranked above the rest because it is a ~40-line
function.

### 4. `checks.non_product_row` — reject rows that were never products

A heuristic flagging rows that do not look like catalogue entries: missing price
combined with an empty, extremely long, or article-like description. Emit them
as quarantine candidates rather than hard failures.

**Why:** a blog post was ingested as a product and flowed downstream. No
value-level check catches this, because every individual field is well-formed —
the row is simply not a product. Keep it a heuristic and default it to `warn`;
a false positive here quarantines a real product, so it must not be `fail` until
tuned against a real feed.

### 5. `checks.zero_yield_source` — detect silent scraper breakage

Given the feed plus an expected-source roster passed in by the caller, flag any
expected source that contributed zero rows.

**Why:** sources go dark for unglamorous reasons — a parked domain, a site
rewritten as a JavaScript app the scraper cannot read, a B2B site with no public
prices — and a feed missing an entire source looks perfectly healthy by every
per-row measure. Note the constraint: the roster is an **argument**, not
something this package fetches. No network calls (see `CLAUDE.md` rule 5).

---

## Next

### 6. Alerting integration with de-duplication

On gate failure, emit through `astk.alerts`, keyed on `feed_id` plus the set of
failing check names, with a TTL so the same failure does not re-alert every run.
Console notifier by default; Slack when configured. Must degrade to a no-op when
`astk` is not installed.

**Why:** a stale feed stays stale for weeks. Alerting once per run turns a real
signal into noise that gets muted, and then the next genuine failure is muted
too. De-duplication is the difference between an alert that works and one that
gets filtered.

### 7. Freeze the report JSON schema

Commit a JSON Schema for `FeedReport`, validate the shape in tests, and document
the compatibility promise (additive fields only within a major version).

**Why:** the JSON report is the actual product — it is meant to be consumed by a
sync job, an Airflow task, and reporting tooling, none of which should re-derive
counts from prose. The moment a second consumer exists, an unversioned shape
becomes a breaking change waiting to happen. Do this **before** #8, not after.

### 8. A documented consumer integration

Add a worked example (`examples/` plus a README section) showing the gate run
immediately before a downstream sync: load feed → `gate()` → push `clean_df`,
write `held_df` aside, fail the task on `gate_passed == False`. Include the
`astk.db.fetch_df` source-adapter variant.

**Why:** an unused gate protects nothing. The gap between "library exists" and
"library is in the pipeline" is where this kind of tool usually dies. Depends on
#7 for a stable contract.

---

## Later

### 9. Historical quality tracking

Persist each `FeedReport` (via `astk.db`) and add trend-aware checks: a source's
completeness dropping sharply against its own trailing average, or no value
changing at all across a window that should show movement.

**Why:** "no price has moved in a month" is either a frozen feed or a broken
scraper, and it is undetectable from a single batch — you cannot see a trend in
one snapshot. Deliberately last: it is the first item requiring persistent
state, which means migrations, a schema, and a real database in CI. Everything
above stays stateless and pure.

### 10. Per-check documentation page

One page per check: what it catches, the failure it was written for, how to tune
its threshold, and its false-positive mode.

**Why:** thresholds get set once by whoever added the check and are never
revisited, because nobody else knows what a sensible value looks like. A tuning
note is what makes a threshold adjustable by someone other than its author.

---

## Done

- **0. CI workflow added** — closed loop, 2026-09-10. `.github/workflows/ci.yml`
  now present: `ruff check .` + `pytest -q` on Python 3.11 and 3.12, then a CLI
  smoke test that runs `fqg check` against the intentionally-broken example feed
  and fails if the gate exits 0. Content is the workflow written (but un-pushable)
  by the genesis run; pushed now that the token carries the `workflow` scope.
  Verified locally before push: `pip install -e ".[dev]"` clean, `ruff` clean,
  `pytest -q` → 45 passed, `fqg check examples/sample_feed.csv` → exit 1 as
  designed. README's "No CI yet" note replaced and a status badge added.
  This unblocks items #1–#5 (each adds a check; CI is what keeps the next one
  from regressing a prior one).
- **v1 scaffold** — genesis loop, 2026-09-02. `models.py` (`Severity`,
  `CheckResult`, `FeedReport`, weighted scoring), `rules.py` (declarative YAML +
  readable validation errors), `checks.py` (`freshness`, `completeness`),
  `gate.py` (`evaluate` / `gate` split), `report.py` (JSON, console, Markdown,
  exit codes), `cli.py` (`fqg check`, `fqg explain`), working example feed.
  **45 tests passing and ruff clean, verified locally.**
- **pandas dtype portability fix** — `_is_blank` tested `dtype == object`, which
  silently stopped matching whitespace-only values on pandas 3.x (where text
  columns are typed `str`). Found by the end-to-end smoke test, not the unit
  tests, because a fixture had coerced the dtype the code expected. Regression
  tests now go through the real `read_csv` path.
