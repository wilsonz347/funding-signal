# Decisions

## 1. Data source: Sharpe

**Decision:** Use Sharpe as the primary source for crypto derivatives market data.

**Why:** Sharpe provides funding-rate data across multiple exchanges through a single API, making it possible to build a multi-venue dataset without maintaining separate integrations for each exchange.

**Tradeoff:** The API has usage limits, so the ingestion frequency must be chosen carefully.

## 2. Polling interval: 10 minutes

**Decision:** Poll the current funding-rate endpoint every 10 minutes.

**Why:** A 10-minute interval provides regular time-series observations while staying within Sharpe's documented request limits.

**Tradeoff:** Some market changes between polls will not be captured.

## 3. Bronze layer: preserve source data

**Decision:** Store the API response in Bronze before applying analytical transformations.

**Why:** Bronze provides a record of what the source actually returned. This makes the pipeline easier to debug and allows the data to be reprocessed if Silver logic changes.

## 4. Silver layer: clean and standardize the data

**Decision:** Use Silver to create typed, standardized, analysis-ready records from Bronze.

**Why:** Source data can contain inconsistent types, missing values, and different funding intervals. Silver provides a consistent structure for downstream analysis.

## 5. Preserve schema changes

**Decision:** Record missing and unexpected fields instead of failing the entire ingestion process when the API response changes.

**Why:** External APIs can evolve. The pipeline should continue collecting usable data while making schema changes visible for investigation.

## 6. Separate casting from quality checks

**Decision:** Track type-conversion failures separately from data-quality issues.

**Why:** A field can have the correct data type but still contain an invalid or suspicious value. Keeping these problems separate makes debugging and monitoring clearer.

For example, Silver records casting failures in `silver_cast_issues` and value-level problems in `silver_quality_issues`.

## 7. Normalize funding rates

**Decision:** Convert funding rates to a common 8-hour basis and calculate an annualized rate.

**Why:** Different exchanges and contracts can use different funding intervals. A common basis allows funding rates to be compared across markets.

**Tradeoff:** Annualization is an extrapolation assuming the observed rate remains constant. It is not a prediction of future returns.

## 8. Preserve contract differences

**Decision:** Keep exchange, symbol, and margin type in the Silver dataset rather than collapsing contracts into a single BTC-level series.

**Why:** Different contracts can have different funding schedules and market mechanics. Keeping the contract-level information preserves the ability to analyze these differences later.

## 9. Incremental Silver processing

**Decision:** Process only Bronze observations newer than the latest Silver `fetched_at` value.

**Why:** The dataset grows continuously, so reprocessing the entire Bronze table on every run would be unnecessary.

## 10. Idempotent Silver writes

**Decision:** Use `(exchange, symbol, fetched_at)` as the Silver observation key and MERGE new records into the Delta table.

**Why:** This represents one observation from one contract at one collection time and prevents duplicate observations when a batch is reprocessed.

## 11. Data-quality validation without automatic deletion

**Decision:** Flag questionable observations rather than automatically removing them from Silver.

**Why:** A suspicious market value may represent a real market condition rather than bad data. Keeping the observation and recording the issue preserves the evidence for later investigation.

## 12. Python modules for transformation logic

**Decision:** Keep transformation and validation logic in Python modules instead of putting the logic directly in Databricks notebooks.

**Why:** This makes the core pipeline logic easier to test, reuse, and maintain. Notebooks are primarily used to orchestrate the workflow.

## 13. Bronze and Silver as separate pipeline stages

**Decision:** Run Bronze ingestion and Silver transformation as separate dependent tasks.

**Why:** Bronze should first establish a successful source-data snapshot. Silver then transforms that data independently, creating a clear pipeline dependency.

## 14. Testing with real and edge-case data

**Decision:** Test transformations using both representative market data and edge cases such as missing values, invalid intervals, and timestamp inconsistencies.

**Why:** This verifies that the pipeline handles realistic source behavior instead of only working on ideal input.

## 15. Gold layer: feature engineering

**Decision:** Use Gold to create analysis-ready features from Silver, including funding-rate, open-interest, and price changes.

**Why:** Silver contains cleaned observations, while Gold contains the features needed for downstream analysis and modeling.

## 16. Historical context for Gold features

**Decision:** Read a bounded amount of historical Silver data when processing new observations.

**Why:** Features such as funding-rate changes and frozen-rate detection require previous observations. A bounded lookback provides the necessary context without reprocessing the entire dataset.

## 17. Gold incremental processing

**Decision:** Use the latest `fetched_at` timestamp in Gold as the watermark for incremental processing.

**Why:** The current dataset is small enough that querying the Gold table for its latest timestamp is simple and sufficient.

## 18. Time-series features by contract

**Decision:** Calculate historical features separately for each `(exchange, symbol)`.

**Why:** Funding rates and market behavior are contract-specific, so an observation should only be compared with the historical observations of the same contract.

## 19. Gold transformations

**Decision:** Keep Gold feature calculations in reusable Python modules and apply them to the incremental batch.

**Why:** This keeps analytical logic separate from pipeline orchestration and makes the calculations easier to test and maintain.

## 20. Idempotent Gold writes

**Decision:** Use `(exchange, symbol, fetched_at)` as the Gold observation key and MERGE results into the Delta table.

**Why:** The same batch may be processed more than once after a retry or failure. Idempotent writes prevent duplicate observations.

## 21. `is_frozen` as a behavioral feature

**Decision:** Treat `is_frozen` as a signal of repeated unchanged funding rates rather than automatically classifying the observation as bad data.

**Why:** A funding rate remaining unchanged across several polls can reflect naturally low update frequency rather than a broken feed. The behavior can vary across exchanges.
