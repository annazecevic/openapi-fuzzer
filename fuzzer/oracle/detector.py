import jsonschema

from fuzzer.models import TestResult


PERFORMANCE_THRESHOLD_MS = 2000.0 # prag iznad kog se vreme odgovora smatra problemom

# Za jedan rezultat, proverava sve tri vrste anomalija i vraća listu problema
def detect(result: TestResult) -> list[str]:
    anomalies = []
    anomalies += _check_server_failure(result)
    anomalies += _check_contract_mismatch(result)
    anomalies += _check_performance(result)
    return anomalies

# Anomalija ako server nije odgovorio (timeout/konekcija) ili je pukao (5xx) —
# CLIENT_ERROR se ne broji, to je greška na strani fuzzera, ne servera
def _check_server_failure(result: TestResult) -> list[str]:
    if result.status_code >= 500:
        return [f"SERVER_FAILURE: Status {result.status_code} — server crash na mutiranom ulazu"]
    if result.error_category == "TIMEOUT":
        return ["SERVER_FAILURE: Timeout — server nije odgovorio na vreme"]
    if result.error_category == "CONNECT_ERROR":
        return ["SERVER_FAILURE: Konekcija odbijena — server verovatno pao"]
    return []

# Anomalija ako server vratio 2xx na payload koji krši OpenAPI šemu — proverava se
# pravom JSON Schema validacijom, ne heuristikom po tipu mutacije
def _check_contract_mismatch(result: TestResult) -> list[str]:
    if not (200 <= result.status_code < 300):
        return []

    if not result.request_schema:
        return []

    try:
        jsonschema.validate(instance=result.payload, schema=result.request_schema)
    except jsonschema.ValidationError as e:
        return [
            f"CONTRACT_MISMATCH: Server vratio {result.status_code} na payload koji "
            f"krši šemu ({e.message}) — polje '{result.mutated_field}'"
        ]

    return []

# Anomalija ako je vreme odgovora prešlo prag od 2 sekunde
def _check_performance(result: TestResult) -> list[str]:
    if result.response_time_ms > PERFORMANCE_THRESHOLD_MS:
        return [
            f"PERFORMANCE_ANOMALY: Odgovor trajao {result.response_time_ms}ms "
            f"(prag: {PERFORMANCE_THRESHOLD_MS}ms) za polje '{result.mutated_field}'"
        ]
    return []

# Za svaki (endpoint, method), proverava da li je njegov baseline (kontrolni)
# zahtev prošao bez anomalija — koristi se da se rezultati mutacija označe
# kao nepouzdani kad je već i sam validan zahtev pukao
def check_baselines(results: list[TestResult]) -> dict[tuple[str, str], bool]:
    baselines = {}
    for r in results:
        if r.mutation_type == "baseline":
            ok = (200 <= r.status_code < 300) and not r.anomalies
            baselines[(r.endpoint, r.method)] = ok
    return baselines

# Primenjuje detekciju na celu listu rezultata, dodaje anomalije bez dupliranja,
# ispravlja passed status ako je pronađen bilo kakav problem
def analyze_results(results: list[TestResult]) -> list[TestResult]:
    for result in results:
        detected = detect(result)
        for anomaly in detected:
            if anomaly not in result.anomalies:
                result.anomalies.append(anomaly)
        if result.anomalies:
            result.passed = False

    baseline_status = check_baselines(results)
    for r in results:
        if r.mutation_type == "baseline":
            continue
        key = (r.endpoint, r.method)
        if key in baseline_status and not baseline_status[key]:
            r.baseline_valid = False

    return results

# Pravi statistički pregled — ukupno/prošlo/palo, i broj svake vrste anomalije
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
        "unreliable_results": sum(1 for r in results if not r.baseline_valid and r.mutation_type != "baseline"),
    }
