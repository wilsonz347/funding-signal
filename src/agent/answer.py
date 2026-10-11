# src/agent/answer.py
"""Turns SQL query results into natural language answers"""

from __future__ import annotations

from dataclasses import dataclass

from src.agent.agent import AgentResult
from src.agent.catalog import Catalog
from src.agent.llm import LLMClient, LLMError



ANSWER_SYSTEM_PROMPT = """\
You are a data analyst answering questions using SQL query results.

Rules:
- Use only the supplied question, SQL, query results, and notes as evidence.
- Answer the question directly and concisely.
- Distinguish observed data, aggregated statistics, and predictions.
- Do not treat historical observations or averages as evidence of future outcomes.
- Do not claim causes or explanations that the results do not establish.
- If the data is insufficient to answer the question, clearly state what is missing.
- Preserve the meaning and units of numeric values.
- Funding rates are stored as decimal fractions. Multiply by 100 when expressing them as percentages. For example, 0.0002 = 0.02%.
- Never invent values, facts, or conclusions.
- Keep answers to at most 3 sentences.
"""


@dataclass
class Answer:
    text: str
    ok: bool
    sql: str | None = None
    rows_shown: int = 0
    rows_total: int = 0
    notes: list[str] | None = None


class Answerer:
    def __init__(self, llm: LLMClient, catalog: Catalog) -> None:
        self.llm = llm
        self.catalog = catalog

    def answer(self, agent_result: AgentResult) -> Answer:
        if not agent_result.ok or agent_result.result is None:
            return Answer(
                text=agent_result.error or "The query could not be completed.",
                ok=False,
            )

        result = agent_result.result
        if not result.rows:
            return Answer(
                text="No rows matched the query.",
                ok=True,
                sql=agent_result.sql,
                rows_total=0,
            )

        rows = result.rows[:self.catalog.max_llm_rows]
        notes = []

        if result.truncated or len(result.rows) > len(rows):
            notes.append("Results were truncated; only a subset is shown.")

        # Format results as readable text.
        data_text = "\n".join(
            [
                " | ".join(result.columns),
                *[
                    " | ".join(str(row.get(col, "NULL")) for col in result.columns)
                    for row in rows
                ],
            ]
        )

        prompt = (
            f"Question: {agent_result.question}\n\n"
            f"SQL executed:\n{agent_result.sql}\n\n"
            f"Query results:\n{data_text}\n\n"
            f"Notes: {notes or 'None'}\n\n"
            "Answer the question using only the evidence above."
        )

        try:
            text = self.llm.complete(ANSWER_SYSTEM_PROMPT, prompt)
        except LLMError:
            text = (
                "The query succeeded, but the summary is unavailable. "
                "Please refer to the query results."
            )

        return Answer(
            text=text,
            ok=True,
            sql=agent_result.sql,
            rows_shown=len(rows),
            rows_total=len(result.rows),
            notes=notes,
        )
