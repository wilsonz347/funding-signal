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

**Why:** The interval provides regular observations while staying below the API's refresh cadence and leaves substantial monthly quota for retries and backfills. It also provides sufficient temporal resolution for the project's four-hour prediction horizon.

**Tradeoff:** More frequent polling uses more quota without necessarily providing newer data.

## 4. Catalog and schema layout

**Decision:** Use one dedicated catalog, `funding_regime_project`, with `bronze`, `silver`, `gold`, and `sandbox` schemas.

**Why:** Keeps the project organized around a standard medallion structure while separating exploratory work from the main data layers.

## 5. Python over PySpark for initial processing

**Decision:** Use Python for ingestion and early transformations rather than PySpark.

**Why:** The expected dataset is small enough to process without distributed computing. Using PySpark at this stage would add complexity without a clear performance need.

**Tradeoff:** This will need to be revisited if the project expands to substantially more assets, finer-grained data, or larger historical datasets.

## 6. Layered API ingestion

**Decision:** Separate API communication, retry handling, and Bronze transformation into independent modules.

**Why:** `sharpe_client.py` handles communication with the API, `sharpe_wrapper.py` handles transient failures, and `bronze_transform.py` converts responses into table-ready records. This keeps each component focused and makes failures easier to isolate and test.

**Tradeoff:** The separation adds some files and interfaces compared with putting the ingestion logic in a single script.

## 7. Raw Bronze preservation

**Decision:** Preserve the vendor response and metadata in Bronze before applying downstream transformations.

**Why:** The Bronze layer should provide a faithful record of what was received. Each structured record also retains its raw JSON representation, allowing the source data to be reconstructed if the transformation logic changes.

**Tradeoff:** Storing raw data alongside structured fields increases storage slightly.

## 8. Schema drift handling

**Decision:** Flag unexpected or missing fields rather than failing the ingestion cycle.

**Why:** External API schemas can change. Making drift visible in the data allows the pipeline to continue collecting observations while preserving evidence that the source changed.

**Tradeoff:** Downstream transformations must account for records flagged with schema drift.

## 9. Ingestion testing

**Decision:** Test the API client, retry behavior, and transformation logic independently using mocked HTTP responses.

**Why:** Tests cover both successful requests and expected failure modes without consuming API quota. This also allows ingestion behavior to be validated before running it on a schedule.

## 10. Notebook orchestration

**Decision:** Keep the Databricks notebook as a thin orchestration layer.

**Why:** The notebook coordinates configuration, secrets, API calls, transformation, and writes to Bronze, while the actual behavior remains in tested Python modules.

**Tradeoff:** The workflow is split between the notebook and `src/`, but the separation keeps business logic out of the orchestration layer.

## 11. Scheduled ingestion

**Decision:** Run the ingestion job every 10 minutes with no job-level retries.

**Why:** The pipeline is designed as a continuous polling process. Transient API failures are handled within the ingestion wrapper, while a failed cycle can be picked up by the next scheduled run. This avoids rerunning the entire Databricks task unnecessarily.

**Tradeoff:** A failed cycle may result in a gap in the collected observations.

## 12. Bronze operates independently

**Decision:** Run Bronze ingestion independently of Silver and Gold transformations.

**Why:** Historical observations should accumulate even while downstream modeling layers are still under development. This allows the dataset to grow without coupling collection to the readiness of later pipeline stages.
