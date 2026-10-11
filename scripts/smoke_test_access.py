# scripts/smoke_test_access.py
"""
Smoke test for access to the Databricks warehouse using the agent's credentials.
This script attempts to connect to the Databricks warehouse and perform a series of queries to verify
that the agent has the expected permissions. It checks both allowed and denied operations.
Usage:
    python scripts/smoke_test_access.py
Make sure to set the required environment variables for the agent's credentials before running this script.
Environment Variables:
    - FUNDING_SIGNAL_HOST: The Databricks host URL (e.g., "<databricks-instance>.cloud.databricks.com").
    - FUNDING_SIGNAL_HTTP_PATH: The HTTP path for the Databricks SQL endpoint (e.g., "/sql/1.0/endpoints/xxxxxxx")
    - FUNDING_SIGNAL_CLIENT_ID: The client ID for the Databricks service principal.
    - FUNDING_SIGNAL_CLIENT_SECRET: The client secret for the Databricks service principal.
"""

from databricks import sql
from databricks.sdk.core import Config, oauth_service_principal

from agent.settings import Settings


GOLD_TABLE = "funding_regime_project.gold.funding_rate_analysis"


def credentials_provider(settings: Settings):
    return oauth_service_principal(
        Config(
            host=f"https://{settings.host}",
            client_id=settings.client_id,
            client_secret=settings.client_secret,
        )
    )


def create_connection(settings: Settings):
    return sql.connect(
        server_hostname=settings.host,
        http_path=settings.http_path,
        credentials_provider=lambda: credentials_provider(settings),
    )


# Test helpers
def run_allowed_test(cursor, name, query):
    """Test a query that should succeed."""
    try:
        cursor.execute(query)
        result = cursor.fetchone()

        print(f"[PASS] {name}")
        if result is not None:
            print(f"       Result: {result}")

        return True

    except Exception as e:
        print(f"[FAIL] {name}")
        print(f"       {e}")
        return False


def run_denied_test(cursor, name, query):
    """Test a query that should be rejected by permissions."""
    try:
        cursor.execute(query)

        print(f"[FAIL] {name}")
        print("Query unexpectedly succeeded.")

        return False

    except Exception:
        print(f"[PASS] {name}")
        print("Access denied as expected.")

        return True


def main():
    settings = Settings.from_env()
    conn = None

    try:
        conn = create_connection(settings)

        with conn.cursor() as cursor:

            print("\n=== ALLOWED ACCESS ===\n")

            run_allowed_test(
                cursor,
                "SELECT from Gold table",
                f"""
                SELECT COUNT(*)
                FROM {GOLD_TABLE}
                """,
            )

            run_allowed_test(
                cursor,
                "DESCRIBE Gold table",
                f"""
                DESCRIBE TABLE {GOLD_TABLE}
                """,
            )

            print("\n=== DENIED ACCESS ===\n")

            run_denied_test(
                cursor,
                "SELECT from Bronze",
                """
                SELECT COUNT(*)
                FROM funding_regime_project.bronze.funding_rates
                """,
            )

            run_denied_test(
                cursor,
                "SELECT from Silver",
                """
                SELECT COUNT(*)
                FROM funding_regime_project.silver.funding_rates
                """,
            )

            print("\n=== DENIED WRITE OPERATIONS ===\n")

            run_denied_test(
                cursor,
                "INSERT into Gold",
                f"""
                INSERT INTO {GOLD_TABLE}
                SELECT *
                FROM {GOLD_TABLE}
                LIMIT 1
                """,
            )

            run_denied_test(
                cursor,
                "DELETE from Gold",
                f"""
                DELETE FROM {GOLD_TABLE}
                WHERE 1 = 0
                """,
            )

            run_denied_test(
                cursor,
                "DROP Gold table",
                f"""
                DROP TABLE {GOLD_TABLE}
                """,
            )

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
