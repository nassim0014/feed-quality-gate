# CLAUDE.md — feed-quality-gate

Guidance for agents working in this repository.

## What this is

A generic quality-and-freshness gate for tabular feeds. It sits between a data
producer and its consumers, decides whether a feed is trustworthy, and splits
safe rows from unsafe ones. It **validates; it never transforms.**

## Hard rules

1. **No real data, ever.** No catalogue, competitor, customer, pricing or
   accounting data may be committed here — not in tests, not in fixtures, not in
   examples. Every fixture is invented. If you need a realistic feed, generate
   one.
2. **No hardcoded schema.** Column names always come from the rules file. If you
   find yourself typing a specific business column name into `feed_quality_gate/`,
   stop — it belongs in YAML.
3. **Checks stay pure.** A check is `(df, rule) -> CheckResult`. No I/O, no
   network, no database, no clock reads outside the injected `now`. This is what
   makes them testable and safe to call from an Airflow task.
4. **No transformation.** Normalising, matching, or repairing rows is the
   consumer's job. This package's output is a verdict and a partition.
5. **Never widen scope into live probing.** Checking whether a website is up is
   a different tool. This gate only ever looks at feed *data*.

## Conventions

- Python 3.11+, `from __future__ import annotations` at the top of every module.
- `ruff check .` must pass. Line length 100. The `B008` ignore on `cli.py` is
  deliberate — it is Typer's required idiom, not an oversight.
- Public functions get a docstring saying *why*, not just what. The interesting
  comments here explain a decision (see `_is_blank`, `quarantine_ids_for`).
- Value objects are dataclasses in `models.py` and must stay JSON-serialisable.

## Running things

```bash
pip install -e ".[dev]"
pytest                    # full suite, ~0.3s
ruff check .
fqg check -i examples/sample_feed.csv -r rules.example.yaml   # exits 1 by design
```

The example feed is **intentionally broken** (stale, missing prices, missing
category). A run that exits 0 against it means something regressed.

## Adding a check — the common task

Each backlog item in `docs/IMPROVEMENTS.md` is one check and one PR:

1. Add a rule model to `rules.py` (pydantic, with sane defaults so existing
   rules files keep working — never make a new rule required).
2. Add the pure check function to `checks.py`, returning a `CheckResult`.
3. Wire it into `evaluate()` in `gate.py` behind its `enabled` flag.
4. Add synthetic fixtures and tests, including the boundary case.
5. Document it in `rules.example.yaml` with a comment explaining *when* to use
   it, and update the README's "not built yet" list.

## Testing notes

- **Do not over-construct fixtures.** A bug shipped in the first version because
  a test called `astype(object)`, manufacturing the dtype the code expected and
  hiding a failure that only appeared via `read_csv`. When a code path handles
  parsed input, test it through the real read path at least once.
- pandas 2.x types text columns as `object`, pandas 3.x as `str`. Use
  `pd.api.types.is_string_dtype` / `is_object_dtype`, never `dtype == object`.
- Always inject `now` in freshness tests. Never let a test depend on the wall
  clock, or it will start failing on its own.

## Integration seam

`astk` (analytics-service-toolkit) is an **optional** extra, not a core
dependency, because it is a private repo and CI must be able to install this
package without credentials. Keep it that way: anything importing `astk` must
degrade gracefully when it is absent.
