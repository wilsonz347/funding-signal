# Decisions

Short record of the decisions shaping the project and the reasoning behind them.

## 1. Data source: Sharpe

**Decision:** Use Sharpe as the primary data source.

**Considered:** FinancialData.Net, CoinCap, Blockchain.com.

**Why:** Sharpe provides derivatives data, including funding rates, with documented limits of 30 requests/minute and 10,000 requests/month.

**Tradeoff:** Sharpe is a newer API, so its behavior still needs to be tested before relying on it for larger backfills.

## 2. Research question: funding rate mean-reversion

**Decision:** Predict whether an extreme funding rate returns toward normal within a defined time window.

**Considered:** Regime persistence, liquidation-driven volatility, cross-exchange funding divergence, and options skew.

**Why:** The question can start with a single asset and data source, and the reversion label is relatively straightforward to define.

**Tradeoff:** The scope is narrower than the alternatives and focuses primarily on funding-rate data.

## 3. Polling interval: 10 minutes

**Decision:** Poll the current funding endpoint every 10 minutes.

**Considered:** 5 minutes and hourly polling.

**Why:** Ten minutes provides more observations than hourly polling without polling faster than the API's approximately 5-minute refresh cycle. It uses roughly 4,320 requests/month, leaving room for retries and backfills.

**Tradeoff:** Uses more of the monthly quota than a slower polling schedule.

## 4. Catalog and schema layout

**Decision:** Use one dedicated catalog, `funding_regime_project`, with `bronze`, `silver`, `gold`, and `sandbox` schemas.

**Why:** Keeps the project organized around a standard medallion structure while separating exploratory work from the main data layers.

## 5. Python over PySpark for initial processing

**Decision:** Use Python for ingestion and early transformations rather than PySpark.

**Why:** The expected dataset is small enough to process on a single machine. Using distributed processing at this stage would add complexity without a clear performance need.

**Tradeoff:** This will need to be revisited if the project expands to substantially more assets, finer-grained data, or larger historical datasets.