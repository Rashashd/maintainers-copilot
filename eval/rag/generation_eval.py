"""Generation evaluation — RAGAS metrics.

Calls POST /rag/ask for each golden item at the given alpha and evaluates
the returned answers using RAGAS metrics. Requires the `ragas` and
`datasets` packages (included in pyproject.toml).

LLM-as-judge note: RAGAS uses an LLM internally. Ensure OPENAI_API_KEY
(or equivalent) is reachable when running this module.
"""

import math

import httpx

_EMPTY = {
    "faithfulness": None,
    "answer_relevancy": None,
    "context_recall": None,
}


def _mean(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, list):
        valid = [v for v in val if v is not None and not (isinstance(v, float) and math.isnan(v))]
        return sum(valid) / len(valid) if valid else None
    v = float(val)
    return None if math.isnan(v) else v


async def run(items: list[dict], api_url: str, alpha: float) -> dict:
    """Run RAGAS faithfulness, answer_relevancy, context_recall, answer_correctness.

    Returns a dict with all four metrics (float or None if RAGAS unavailable).
    """
    try:
        from datasets import Dataset
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_recall,
            faithfulness,
        )
    except ImportError:
        print("  ragas/datasets not available — skipping generation metrics.")
        return _EMPTY

    questions, answers, contexts, ground_truths = [], [], [], []

    async with httpx.AsyncClient(base_url=api_url, timeout=60.0) as client:
        for item in items:
            try:
                resp = await client.post(
                    "/rag/ask", json={"query": item["question"], "alpha": alpha}
                )
                resp.raise_for_status()
                body = resp.json()
                questions.append(item["question"])
                answers.append(body.get("answer", ""))
                contexts.append(body.get("contexts", []))
                ground_truths.append(item["ideal_answer"])
            except Exception as exc:
                print(f"    skip '{item['question'][:55]}': {type(exc).__name__}: {exc}")

    if not questions:
        return _EMPTY

    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall],
        llm=ChatOpenAI(model="gpt-4o-mini"),
        embeddings=OpenAIEmbeddings(),
    )

    return {
        "faithfulness":     _safe_round(result["faithfulness"]),
        "answer_relevancy": _safe_round(result["answer_relevancy"]),
        "context_recall":   _safe_round(result["context_recall"]),
    }


def _safe_round(val) -> float | None:
    v = _mean(val)
    return round(v, 4) if v is not None else None
