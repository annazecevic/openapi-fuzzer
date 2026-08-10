# Glavna ulazna tačka fuzzer alata — čita argumente iz komandne linije i
# redom pokreće ceo tok kroz 5 koraka: parsiranje spec-a, generisanje test
# scenarija, izvršavanje HTTP testova, analizu rezultata (detekcija anomalija),
# i generisanje HTML/JSON/PDF izveštaja. Vraća statusni kod (0/1/2) zavisno
# od toga da li je sve prošlo uspešno, pronađene su anomalije, ili je pukla
# greška pri pokretanju — radi lakše integracije u automatizovane procese.

import argparse
import sys
from pathlib import Path

from fuzzer.parser import parse_file, OpenAPIValidationError
from fuzzer.generator.scenario_generator import generate_scenarios
from fuzzer.runner.http_runner import run_all
from fuzzer.oracle.detector import analyze_results, summary
from fuzzer.reporter.report_generator import generate_html, generate_json, generate_pdf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fuzzer",
        description="OpenAPI REST API Fuzzer — automatsko fuzz testiranje na osnovu OpenAPI spec-a.",
    )
    parser.add_argument("--spec", required=True, help="Putanja do OpenAPI 3.x YAML ili JSON fajla.")
    parser.add_argument("--url", required=True, help="Base URL ciljnog API-ja, npr. http://localhost:8080")
    parser.add_argument("--token", default=None, help="Opcioni Bearer token za autentifikaciju.")
    parser.add_argument("--output-dir", default=".", help="Folder gde se snimaju izveštaji (default: trenutni folder).")
    parser.add_argument("--rate-limit", type=float, default=0.0, help="Maksimalan broj zahteva u sekundi, 0 = bez ograničenja")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout po HTTP zahtevu u sekundama (default: 10).")
    parser.add_argument("--concurrency", type=int, default=1, help="Broj paralelnih HTTP zahteva (default: 1).")
    parser.add_argument("--pdf", action="store_true", default=False, help="Generiši i PDF izveštaj (zahteva: pip install xhtml2pdf).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(f"[1/5] Parsiranje OpenAPI spec-a: {args.spec}")
    try:
        spec = parse_file(args.spec)
    except FileNotFoundError as exc:
        print(f"GREŠKA: {exc}")
        return 2
    except OpenAPIValidationError as exc:
        print(f"GREŠKA: {exc}")
        return 2

    print(f"      {spec.summary()}")

    if spec.resource_links:
        print(f"      Otkriveno {len(spec.resource_links)} zavisnosti između endpointa:")
        for link in spec.resource_links:
            print(f"        {link.producer_method} {link.producer_endpoint} "
                  f"[{link.producer_field}] → {link.consumer_endpoint} [{link.consumer_param}]")

    print(f"\n[2/5] Generisanje test scenarija...")
    scenarios = generate_scenarios(spec.endpoints)
    print(f"      Generisano {len(scenarios)} scenarija")

    if spec.resource_links:
        print(f"      Povezivanje zavisnih resursa (stvaran ID umesto podrazumevanog)...")
        for link in spec.resource_links:
            producer_label = f"{link.producer_method} {link.producer_endpoint}"

            baseline = next(
                (s for s in scenarios
                 if s.endpoint == link.producer_endpoint
                 and s.method == link.producer_method
                 and s.mutation_type == "baseline"),
                None,
            )

            real_value = None
            if baseline is not None:
                producer_results = run_all(
                    [baseline],
                    base_url=args.url,
                    token=args.token,
                    timeout=args.timeout,
                    concurrency=1,
                    requests_per_second=args.rate_limit,
                )
                producer_result = producer_results[0]
                if 200 <= producer_result.status_code < 300 and isinstance(producer_result.response_json, dict):
                    real_value = producer_result.response_json.get(link.producer_field)

            if real_value is None:
                print(f"      Nije uspelo povezivanje {producer_label} → "
                      f"{link.consumer_endpoint}, koriste se podrazumevane vrednosti")
                continue

            for scenario in scenarios:
                if scenario.endpoint != link.consumer_endpoint:
                    continue
                if scenario.mutated_field == link.consumer_param:
                    continue
                if link.consumer_param in scenario.path_params:
                    scenario.path_params[link.consumer_param] = real_value

    print(f"\n[3/5] Izvršavanje fuzz testova na: {args.url} "
          f"(konkurentnost: {args.concurrency})")

    def on_progress(done: int, total: int, result) -> None:
        status_str = str(result.status_code) if result.status_code else "ERR"
        print(f"      [{done}/{total}] {result.method} {result.endpoint} "
              f"({result.mutation_type}: {result.mutated_field}) → {status_str}")

    results = run_all(
        scenarios,
        base_url=args.url,
        token=args.token,
        timeout=args.timeout,
        concurrency=args.concurrency,
        requests_per_second=args.rate_limit,
        progress_cb=on_progress,
    )

    print(f"\n[4/5] Analiza rezultata...")
    results = analyze_results(results)
    stats = summary(results)

    total_endpoints = len(spec.endpoints)
    tested_endpoints = len(set((s.endpoint, s.method) for s in scenarios))
    coverage_pct = (tested_endpoints / total_endpoints * 100) if total_endpoints > 0 else 0.0
    stats["coverage_pct"] = round(coverage_pct, 1)
    stats["tested_endpoints"] = tested_endpoints
    stats["total_endpoints"] = total_endpoints

    print(f"      Ukupno:               {stats['total']}")
    print(f"      Prošlo:               {stats['passed']}")
    print(f"      Anomalija:            {stats['failed']}")
    print(f"        - Server Failure:     {stats['server_failures']}")
    print(f"        - Contract Mismatch:  {stats['contract_mismatches']}")
    print(f"        - Response Contract:  {stats['response_contract_mismatches']}")
    print(f"        - Performance:        {stats['performance_anomalies']}")
    print(f"      Nepouzdani rezultati: {stats['unreliable_results']} (baseline pao)")
    print(f"      API Coverage:         {tested_endpoints}/{total_endpoints} endpointa ({coverage_pct:.1f}%)")

    print(f"\n[5/5] Generisanje izveštaja...")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generate_html(results, stats, api_title=spec.title, api_version=spec.version,
                  output_path=str(output_dir / "report.html"))
    generate_json(results, stats, api_title=spec.title,
                  output_path=str(output_dir / "report.json"))

    if args.pdf:
        try:
            generate_pdf(results, stats, api_title=spec.title, api_version=spec.version,
                         output_path=str(output_dir / "report.pdf"))
        except RuntimeError as exc:
            print(f"      UPOZORENJE: PDF nije generisan — {exc}")

    if stats["failed"] > 0:
        print(f"\n⚠ Pronađeno {stats['failed']} anomalija.")
        return 1

    print(f"\n✓ Nema anomalija.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
