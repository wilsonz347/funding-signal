# Funding Rate Regime Prediction

## What this project does

This project predicts whether an extreme funding rate on Bitcoin perpetual futures will revert toward normal within a defined time window or remain extreme.

Funding rate is the periodic payment between long and short traders on a perpetual futures contract. When it moves far from zero, one side of the market is unusually crowded and paying a higher cost to hold its position.

The goal is not to build a guaranteed profitable trading bot. It is to build a reliable data pipeline, properly validate the model, and distinguish predictive performance from profitability after trading costs.

## Current phase: Data Engineering

The project is split into three phases. The current focus is **Phase 1**.

1. **Data Engineering** — ingest funding-rate data from the Sharpe API, store the raw data, clean it, and produce model-ready tables.
2. **Data Science** — develop baseline, statistical, and ML models using the Phase 1 data.
3. **Quantitative Evaluation** — test whether the resulting signal holds up after fees and slippage.

Modeling begins only after Phase 1 produces trustworthy data.

## Data source

Primary data source: [Sharpe](https://www.sharpe.ai), a key-based API for crypto derivatives data, including funding rates, open interest, and liquidations.

See `docs/data.md` for the API findings and limitations identified so far.

## Architecture

Built on Databricks using a medallion architecture:

```text
Sharpe API → Ingestion job → Bronze (raw) → Silver (cleaned) → Gold (features)
```

- **Catalog:** `funding_regime_project`
- **Schemas:** `bronze`, `silver`, `gold`, `sandbox`
- **Processing:** Plain Python for the initial pipeline. The expected data volume does not currently require distributed processing.

See `docs/decisions.md` for the reasoning behind these choices.

## Repo structure

```text
project/
├── README.md
├── src/ingestion/        # API client and ingestion logic
├── notebooks/            # Databricks notebooks (source format)
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

## Status

Project structure initialized. Ingestion logic not yet implemented.