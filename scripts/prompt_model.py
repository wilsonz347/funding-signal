# scripts/prompt_model.py
"""Runs end-to-end SQL agent tests against Ollama and Databricks"""

from src.agent.agent import SQLAgent
from src.agent.catalog import load_catalog
from src.agent.llm import OllamaClient
from src.agent.settings import Settings
from src.agent.warehouse import DatabricksWarehouse


QUESTIONS = [
    "What is the average funding rate by exchange?",
    "What is the latest funding rate for each exchange and symbol?",
    "Which exchanges have the largest funding moves?",
    "Which symbols have frozen funding rates?",
    "What is the relationship between funding rates and open interest?",
    "Which symbols currently have frozen funding rates?",
]


def main():
    catalog = load_catalog("config/agent_catalog.yaml")
    llm = OllamaClient()
    settings = Settings.from_env()

    with DatabricksWarehouse(settings) as warehouse:
        agent = SQLAgent(
            llm=llm,
            warehouse=warehouse,
            catalog=catalog,
        )

        for i, question in enumerate(QUESTIONS, start=1):
            print(f"\n{'=' * 70}")
            print(f"TEST {i}: {question}")
            print("=" * 70)

            result = agent.run(question)

            print(f"\nSTATUS: {'PASS' if result.ok else 'FAIL'}")
            print(f"ATTEMPTS: {len(result.attempts)}")

            for attempt in result.attempts:
                print(f"\nAttempt {attempt.number}: {attempt.stage}")

                if attempt.errors:
                    for error in attempt.errors:
                        print(f"  Error: {error}")

            if result.sql:
                print(f"\nFINAL SQL:\n{result.sql}")

            if result.ok and result.result is not None:
                query_result = result.result
                print(f"\nROWS RETURNED: {len(query_result.rows)}")
                print(f"TRUNCATED: {query_result.truncated}")
                print(f"DURATION: {query_result.duration_ms:.0f} ms")

                for row in query_result.rows:
                    print(row)

            if result.error:
                print(f"\nFINAL ERROR: {result.error}")


if __name__ == "__main__":
    main()
