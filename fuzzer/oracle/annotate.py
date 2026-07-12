import json
import argparse
import sys
from pathlib import Path


def prepare_annotation_file(input_path: str, output_path: str) -> int:
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))

    anomalies_only = [
        {
            "endpoint": r["endpoint"],
            "method": r["method"],
            "mutated_field": r["mutated_field"],
            "mutation_type": r["mutation_type"],
            "status_code": r["status_code"],
            "response_time_ms": r["response_time_ms"],
            "anomalies": r["anomalies"],
            "true_positive": None,  # null = nije anotiran | true = TP | false = FP
        }
        for r in data.get("results", [])
        if r.get("anomalies")
    ]

    output = {
        "_instructions": (
            "Za svaki rezultat postavi true_positive: true (stvarni propust) "
            "ili false (lazna uzbuna). "
            "Na kraju dodaj false_negatives: N (propusti koje fuzzer nije pronasao)."
        ),
        "api": data.get("api", ""),
        "total_tests": data.get("summary", {}).get("total", 0),
        "anomaly_count": len(anomalies_only),
        "false_negatives": 0,
        "results": anomalies_only,
    }

    Path(output_path).write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return len(anomalies_only)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pripremi fajl za rucnu anotaciju (F1 Score evaluacija)."
    )
    parser.add_argument("--input", required=True, help="Putanja do report.json.")
    parser.add_argument("--output", default="annotate.json", help="Izlazni fajl.")
    args = parser.parse_args()

    try:
        count = prepare_annotation_file(args.input, args.output)
        print(f"Kreirano: {args.output}")
        print(f"Anomalija za anotaciju: {count}")
        print(f"\nSledeci korak: otvori '{args.output}' i za svaki unos postavi:")
        print('  "true_positive": true   — ako je stvarni bezbednosni propust')
        print('  "true_positive": false  — ako je lazna uzbuna')
        print(f'\nNa kraju dodaj "false_negatives": N (propusti koje fuzzer nije uhvatio)')
        print(f"\nZatim pokreni:")
        print(f"  python3 -m fuzzer.oracle.f1_score --ground-truth {args.output}")
    except FileNotFoundError:
        print(f"GREŠKA: Fajl nije pronađen: {args.input}")
        sys.exit(1)
