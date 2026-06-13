"""
fuzzer/runner/http_runner.py
 
Uzima TestScenario objekte i šalje ih kao HTTP zahtjeve ka API-ju.
Mjeri vrijeme odgovora i vraća TestResult objekte.
"""
 
import time
import httpx
 
from fuzzer.models import TestResult
from fuzzer.generator.scenario_generator import TestScenario
 
 
# Timeout u sekundama — koliko čekamo na odgovor prije nego odustanemo
DEFAULT_TIMEOUT = 10.0
 
 
def _build_url(base_url: str, path: str, path_params: dict) -> str:
    """
    Spaja base_url i path, i zamjenjuje {parametre} stvarnim vrednostima.
 
    Primer:
        base_url = "http://localhost:8080"
        path = "/books/{bookId}"
        path_params = {"bookId": 1}
        → "http://localhost:8080/books/1"
    """
    # Zamijeni svaki {param} u pathu sa stvarnom vrijednošću
    for param_name, param_value in path_params.items():
        path = path.replace(f"{{{param_name}}}", str(param_value))
 
    # Ukloni dupli slash ako postoji
    base_url = base_url.rstrip("/")
    return base_url + path
 
 
def _build_headers(token: str | None) -> dict:
    """
    Pravi HTTP headere.
    Ako token počinje sa 'JSESSIONID=' — šalje se kao Cookie.
    Inače se šalje kao Bearer token.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        if token.startswith("JSESSIONID="):
            headers["Cookie"] = token
        else:
            headers["Authorization"] = f"Bearer {token}"
    return headers
 
def run_scenario(
    scenario: TestScenario,
    base_url: str,
    token: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> TestResult:
    """
    Izvršava jedan TestScenario — šalje HTTP zahtjev i vraća TestResult.
 
    Args:
        scenario:  jedan test scenario od Generatora
        base_url:  adresa API-ja, npr. "http://localhost:8080"
        token:     opcioni Bearer token
        timeout:   koliko sekundi čekamo na odgovor
 
    Returns:
        TestResult sa status kodom, vremenom odgovora i payloadom.
    """
    url = _build_url(base_url, scenario.endpoint, scenario.path_params)
    headers = _build_headers(token)
 
    status_code = 0
    response_time_ms = 0.0
    error_message = None
 
    try:
        start = time.perf_counter()
 
        with httpx.Client(timeout=timeout) as client:
            if scenario.method == "GET":
                response = client.get(url, headers=headers, params=scenario.query_params)
            elif scenario.method == "POST":
                response = client.post(url, headers=headers, json=scenario.payload)
            elif scenario.method == "PUT":
                response = client.put(url, headers=headers, json=scenario.payload)
            elif scenario.method == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                # Ne bi trebalo da se desi — Generator filtrira metode
                raise ValueError(f"Nepodržana metoda: {scenario.method}")
 
        end = time.perf_counter()
        response_time_ms = (end - start) * 1000
        status_code = response.status_code
 
    except httpx.TimeoutException:
        # Server nije odgovorio na vrijeme — bilježimo kao timeout
        response_time_ms = timeout * 1000
        status_code = 0
        error_message = "TIMEOUT"
 
    except httpx.ConnectError:
        # Server nije dostupan
        status_code = 0
        error_message = "CONNECTION_ERROR"
 
    except Exception as exc:
        status_code = 0
        error_message = str(exc)
 
    return TestResult(
        endpoint=scenario.endpoint,
        method=scenario.method,
        status_code=status_code,
        response_time_ms=round(response_time_ms, 2),
        payload=scenario.payload,
        mutation_type=scenario.mutation_type,
        mutated_field=scenario.mutated_field,
        anomalies=[error_message] if error_message else [],
        passed=status_code < 500,
    )
 
 
def run_all(
    scenarios: list[TestScenario],
    base_url: str,
    token: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[TestResult]:
    """
    Izvršava sve scenarije jedan po jedan i vraća listu rezultata.
 
    Args:
        scenarios:  lista TestScenario objekata od Generatora
        base_url:   adresa API-ja
        token:      opcioni Bearer token
        timeout:    timeout po zahtjevu u sekundama
 
    Returns:
        Lista TestResult objekata — jedan po scenariju.
    """
    results = []
    total = len(scenarios)
 
    for i, scenario in enumerate(scenarios, start=1):
        print(f"[{i}/{total}] {scenario.method} {scenario.endpoint} — {scenario.description[:60]}")
 
        result = run_scenario(scenario, base_url, token, timeout)
        results.append(result)
 
        # Kratki ispis rezultata
        status_str = str(result.status_code) if result.status_code else "ERR"
        print(f"         → {status_str} ({result.response_time_ms}ms)")
 
    return results
 