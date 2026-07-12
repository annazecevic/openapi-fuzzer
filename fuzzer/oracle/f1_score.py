import json
from pathlib import Path


def compute_f1(ground_truth_path: str) -> dict:
    data = json.loads(Path(ground_truth_path).read_text(encoding="utf-8"))

    results = data.get("results", [])
    fn_count = int(data.get("false_negatives", 0))

    tp = 0
    fp = 0

    for r in results:
        if not r.get("anomalies"):
            continue
        if r.get("true_positive") is True:
            tp += 1
        elif r.get("true_positive") is False:
            fp += 1

    fn = fn_count
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
    }


def print_report(metrics: dict) -> None:
    print("\n── F1 Score Evaluacija ──────────────────────────────")
    print(f"  True Positives  (TP): {metrics['true_positives']}")
    print(f"  False Positives (FP): {metrics['false_positives']}")
    print(f"  False Negatives (FN): {metrics['false_negatives']}")
    print(f"  Precision:            {metrics['precision']:.4f}")
    print(f"  Recall:               {metrics['recall']:.4f}")
    print(f"  F1 Score:             {metrics['f1_score']:.4f}")
    print("─────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Izračunaj F1 Score iz anotiranog report.json fajla."
    )
    parser.add_argument(
        "--ground-truth",
        required=True,
        help="Putanja do anotiranog JSON fajla (sa true_positive i false_negatives poljem).",
    )
    args = parser.parse_args()

    try:
        metrics = compute_f1(args.ground_truth)
        print_report(metrics)
    except FileNotFoundError:
        print(f"GREŠKA: Fajl nije pronađen: {args.ground_truth}")
        sys.exit(1)
    except (KeyError, json.JSONDecodeError) as exc:
        print(f"GREŠKA: Neispravan format fajla: {exc}")
        sys.exit(1)
