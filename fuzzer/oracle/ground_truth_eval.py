import json
from pathlib import Path

import yaml

# Poredi izveštaj alata (report.json) sa unapred pripremljenom listom poznatih
# bagova (known_bugs.yaml) — za razliku od f1_score.py (ručna anotacija posle
# izvršavanja), ovde je ground truth definisan UNAPRED, pa se poklapanje radi
# automatski po (endpoint, method, mutated_field)
def evaluate_against_ground_truth(report_path: str, known_bugs_path: str) -> dict:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    known_bugs = yaml.safe_load(Path(known_bugs_path).read_text(encoding="utf-8")) or []

    findable_bugs = [b for b in known_bugs if b.get("findable_by_tool")]
    known_unfindable = [b["id"] for b in known_bugs if not b.get("findable_by_tool")]

    true_positives = []
    false_positives = []
    matched_bug_ids = set()

    for r in report.get("results", []):
        if not r.get("anomalies"):
            continue

        endpoint = r.get("endpoint")
        method = r.get("method")
        mutated_field = r.get("mutated_field")

        anomalies = r.get("anomalies", [])
        matched_bug = next(
            (
                b for b in findable_bugs
                if b["endpoint"] == endpoint
                and b["method"] == method
                and b["field"] == mutated_field
                and any(b["expected_anomaly"] in a for a in anomalies)
            ),
            None,
        )

        if matched_bug:
            matched_bug_ids.add(matched_bug["id"])
            true_positives.append({
                "bug_id": matched_bug["id"],
                "endpoint": endpoint,
                "method": method,
                "mutated_field": mutated_field,
                "anomalies": r.get("anomalies"),
            })
        else:
            false_positives.append({
                "endpoint": endpoint,
                "method": method,
                "mutated_field": mutated_field,
                "anomalies": r.get("anomalies"),
            })

    # Bagovi koje alat teorijski MOŽE naći, a nijedan rezultat ga nije pogodio
    false_negatives = [b["id"] for b in findable_bugs if b["id"] not in matched_bug_ids]

    tp_count = len(true_positives)
    fp_count = len(false_positives)
    fn_count = len(false_negatives)

    # Zaštita od deljenja nulom ako nema prijavljenih/nalazivih bagova
    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
    recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "known_unfindable": known_unfindable,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }

# Čitko ispisuje rezultat evaluacije: koji bag je pronađen, koji je promašen,
# koji su lažni pozitivi, i finalne metrike
def print_report(evaluation: dict) -> None:
    print("\n── Ground Truth Evaluacija ───────────────────────────")

    found_ids = sorted({tp["bug_id"] for tp in evaluation["true_positives"]})
    print(f"  Pronađeni bagovi ({len(found_ids)}):")
    for bug_id in found_ids:
        print(f"    ✓ {bug_id}")

    if evaluation["false_negatives"]:
        print(f"\n  Promašeni bagovi ({len(evaluation['false_negatives'])}):")
        for bug_id in evaluation["false_negatives"]:
            print(f"    ✗ {bug_id}")

    if evaluation["false_positives"]:
        print(f"\n  Lažni pozitivi ({len(evaluation['false_positives'])}):")
        for fp in evaluation["false_positives"]:
            print(f"    ? {fp['method']} {fp['endpoint']} (polje: {fp['mutated_field']})")
            for a in fp["anomalies"]:
                print(f"        {a}")

    if evaluation["known_unfindable"]:
        print(f"\n  Poznati, očekivani propusti (alat ih po dizajnu ne može naći):")
        for bug_id in evaluation["known_unfindable"]:
            print(f"    • {bug_id}")

    print(f"\n  Precision: {evaluation['precision']:.4f}")
    print(f"  Recall:    {evaluation['recall']:.4f}")
    print(f"  F1 Score:  {evaluation['f1']:.4f}")
    print("──────────────────────────────────────────────────────\n")

# CLI deo — čita --report i --known-bugs argumente, poziva evaluaciju i
# ispisuje čitljiv rezultat
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Uporedi report.json sa unapred pripremljenom listom poznatih bagova (ground truth)."
    )
    parser.add_argument("--report", required=True, help="Putanja do report.json fajla.")
    parser.add_argument("--known-bugs", required=True, help="Putanja do known_bugs.yaml fajla.")
    args = parser.parse_args()

    try:
        evaluation = evaluate_against_ground_truth(args.report, args.known_bugs)
        print_report(evaluation)
    except FileNotFoundError as exc:
        print(f"GREŠKA: Fajl nije pronađen: {exc}")
        sys.exit(1)
