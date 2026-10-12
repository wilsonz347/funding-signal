# Bitcoin Perpetual Funding Rate Pipeline

## What this project does

This project collects funding-rate data for Bitcoin perpetual futures across multiple exchanges and processes it into structured, analysis-ready tables on Databricks. It also includes an LLM-powered SQL agent that lets users query the resulting dataset using natural language.

Funding rate is the periodic payment between long and short traders on a perpetual futures contract.

## Data source

[Sharpe](https://www.sharpe.ai) authenticated API (v1). The current funding-rate endpoint returns every contract in one call and is polled every 10 minutes.

- **Rate limits:** 30 requests per minute and 10,000 per month. Polling every 10 minutes uses about 4,320 requests a month.
- **Coverage:** 42 BTC perpetual contracts across 31 exchanges, selected by `base_coin = 'BTC'`.

See [`docs/data.md`](docs/data.md) for API findings and known quirks.

## Architecture

```text
Sharpe API
    |
    v
Bronze (raw data)
    |
    v
Silver (typed and standardized)
    |
    v
Gold (derived features)
    |
    v
LLM-powered SQL agent
    |
    v
Natural-language answers
```

A scheduled Databricks job runs the data layers as dependent tasks, with validation checks after each one. The SQL agent is a separate application layer that generates SQL, validates it, executes approved queries against the Gold table, and summarizes the results.

- **Catalog:** `funding_regime_project`
- **Schemas:** `bronze`, `silver`, `gold`, `sandbox`
- **Platform:** Databricks Free Edition (serverless)
- **Transformations:** Python and Delta tables
- **Agent:** Python, Ollama, and Flask

### Data layers

- **Bronze** stores API responses, unfiltered and append-only, with raw JSON alongside structured columns. Missing or unexpected fields are flagged without stopping ingestion.
- **Silver** (`silver.funding_rates`) contains typed BTC contract data at the same grain as Bronze. It adds `rate_per_8h`, `rate_annualized`, and `poll_lag_seconds`. Type failures and implausible values are recorded in issue tables. Flagged rows are retained.
- **Gold** (`gold.funding_rate_analysis`) adds features derived from neighboring observations, with one row per Silver row.

### Gold columns

| Column | Meaning |
| --- | --- |
| `exchange`, `symbol`, `margin_type` | Contract identity |
| `fetched_at` | Poll time; part of the row key |
| `rate_per_8h` | Funding rate on a common 8-hour basis |
| `funding_change` | Change from the previous poll |
| `is_large_move` | Absolute `funding_change` at or above 0.00008 |
| `is_frozen` | Rate unchanged across the previous five polls |
| `open_interest`, `oi_change` | Open interest and its change from the previous poll |
| `mark_price`, `price_change` | Mark price and its change from the previous poll |

Features are null when there is insufficient history, such as the first observation for a contract.

## SQL analyst agent

The agent allows users to ask questions about the Gold dataset in natural language. It uses an LLM to generate SQL, validates the generated query against an approved catalog, executes it through Databricks SQL, and uses a second LLM call to summarize the returned rows.

### Request flow

```text
Question
   |
   v
SQL generation
   |
   v
SQL validation
   |
   v
Databricks query execution
   |
   v
Answer generation
   |
   v
JSON API response
```

The API is implemented in `src/api/server.py`:

- `POST /ask` accepts a natural-language question and returns the answer, SQL, and result metadata.
- `GET /health` provides a basic application health check.

See [`docs/decisions.md`](docs/decisions.md) for pipeline design decisions and [`docs/agent_decisions.md`](docs/agent_decisions.md) for SQL agent architecture decisions.

## Repository structure

```text
project/
├── .github/              # CI/CD
├── README.md
├── src/
│   ├── ingestion/        # API client and ingestion logic
│   ├── transformations/  # Silver and Gold transformations
│   ├── validation/       # Data quality checks
│   ├── agent/            # SQL agent, prompts, validation and answers
│   └── api/              # Flask API
├── notebooks/            # Databricks orchestration
├── scripts/              # Agent testing scripts
├── config/               # Pipeline and agent configuration
├── docs/
│   ├── data.md
│   ├── decisions.md
│   └── agent_decisions.md
├── tests/
├── .gitignore
├── .env.example
├── LICENSE
└── requirements.txt
```

## Running the project

### SQL agent

1. Install the project dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Configure the required Databricks connection environment variables using `.env.example` as a reference.
3. Ensure the local Ollama service is running and the configured model is available.
4. Start the Flask API:

   ```bash
   python -m src.api.server
   ```

5. Send a question to `POST /ask` as JSON:

   ```json
   {
     "question": "What is the average funding rate by exchange?"
   }
   ```

6. Check `GET /health` to confirm the API is responding.

## Testing

Run the unit tests:

```bash
pytest
```

Run the Databricks warehouse integration tests:

```bash
pytest tests/test_warehouse_integration.py
```

Integration tests require valid Databricks credentials and an available SQL warehouse. Configure the required environment variables before running them.

Evaluate the SQL agent against the fixed validation set:

```bash
python scripts/evaluate_agent.py
```

The evaluation compares generated-query results against reference-query results for predefined natural-language questions. See `docs/agent_decisions.md` for the evaluation approach and its limitations.

## Documentation

- [`docs/data.md`](docs/data.md): API behavior, data coverage, and known quirks.
- [`docs/decisions.md`](docs/decisions.md): Data pipeline architecture and design tradeoffs.
- [`docs/agent_decisions.md`](docs/agent_decisions.md): SQL agent architecture, validation, evaluation, and limitations.

## Status

## Status

The project includes the Bronze/Silver/Gold data pipeline, incremental Delta processing, automated data validation, and a natural-language SQL agent with query validation and result evaluation. Unit and Databricks integration tests are included in the testing workflow.

Known limitations and design tradeoffs are documented in the accompanying decision records.
