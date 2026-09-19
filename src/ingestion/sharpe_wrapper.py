import time
from src.ingestion.sharpe_client import fetch_current_funding_rates, SharpeAPIError

MAX_RETRIES = 3


def fetch_current_funding_rates_safe(api_key: str) -> dict:
    """
    Attempts the fetch with retry/backoff on rate-limit responses.
    Never raises on API/network failure; returns a status field instead,
    so the caller can decide to skip this ingestion cycle.
    """
    attempt = 0
    while attempt <= MAX_RETRIES:
        try:
            result = fetch_current_funding_rates(api_key)
        except SharpeAPIError as e:
            return {"success": False, "reason": f"network_error: {e}"}

        if result["status_code"] == 200:
            return {"success": True, "result": result}

        if result["status_code"] == 429:
            retry_after = int(result["headers"].get("Retry-After", 30))
            attempt += 1
            if attempt > MAX_RETRIES:
                return {"success": False, "reason": "rate_limit_or_quota_exceeded", "result": result}
            time.sleep(retry_after)
            continue

        return {"success": False, "reason": f"unexpected_status_{result['status_code']}", "result": result}

    return {"success": False, "reason": "max_retries_exhausted"}
