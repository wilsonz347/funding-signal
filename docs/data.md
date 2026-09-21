# Data Source: Sharpe API

## Overview

Sharpe has two API tiers:

- **Unauthenticated:** `/api/*`, no API key, but subject to unspecified per-IP limits.
- **Authenticated v1:** `/api/v1/*`, requires an API key and has documented usage limits.

This project uses the authenticated v1 API.

## Rate limits

- 30 requests per minute
- 10,000 requests per month
- `429` responses distinguish between:
  - `rate_limit_exceeded`: retry after `Retry-After`
  - `monthly_quota_exceeded`: unavailable until the next month
- Conditional requests using `If-None-Match` still count toward the monthly quota.

## Endpoints

### Current funding rates

```text
GET /v1/funding/rates?type=current
```

- Returns funding rates for all coins in one request.
- Data refreshes approximately every 5 minutes.
- Polling more frequently does not necessarily provide newer data.

### Historical funding rates

```text
GET /v1/funding/rates?type=history&coin=BTC&days=30
```

- Requires a single `coin` parameter.
- History is retrieved per coin rather than in bulk.
- The maximum `days` value and pagination behavior still need to be tested.
