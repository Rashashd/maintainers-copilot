"""Classification golden-set evaluator.

Runs the classifier against the 25-item hand-curated golden set and checks results
against thresholds in eval_thresholds.yaml. Writes eval_report.json to MinIO and
exits non-zero on threshold violation (CI gate).

Usage:
    python -m eval.classification.runner [--golden eval/classification/golden_set.jsonl]
"""

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"
THRESHOLDS_PATH = Path(__file__).resolve().parents[2] / "eval_thresholds.yaml"
REPORT_PATH = Path(__file__).parent / "eval_report.json"


def load_golden_set(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


async def call_classifier(base_url: str, title: str, body: str) -> dict:
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        resp = await client.post("/classify", json={"title": title, "body": body})
        resp.raise_for_status()
        return resp.json()


def compute_metrics(results: list[dict]) -> dict:
    labels = ["bug", "feature", "docs", "question"]
    tp: dict = defaultdict(int)
    fp: dict = defaultdict(int)
    fn: dict = defaultdict(int)

    correct = 0
    for r in results:
        pred = r["predicted"]
        gold = r["gold"]
        if pred == gold:
            correct += 1
            tp[gold] += 1
        else:
            fp[pred] += 1
            fn[gold] += 1

    accuracy = correct / len(results)

    per_class_f1 = {}
    for label in labels:
        precision = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) > 0 else 0.0
        recall = tp[label] / (tp[label] + fn[label]) if (tp[label] + fn[label]) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_class_f1[label] = round(f1, 4)

    macro_f1 = round(sum(per_class_f1.values()) / len(labels), 4)

    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": macro_f1,
        "per_class_f1": per_class_f1,
        "n": len(results),
        "correct": correct,
    }


def check_thresholds(metrics: dict, thresholds: dict) -> list[str]:
    violations = []
    t = thresholds.get("classification", {})

    if metrics["accuracy"] < t.get("accuracy", 0):
        violations.append(f"accuracy {metrics['accuracy']} < threshold {t['accuracy']}")
    if metrics["macro_f1"] < t.get("macro_f1", 0):
        violations.append(f"macro_f1 {metrics['macro_f1']} < threshold {t['macro_f1']}")

    per_class_t = t.get("per_class", {})
    for label, threshold in per_class_t.items():
        actual = metrics["per_class_f1"].get(label, 0)
        if actual < threshold:
            violations.append(f"per_class_f1[{label}] {actual} < threshold {threshold}")

    return violations


async def main(inference_url: str, golden_path: Path) -> int:
    print(f"Loading golden set from {golden_path} ...")
    items = load_golden_set(golden_path)
    print(f"Running classifier on {len(items)} items against {inference_url} ...")

    results = []
    for item in items:
        try:
            pred = await call_classifier(inference_url, item["title"], item["body"])
            results.append({
                "id": item["id"],
                "title": item["title"],
                "gold": item["label"],
                "predicted": pred["label"],
                "scores": pred["scores"],
                "correct": pred["label"] == item["label"],
            })
        except Exception as exc:
            print(f"  ERROR on item {item['id']}: {exc}")
            results.append({
                "id": item["id"],
                "title": item["title"],
                "gold": item["label"],
                "predicted": "error",
                "scores": {},
                "correct": False,
            })

    metrics = compute_metrics(results)
    print("\nResults:")
    print(f"  Accuracy:  {metrics['accuracy']:.4f}")
    print(f"  Macro-F1:  {metrics['macro_f1']:.4f}")
    print(f"  Per-class: {metrics['per_class_f1']}")

    thresholds = yaml.safe_load(THRESHOLDS_PATH.read_text())
    violations = check_thresholds(metrics, thresholds)

    report = {
        "metrics": metrics,
        "violations": violations,
        "passed": len(violations) == 0,
        "results": results,
    }
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
    parser.add_argument("--inference-url", default="http://localhost:8001")
    parser.add_argument("--golden", default=str(GOLDEN_SET_PATH))
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.inference_url, Path(args.golden))))
