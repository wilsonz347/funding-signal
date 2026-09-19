import requests
from datetime import datetime, timezone

SHARPE_BASE_URL = "https://www.sharpe.ai/api/v1"


class SharpeAPIError(Exception):
    """Raised on network-level failures (timeout, connection error)."""
    pass


def fetch_current_funding_rates(api_key: str, timeout: int = 10) -> dict:
    """
    Calls the Sharpe current-funding-rate endpoint once.
    Returns the raw response wrapped with ingestion metadata.
    """
    url = f"{SHARPE_BASE_URL}/funding/rates"
    params = {"type": "current"}
    headers = {"Authorization": f"Bearer {api_key}"}
    fetched_at = datetime.now(timezone.utc).isoformat()

    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise SharpeAPIError(f"Request failed: {e}") from e

    return {
        "fetched_at": fetched_at,
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "url": response.url,
        "payload": response.text,
    }
