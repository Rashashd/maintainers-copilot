"""RAG eval orchestrator — entry point for CI and manual runs.

Loads the golden set, runs retrieval eval (alpha sweep) and generation eval
(RAGAS), checks thresholds, writes eval_report.json, and exits non-zero on
threshold violation.

Usage:
    python -m eval.rag.runner                  # default alpha=0.5, with RAGAS
    python -m eval.rag.runner --alpha-sweep    # sweep alpha 0.1-0.9
    python -m eval.rag.runner --no-ragas       # skip RAGAS (faster)
    python -m eval.rag.runner --ablation       # extra passes: no-reranker, no-HyDE
    python -m eval.rag.runner --api-url http://localhost:8000
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from eval.rag import generation_eval, retrieval_eval  # noqa: E402


def _inject_llm_keys_from_vault(vault_addr: str, vault_token: str) -> None:
    if os.environ.get("OPENAI_API_KEY") and os.environ.get("ANTHROPIC_API_KEY"):
        return
    try:
        resp = httpx.get(
            f"{vault_addr}/v1/secret/data/llm",
            headers={"X-Vault-Token": vault_token},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]["data"]
        if not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = data["openai_api_key"]
            print("  OPENAI_API_KEY loaded from Vault.")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = data["anthropic_api_key"]
            print("  ANTHROPIC_API_KEY loaded from Vault.")
    except Exception as exc:
        print(f"  Warning: could not load LLM keys from Vault: {exc}")

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"
THRESHOLDS_PATH = Path(__file__).resolve().parents[2] / "eval_thresholds.yaml"
REPORT_PATH = Path(__file__).parent / "eval_report.json"

_K = 5


def load_golden_set(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def check_thresholds(metrics: dict, thresholds: dict) -> list[str]:
    violations = []
    t = thresholds.get("rag", {})
    checks = [
        (f"hit_at_{_K}", "hit_at_5"),
        ("mrr", "mrr"),
        ("faithfulness", "faithfulness"),
        ("answer_relevancy", "answer_relevancy"),
        ("context_recall", "context_recall"),
    ]
    for metric_key, threshold_key in checks:
        val = metrics.get(metric_key)
        thr = t.get(threshold_key)
        if val is not None and thr is not None and val < thr:
            violations.append(f"{metric_key} {val:.4f} < threshold {thr}")
    return violations


async def main(api_url: str, run_sweep: bool, run_ragas: bool, run_ablation: bool) -> int:
    items = load_golden_set(GOLDEN_SET_PATH)
    print(f"Loaded {len(items)} golden items from {GOLDEN_SET_PATH}")

    thresholds = yaml.safe_load(THRESHOLDS_PATH.read_text())
    report: dict = {"api_url": api_url, "n": len(items)}

    # ── Retrieval eval ────────────────────────────────────────────────────────
    alphas = [round(a * 0.1, 1) for a in range(1, 10)] if run_sweep else [0.6]
    print(f"\nRetrieval eval (alphas: {alphas}) ...")
    sweep = await retrieval_eval.run(items, api_url, alphas)
    report["sweep"] = sweep

    best = max(sweep, key=lambda r: r[f"hit_at_{_K}"])
    report["best_alpha"] = best["alpha"]
    hit = best[f"hit_at_{_K}"]
    print(f"\nBest alpha: {best['alpha']}  hit@{_K}={hit:.4f}  MRR={best['mrr']:.4f}")

    # ── Ablation passes (no-reranker, no-HyDE) ───────────────────────────────
    if run_ablation:
        best_alpha = best["alpha"]
        ablations = []
        for label, flags in [
            ("no_reranker", {"use_reranker": False, "use_hyde": True}),
            ("no_hyde",     {"use_reranker": True,  "use_hyde": False}),
        ]:
            print(f"\nAblation: {label} (alpha={best_alpha}) ...")
            rows = await retrieval_eval.run(items, api_url, [best_alpha], **flags)
            r = rows[0]
            ablations.append({"label": label, **flags, **r})
            print(f"  hit@{_K}={r[f'hit_at_{_K}']:.4f}  MRR={r['mrr']:.4f}")
        report["ablations"] = ablations
    else:
        report["ablations"] = []

    # ── Generation eval (RAGAS) ───────────────────────────────────────────────
    if run_ragas:
        _inject_llm_keys_from_vault(
            os.environ.get("VAULT_ADDR", "http://localhost:8200"),
            os.environ.get("VAULT_TOKEN", "dev-root-token"),
        )
        print(f"\nGeneration eval (RAGAS, alpha={best['alpha']}) ...")
        gen = await generation_eval.run(items, api_url, best["alpha"])
        report["generation"] = gen
        for key in ("faithfulness", "answer_relevancy", "context_recall"):
            val = gen.get(key)
            if val is not None:
                print(f"  {key}={val:.4f}")
    else:
        report["generation"] = {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_recall": None,
            "answer_correctness": None,
        }

    # ── Threshold check ───────────────────────────────────────────────────────
    all_metrics = {**best, **report["generation"]}
    violations = check_thresholds(all_metrics, thresholds)
    report["violations"] = violations
    report["passed"] = not violations

    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nReport written to {REPORT_PATH}")

    if violations:
        print("\nTHRESHOLD VIOLATIONS:")
        for v in violations:
            print(f"  ✗ {v}")
        return 1

    print("\n✓ All thresholds passed.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--alpha-sweep", action="store_true")
    parser.add_argument("--no-ragas", action="store_true")
    parser.add_argument("--ablation", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.api_url, args.alpha_sweep, not args.no_ragas, args.ablation)))
