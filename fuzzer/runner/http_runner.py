import asyncio
import time
from collections.abc import Callable

import httpx

from fuzzer.models import TestResult
from fuzzer.generator.scenario_generator import TestScenario


DEFAULT_TIMEOUT = 10.0

# Ubacuje stvarne vrednosti umesto {placeholder}-a u putanji (npr. {id} -> 42)
# i spaja je sa osnovnim URL-om
def _build_url(base_url: str, path: str, path_params: dict) -> str:
    for param_name, param_value in path_params.items():
        path = path.replace(f"{{{param_name}}}", str(param_value))
    return base_url.rstrip("/") + path

# Pravi HTTP zaglavlja — Content-Type/Accept su uvek tu, token se stavlja
# kao Cookie ili Bearer u zavisnosti od oblika, plus dodatna zaglavlja iz scenarija
def _build_headers(token: str | None, extra_headers: dict | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        if token.startswith("JSESSIONID="):
            headers["Cookie"] = token
        else:
            headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        for name, value in extra_headers.items():
            headers[str(name)] = str(value)
    return headers

# Šalje jedan HTTP zahtev na osnovu scenarija, meri vreme, hvata greške
# (timeout/connection/ostalo), i vraća TestResult sa svim prikupljenim podacima
async def _run_one(
    scenario: TestScenario,
    client: httpx.AsyncClient,
    token: str | None,
    timeout: float,
    semaphore: asyncio.Semaphore,
    delay: float,
) -> TestResult:
    
    # Pravi konačan URL i zaglavlja za ovaj konkretan test
    url = _build_url(client.base_url.raw_path.decode(), scenario.endpoint, scenario.path_params)
    extra_headers = getattr(scenario, "header_params", {}) or {}
    headers = _build_headers(token, extra_headers)

 # Podrazumevane/neutralne vrednosti pre nego što se stvarno popune
    status_code = 0
    response_time_ms = 0.0
    response_body: str | None = None
    response_size_bytes = 0
    error_message = None

# Semafor ograničava koliko se zahteva izvršava istovremeno
    async with semaphore:
        try:
            start = time.perf_counter()
            # Bira se HTTP metoda i šalje se zahtev
            if scenario.method == "GET":
                response = await client.get(url, headers=headers, params=scenario.query_params)
            elif scenario.method == "POST":
                response = await client.post(url, headers=headers, json=scenario.payload)
            elif scenario.method == "PUT":
                response = await client.put(url, headers=headers, json=scenario.payload)
            elif scenario.method == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Nepodržana metoda: {scenario.method}")
            

            # Vreme trajanja (koristi se za performance anomaliju) 
            response_time_ms = (time.perf_counter() - start) * 1000
            status_code = response.status_code # koristi se za server failure anomaliju
            response_size_bytes = len(response.content)
            try:
                response_body = response.text[:2000] # skraćeno, da se ne troši memorija
            except Exception:
                response_body = "<binary>"  # odgovor nije tekstualan

        except httpx.TimeoutException:
            # Server nije odgovorio u zadatom roku
            response_time_ms = timeout * 1000
            status_code = 0
            error_message = "TIMEOUT"

        except httpx.ConnectError:
            # Konekcija sa serverom nije uspela da se uspostavi
            status_code = 0
            error_message = "CONNECTION_ERROR"

        except Exception as exc:
             # Bilo koja druga neočekivana greška (npr. nepodržana metoda)
            status_code = 0
            error_message = str(exc)

        # Opciono usporavanje između zahteva, da se server ne preplavi  
        if delay > 0:
            await asyncio.sleep(delay)

# Pakuje sve prikupljene podatke u finalni rezultat testa
    return TestResult(
        endpoint=scenario.endpoint,
        method=scenario.method,
        status_code=status_code,
        response_time_ms=round(response_time_ms, 2),
        payload=scenario.payload,
        response_body=response_body,
        response_size_bytes=response_size_bytes,
        mutation_type=scenario.mutation_type,
        mutated_field=scenario.mutated_field,
        anomalies=[error_message] if error_message else [],
        passed=status_code < 500,
        request_schema=scenario.request_schema,
    )

# Paralelno pokreće sve test scenarije (semafor ograničava broj istovremenih
# zahteva), bezbedno prati napredak preko lock-a, čuva originalni redosled
async def _run_all_async(
    scenarios: list[TestScenario],
    base_url: str,
    token: str | None,
    timeout: float,
    concurrency: int,
    delay: float,
    progress_cb: Callable | None,
) -> list[TestResult]:
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0
    lock = asyncio.Lock() # sprečava da dva zadatka istovremeno menjaju "completed"

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        # Izvršava jedan scenario i bezbedno javlja napredak    
        async def run_and_report(scenario: TestScenario) -> TestResult:
            nonlocal completed
            result = await _run_one(scenario, client, token, timeout, semaphore, delay)
            async with lock:
                completed += 1
                if progress_cb:
                    progress_cb(completed, len(scenarios), result)
            return result

        # asyncio.gather čuva redosled
        results = await asyncio.gather(*[run_and_report(s) for s in scenarios])

    return list(results)

# Javna, sinhrona funkcija koja pokreće testiranje — unutra koristi
# asyncio.run da izvrši sve scenarije paralelno
def run_all(
    scenarios: list[TestScenario],
    base_url: str,
    token: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    concurrency: int = 1,
    delay: float = 0.0,
    progress_cb: Callable | None = None,
) -> list[TestResult]:
    return asyncio.run(
        _run_all_async(scenarios, base_url, token, timeout, concurrency, delay, progress_cb)
    )
