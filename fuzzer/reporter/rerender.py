# Ponovo generiše HTML izveštaj iz postojećeg report.json fajla, bez
# ponovnog pokretanja fuzzera — korisno za stare izveštaje (npr. WebGoat,
# Spotify) čiji servisi više nisu lako dostupni. Pokretanje:
#
#   python -m fuzzer.reporter.rerender --report reports/webgoat/report.json \
#       --output reports/webgoat/report.html

import argparse
import json
from pathlib import Path

from fuzzer.models import TestResult
from fuzzer.reporter.report_generator import generate_html


# Učitava report.json i vraća (rezultati, summary, naziv API-ja, verzija API-ja).
# Stari izveštaji nemaju ključ "not_executed" u summary-ju, pa se on ovde
# računa iz rezultata na isti način kao u detector.summary()
def load_report(path: str, default_version: str = "1.0.0") -> tuple[list[TestResult], dict, str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    results = [TestResult.model_validate(item) for item in data.get("results", [])]

    summary = dict(data.get("summary", {}))
    if "not_executed" not in summary:
        summary["not_executed"] = sum(
            1 for r in results if r.passed and r.error_category == "CLIENT_ERROR"
        )

    api_title = data.get("api") or "Unknown API"
    api_version = data.get("version") or default_version
    return results, summary, api_title, api_version


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Ponovo generiše HTML izveštaj iz postojećeg report.json fajla."
    )
    parser.add_argument("--report", required=True, help="putanja do report.json")
    parser.add_argument("--output", required=True, help="putanja do izlaznog report.html")
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="verzija API-ja ako je nema u JSON-u (podrazumevano 1.0.0)",
    )
    args = parser.parse_args(argv)

    results, summary, api_title, api_version = load_report(args.report, args.version)
    generate_html(results, summary, api_title, api_version, args.output)


if __name__ == "__main__":
    main()
