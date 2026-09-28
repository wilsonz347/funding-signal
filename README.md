# Bitcoin Perpetual Funding Rate Pipeline

## What this project does

This project collects funding-rate data for Bitcoin perpetual futures from many exchanges and turns it into clean, analysis-ready tables on Databricks.

Funding rate is the periodic payment between long and short traders on a perpetual futures contract. When it moves far from zero, one side of the market is crowded and paying more to hold its position.

The question the data is built to answer:

> How do funding rates behave across crypto perpetual futures markets, and what factors are associated with changes in funding?

## Data source

[Sharpe](https://www.sharpe.ai) authenticated API (v1). The current funding-rate endpoint returns every contract in one call and is polled every 10 minutes.

- Rate limits: 30 requests per minute and 10,000 per month. Polling every 10 minutes uses about 4,320 requests a month.
- Coverage: 42 BTC perpetual contracts across 31 exchanges, selected by `base_coin = 'BTC'`.

See `docs/data.md` for API findings and known quirks.

## Architecture

```text
Sharpe API -> Bronze (raw) -> Silver (typed, standardized) -> Gold (analysis features)
```

One scheduled Databricks job runs the layers as dependent tasks, with validation checks after each one.

- **Catalog:** `funding_regime_project`
- **Schemas:** `bronze`, `silver`, `gold`, `sandbox`
- **Platform:** Databricks Free Edition (serverless). Transformations are plain Python and Delta tables, since the data volume does not need distributed processing.

### Layers

- **Bronze** stores what the API returned, unfiltered and append-only, one row per exchange and symbol per poll. The raw JSON for each record is kept next to the structured columns. Missing or unexpected fields are flagged on the row and never stop ingestion.
- **Silver** (`silver.funding_rates`) has the same grain as bronze, filtered to BTC contracts and cast to proper types. It adds `rate_per_8h` and `rate_annualized` so venues with 1, 4 and 8 hour intervals can be compared, plus `poll_lag_seconds`. Type failures are recorded in `silver_cast_issues` and implausible values in `silver_quality_issues`. Flagged rows are kept, not deleted.
- **Gold** (`gold.funding_rate_analysis`) adds features that need neighboring rows, one row per silver row.

### Gold columns

| Column | Meaning |
| --- | --- |
| `exchange`, `symbol`, `margin_type` | Contract identity, kept so differences are not hidden |
| `fetched_at` | Poll time (row key with exchange and symbol) |
| `rate_per_8h` | Funding rate on a common 8-hour basis |
| `funding_change` | Change from the previous poll |
| `is_large_move` | Absolute `funding_change` at or above 0.00008 (about the 99th percentile of observed changes) |
| `is_frozen` | Rate unchanged across the previous 5 polls |
| `open_interest`, `oi_change` | Open interest and its change from the previous poll |
| `mark_price`, `price_change` | Mark price and its change from the previous poll |

Features are null when there is not enough history, for example the first poll of a contract.

## Pipeline design

- **Idempotent writes.** Silver and gold MERGE on `(exchange, symbol, fetched_at)`, so re-running a batch does not create duplicates.
- **Incremental reads.** Each layer reads rows newer than the latest `fetched_at` already in its target table. Delta change feed and time travel are not available on serverless.
- **Logic in modules, orchestration in notebooks.** Transformation code lives in `src/` and is unit tested. Notebooks only wire the steps together.
- **Flag, don't delete.** A suspicious value may be a real market condition, so it is recorded and kept.

## Data quality checks

- One check per layer: duplicate keys, freshness or lag against the upstream layer, and layer-specific checks such as partial polls in bronze and unpopulated derived columns in silver.
- A cross-layer reconciliation that compares row counts from bronze to silver to gold. The counts matched exactly at the last run.

## What the data shows

These are descriptive findings from about 8 days of data.

- Most venues fund in a narrow band, about 0.003% to 0.005% per 8 hours, mostly paid by longs.
- CoinEx is a clear outlier at roughly -0.25% to -0.34% per 8 hours, and one contract sits at a single value for long stretches.
- Update frequency differs by venue. Some rates change on almost every poll, others on fewer than 6%.
- About a third of large funding moves happen in three hours of the day (00:00, 08:00, 16:00 UTC), the usual settlement times.
- Funding changes tend to move with price changes on most venues, modestly. No clear link to open interest.

The window is short and calm, and these are associations, not causes.

## Known limitations

- **Short history.** All data comes from the pipeline's own polling. The API also has a history endpoint, but it returns settled rates at one row per settlement, a different grain and meaning from the polled rate. It would need its own table and load path, so backfill was not built.
- **Backdated rows are skipped.** The watermark pattern ignores rows older than the latest one already loaded.
- **`is_frozen` means "not updating," not "broken."** Naturally quiet venues show high rates of it. See `docs/decisions.md`.
- **Price is coin-level.** `mark_price` is the same value across contracts at each poll, so there is no cross-venue basis.

## Possible next steps

- Build a settlement-grain history table to extend the analysis to volatile periods.
- Add cross-exchange comparison views on top of the gold table.

## Repo structure

```text
project/
├── README.md
├── src/
│   ├── ingestion/        # API client and ingestion logic
│   ├── transformations/  # Silver and gold transformation logic
│   └── validation/       # Per-layer and cross-layer checks
├── notebooks/            # Databricks notebooks (thin orchestration)
├── config/               # Catalog, schema, and endpoint settings
├── docs/
│   ├── data.md           # Data source investigation
│   └── decisions.md      # Decision log
├── tests/
├── sql/
├── .gitignore
├── LICENSE
└── requirements.txt
```

## Running it

1. Link the repo to Databricks as a Git folder.
2. Store the Sharpe API key as a Unity Catalog secret. It is never committed.
3. Create the job with the bronze, silver and gold tasks, each followed by its validation check, on a 10-minute schedule.
4. Run the unit tests with `pytest`.

## Status

Complete for the scope above. See the limitations and next steps sections for what was left out on purpose.