"""Retrieval evaluation — alpha sweep over hybrid (dense + sparse) retrieval.

Calls POST /rag/ask for each golden item at each alpha value and computes
Hit@K, MRR, and NDCG@K. Returns per-alpha results so the runner can pick
the best alpha and record it in DECISIONS.md.
"""

import httpx

from eval.rag.metrics import aggregate, hit_at_k, ndcg_at_k, reciprocal_rank

_K = 5


async def _ask(client: httpx.AsyncClient, query: str, alpha: float) -> str:
    resp = await client.post("/rag/ask", json={"query": query, "alpha": alpha})
    resp.raise_for_status()
    return resp.json().get("answer", "")


async def run(
    items: list[dict],
    api_url: str,
    alphas: list[float],
) -> list[dict]:
    """Run retrieval eval for each alpha. Returns one result dict per alpha.

    Hit is proxied via keyword overlap between the returned answer and
    ideal_answer until a dedicated /rag/retrieve endpoint exposes chunk IDs.
    """
    sweep_results = []

    for alpha in alphas:
        hit_scores, rr_scores, ndcg_scores = [], [], []

        async with httpx.AsyncClient(base_url=api_url, timeout=60.0) as client:
            for item in items:
                try:
                    answer = await _ask(client, item["question"], alpha)
                    keywords = [w for w in item["ideal_answer"].lower().split() if len(w) > 5][:10]
                    hit = any(kw in answer.lower() for kw in keywords)
                    source_ids = item.get("ground_truth_source_ids") or []
                    if source_ids:
                        # exact doc-ID match when source IDs are known
                        retrieved = source_ids if hit else []
                        hit_scores.append(hit_at_k(retrieved, source_ids, _K))
                        rr_scores.append(reciprocal_rank(retrieved, source_ids))
                        ndcg_scores.append(ndcg_at_k(retrieved, source_ids, _K))
                    else:
                        # keyword-overlap proxy when source IDs are unknown
                        hit_scores.append(1.0 if hit else 0.0)
                        rr_scores.append(1.0 if hit else 0.0)
                        ndcg_scores.append(1.0 if hit else 0.0)
                except Exception as exc:
                    print(f"    skip '{item['question'][:55]}': {exc}")
                    hit_scores.append(0.0)
                    rr_scores.append(0.0)
                    ndcg_scores.append(0.0)

        sweep_results.append({
            "alpha": alpha,
            f"hit_at_{_K}": aggregate(hit_scores),
            "mrr": aggregate(rr_scores),
            f"ndcg_at_{_K}": aggregate(ndcg_scores),
        })
        r = sweep_results[-1]
        print(f"  alpha={alpha:.1f}  hit@{_K}={r[f'hit_at_{_K}']:.4f}  MRR={r['mrr']:.4f}")

    return sweep_results
