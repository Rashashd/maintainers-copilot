"""Retrieval metrics for the RAG golden set.

All functions take a list of retrieved source_ids and the ground-truth source_ids
for a single query and return a float score.
"""

import math


def hit_at_k(retrieved: list[str], ground_truth: list[str], k: int = 5) -> float:
    """1.0 if any ground-truth source_id appears in the top-k retrieved, else 0.0."""
    top_k = set(retrieved[:k])
    return 1.0 if any(gt in top_k for gt in ground_truth) else 0.0


def reciprocal_rank(retrieved: list[str], ground_truth: list[str]) -> float:
    """1 / rank of the first ground-truth hit. 0.0 if not found."""
    gt_set = set(ground_truth)
    for rank, item in enumerate(retrieved, start=1):
        if item in gt_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], ground_truth: list[str], k: int = 5) -> float:
    """Normalised Discounted Cumulative Gain at k (binary relevance)."""
    gt_set = set(ground_truth)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(retrieved[:k], start=1)
        if item in gt_set
    )
    ideal_hits = min(len(gt_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def aggregate(scores: list[float]) -> float:
    return round(sum(scores) / len(scores), 4) if scores else 0.0
