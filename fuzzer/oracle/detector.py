"""
fuzzer/oracle/detector.py
 
Analizira TestResult objekte i detektuje anomalije.
 
Tri vrste anomalija:
  1. Server Failure  — status kod 5xx ili timeout (status 0)
  2. Contract Mismatch — server vratio 2xx na namerno pogrešan ulaz
  3. Performance Anomaly — odgovor trajao previše dugo
"""
 
from fuzzer.models import TestResult
 
 
# Prag za performance anomaliju u ms
# Ako odgovor traje duže od ovoga — anomalija
PERFORMANCE_THRESHOLD_MS = 2000.0
 
 
def detect(result: TestResult, mutation_type: str = "") -> list[str]:
    """
    Prima jedan TestResult i vraća listu detektovanih anomalija.
 
    Args:
        result:        rezultat jednog HTTP zahtjeva
        mutation_type: tip mutacije koji je bio primijenjen
 
    Returns:
        Lista stringova — svaki string je jedna anomalija.
        Prazna lista znači da nema anomalija.
    """
    anomalies = []
 
    anomalies += _check_server_failure(result)
    anomalies += _check_contract_mismatch(result, mutation_type)
    anomalies += _check_performance(result)
 
    return anomalies
 
 
# ---------------------------------------------------------------------------
# Tri detektora
# ---------------------------------------------------------------------------
 
def _check_server_failure(result: TestResult) -> list[str]:
    """
    Detektuje 5xx greške i timeout.
 
    5xx znači da server nije znao da obradi zahtjev —
    čak i pogrešan ulaz ne bi trebalo da ruši server.
    """
    if result.status_code == 0:
        return ["SERVER_FAILURE: Timeout ili connection error — server nije odgovorio"]
 
    if result.status_code >= 500:
        return [f"SERVER_FAILURE: Status {result.status_code} — server crash na mutiranom ulazu"]
 
    return []
 
 
def _check_contract_mismatch(result: TestResult, mutation_type: str) -> list[str]:
    """
    Detektuje situaciju gdje server vraća 2xx na namerno pogrešan ulaz.
 
    Ovo je bezbednosni propust — server bi trebao da validira ulaz
    i vrati 400 Bad Request, ali umjesto toga prihvata sve.
 
    Primjer:
        Poslali smo title = None (null)
        Server odgovorio sa 201 Created
        → Contract Mismatch! Server nema validaciju.
    """
    if result.status_code is None:
        return []
 
    # Ako je server vratio uspješan odgovor (2xx) na mutiran payload
    if 200 <= result.status_code < 300:
        if mutation_type in ("type_mutation", "structure", "boundary"):
            return [
                f"CONTRACT_MISMATCH: Server vratio {result.status_code} "
                f"na '{mutation_type}' mutaciju polja '{result.mutated_field}' — "
                f"nedostaje validacija ulaza"
            ]
 
    return []
 
 
def _check_performance(result: TestResult) -> list[str]:
    """
    Detektuje spore odgovore.
 
    Ako mutiran ulaz (npr. 10.000 karaktera) izazove
    naglo usporavanje, može ukazivati na neefikasan algoritam
    ili potencijalni DoS.
    """
    if result.response_time_ms > PERFORMANCE_THRESHOLD_MS:
        return [
            f"PERFORMANCE_ANOMALY: Odgovor trajao {result.response_time_ms}ms "
            f"(prag: {PERFORMANCE_THRESHOLD_MS}ms) za polje '{result.mutated_field}'"
        ]
 
    return []
 
 
# ---------------------------------------------------------------------------
# Batch analiza — za cijelu listu rezultata
# ---------------------------------------------------------------------------
 
def analyze_results(results: list[TestResult]) -> list[TestResult]:
    """
    Prima listu TestResult objekata, detektuje anomalije za svaki
    i vraća ažuriranu listu sa popunjenim anomalies poljem.
 
    Args:
        results: lista rezultata od HTTP Runnera
 
    Returns:
        Ista lista, ali sa popunjenim anomalies za svaki rezultat
        koji ima anomaliju.
    """
    for result in results:
        detected = detect(result, mutation_type=result.mutation_type)
 
        # Dodaj nove anomalije (ne briši postojeće — Runner može dodati TIMEOUT)
        for anomaly in detected:
            if anomaly not in result.anomalies:
                result.anomalies.append(anomaly)
 
        # Ako ima anomalija → passed = False
        if result.anomalies:
            result.passed = False
 
    return results
 
 
def summary(results: list[TestResult]) -> dict:
    """
    Vraća kratki summary cijele fuzzing sesije.
 
    Returns:
        Dict sa brojevima: ukupno, passed, failed, anomalije po tipu
    """
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
 