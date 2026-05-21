# Evaluations

## Overview

Two separate eval pipelines, each with a 25-item golden set and pass/fail thresholds
committed in `eval_thresholds.yaml`. The app refuses to boot if any threshold is
zero or disabled — evals are not optional.

---

## Classification eval

**Golden set:** `eval/classification/golden_set.jsonl`
25 manually verified issues from `home-assistant/core`, one per label class,
drawn from the held-out test split (not seen during training).

**What is measured:**

| Metric | Threshold | Result |
|---|---|---|
| Accuracy | ≥ 0.60 | 0.63 |
| Macro-F1 | ≥ 0.60 | 0.63 |
| Bug F1 | ≥ 0.55 | — |
| Feature F1 | ≥ 0.50 | — |
| Docs F1 | ≥ 0.85 | — |
| Question F1 | ≥ 0.35 | — |
| Classification p95 latency | ≤ 200ms | — |

**How to run:**
```bash
python -m eval.classification.runner
```

**Model:** DistilBERT fine-tuned on 80% of the temporal split (train.parquet).
Baseline: LLM zero-shot (gpt-4o-mini) scored 0.59 macro-F1 on the full test set.
Fine-tuned DistilBERT scored 0.63 — chosen for lower cost and latency.

---

## RAG eval

**Golden set:** `eval/rag/golden_set.jsonl`
25 question/answer pairs derived from resolved `home-assistant/core` issues.
Questions are what a maintainer might ask; answers are grounded in the issue resolution.

**What is measured:**

| Metric | Threshold | Notes |
|---|---|---|
| Hit@5 | ≥ 0.70 | Does the correct chunk appear in top-5 results? |
| MRR | ≥ 0.60 | Mean Reciprocal Rank of the correct chunk |
| Faithfulness | ≥ 0.65 | RAGAS: is the answer grounded in retrieved chunks? |
| Answer relevancy | ≥ 0.35 | RAGAS: does the answer address the question? |
| Context recall | ≥ 0.55 | RAGAS: are the retrieved chunks sufficient? |
| RAG retrieval p95 | ≤ 300ms | Retrieval only, excluding LLM generation |
| Chat e2e p95 | ≤ 5000ms | Full chat round-trip including LLM |

**How to run:**
```bash
# Full eval including RAGAS LLM-as-judge (requires OpenAI key in Vault)
python -m eval.rag.runner --api-url http://localhost:8000

# Retrieval metrics only, no LLM cost
python -m eval.rag.runner --api-url http://localhost:8000 --no-ragas
```

Report written to `eval/rag/eval_report.json`.

**Pipeline tested:**
HyDE query rewriting → BM25 + BGE-base-en-v1.5 dense retrieval → RRF fusion (alpha=0.6)
→ cross-encoder/ms-marco-MiniLM-L-6-v2 reranker → top-5 chunks

---

## LLM-as-judge agreement

5 of the 25 RAG golden items were hand-labeled independently and compared against
RAGAS scores to validate the automated judge. See DECISIONS.md #11 for results.

---

## Cost and latency targets

| Metric | Threshold |
|---|---|
| Max tokens per request | 2000 |
| Max USD per 1k requests | $0.50 |
| Classification p95 | ≤ 200ms |
| RAG retrieval p95 | ≤ 300ms |
| Chat e2e p95 | ≤ 5000ms |

These are enforced in `eval_thresholds.yaml` and checked at startup.
