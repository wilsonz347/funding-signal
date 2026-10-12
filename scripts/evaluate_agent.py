# scripts/evaluate_agent.py
#!/usr/bin/env python3
"""Checks SQL correctness: runs expected_sql and the agent's SQL on Databricks and compares the rows.

Start the API first, then run from the repository root:
    python scripts/evaluate_agent.py
    python scripts/evaluate_agent.py --url http://127.0.0.1:5000/ask --output evals/report.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `src.` imports work from anywhere

import httpx  # noqa: E402
import yaml  # noqa: E402

from src.agent.settings import Settings  # noqa: E402
from src.agent.warehouse import DatabricksWarehouse, WarehouseError  # noqa: E402

MAX_ROWS = 10_000
MAX_LLM_ROWS = 50  # the agent's LIMIT, so a larger golden result may legitimately be cut


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        cases = (yaml.safe_load(f) or {}).get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Validation YAML must contain a non-empty 'cases' list.")
    for i, case in enumerate(cases):
        for field in ("id", "question", "expected_sql"):
            if not case.get(field):
                raise ValueError(f"Case {i} is missing '{field}'.")
        if not case.get("compare", {}).get("key"):
            raise ValueError(f"Case {case['id']} needs compare.key (a list of columns).")
    return cases


def extract_sql(payload: Any) -> str:
    if isinstance(payload, dict):
        sql = payload.get("sql")
        if isinstance(sql, str) and sql.strip():
            return sql.strip()
    raise ValueError("No SQL in the response (expected a 'sql' field).")


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not math.isnan(v)


def results_match(golden, agent, key, rel_tol=1e-3, check_values=False) -> tuple[bool, str]:
    """Compare two result sets by key columns. Aliases may differ, so values match by number, not name."""
    if not agent:
        return False, "agent returned no rows"
    for name, rows in (("golden", golden), ("agent", agent)):
        if rows and not all(k in rows[0] for k in key):
            return False, f"{name} result is missing key column(s) {key}"
    g = {tuple(r[k] for k in key): r for r in golden}
    a = {tuple(r[k] for k in key): r for r in agent}
    if len(a) != len(agent):
        return False, "agent returned duplicate keys (wrong grain)"
    extra = set(a) - set(g)
    if extra:
        return False, f"agent returned keys not in golden: {sorted(map(str, extra))[:3]}"
    missing = set(g) - set(a)
    if missing and len(g) <= MAX_LLM_ROWS:
        return False, f"agent is missing keys: {sorted(map(str, missing))[:3]}"
    if check_values:
        for k, grow in g.items():
            if k not in a:
                continue
            nums = [v for c, v in a[k].items() if c not in key and _is_num(v)]
            for c, v in grow.items():
                if c in key or not _is_num(v):
                    continue
                if not any(math.isclose(v, n, rel_tol=rel_tol, abs_tol=1e-12) for n in nums):
                    return False, f"value mismatch for {k}: golden {c}={v}"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", dest="set_path", type=Path, default=Path("config/validation_set.yaml"))
    parser.add_argument("--url", default="http://127.0.0.1:5000/ask")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", type=Path, default=None, help="Optional path for a JSON report.")
    args = parser.parse_args()

    try:
        cases = load_cases(args.set_path)
        settings = Settings.from_env()
    except Exception as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 2

    results = []
    with DatabricksWarehouse(settings) as warehouse, httpx.Client(timeout=args.timeout) as client:
        for case in cases:
            row = {"id": case["id"], "question": case["question"], "passed": False, "reason": ""}
            print(f"[RUN] {case['id']}: {case['question']}")
            try:
                response = client.post(args.url, json={"question": case["question"]})
                response.raise_for_status()
                agent_sql = extract_sql(response.json())
                golden = warehouse.run_query(case["expected_sql"], MAX_ROWS).rows
                agent = warehouse.run_query(agent_sql, MAX_ROWS).rows
                ok, reason = results_match(golden, agent, **case["compare"])
                row.update(passed=ok, reason=reason, agent_sql=agent_sql,
                           golden_rows=len(golden), agent_rows=len(agent))
            except (httpx.HTTPError, ValueError, WarehouseError) as exc:
                row["reason"] = f"error: {exc}"
            results.append(row)
            print(f"  {'PASS' if row['passed'] else 'FAIL'}: {row['reason']}")

    passed = sum(r["passed"] for r in results)
    print(f"\nSummary: {passed}/{len(results)} passed")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"passed": passed, "total": len(results), "results": results},
                                          indent=2, default=str) + "\n", encoding="utf-8")
        print(f"Report written to {args.output}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
