from fuzzer.models import TestResult

# Odgovori sporiji od ovog praga ukazuju na potencijalni DoS vektor
PERFORMANCE_THRESHOLD_MS = 2000.0


def detect(result: TestResult, mutation_type: str = "") -> list[str]:
    anomalies = []
    anomalies += _check_server_failure(result)
    anomalies += _check_contract_mismatch(result, mutation_type)
    anomalies += _check_performance(result)
    return anomalies


def _check_server_failure(result: TestResult) -> list[str]:
    if result.status_code == 0:
        return ["SERVER_FAILURE: Timeout ili connection error — server nije odgovorio"]
    if result.status_code >= 500:
        return [f"SERVER_FAILURE: Status {result.status_code} — server crash na mutiranom ulazu"]
    return []


def _check_contract_mismatch(result: TestResult, mutation_type: str) -> list[str]:
    if result.status_code is None:
        return []
    # 2xx na namerno pogrešan ulaz znači da server nema validaciju
    if 200 <= result.status_code < 300:
        if mutation_type in ("type_mutation", "structure", "boundary"):
            return [
                f"CONTRACT_MISMATCH: Server vratio {result.status_code} "
                f"na '{mutation_type}' mutaciju polja '{result.mutated_field}' — "
                f"nedostaje validacija ulaza"
            ]
    return []


def _check_performance(result: TestResult) -> list[str]:
    if result.response_time_ms > PERFORMANCE_THRESHOLD_MS:
        return [
            f"PERFORMANCE_ANOMALY: Odgovor trajao {result.response_time_ms}ms "
            f"(prag: {PERFORMANCE_THRESHOLD_MS}ms) za polje '{result.mutated_field}'"
        ]
    return []


def analyze_results(results: list[TestResult]) -> list[TestResult]:
    for result in results:
        detected = detect(result, mutation_type=result.mutation_type)
        for anomaly in detected:
            if anomaly not in result.anomalies:
                result.anomalies.append(anomaly)
        if result.anomalies:
            result.passed = False
    return results


def summary(results: list[TestResult]) -> dict:
    total = len(results)
    failed = [r for r in results if not r.passed]
    server_failures = [r for r in failed if any("SERVER_FAILURE" in a for a in r.anomalies)]
    contract_mismatches = [r for r in failed if any("CONTRACT_MISMATCH" in a for a in r.anomalies)]
    performance = [r for r in failed if any("PERFORMANCE_ANOMALY" in a for a in r.anomalies)]

    return {
        "total": total,
        "passed": total - len(failed),
        "failed": len(failed),
        "server_failures": len(server_failures),
        "contract_mismatches": len(contract_mismatches),
        "performance_anomalies": len(performance),
    }
