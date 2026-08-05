from dataclasses import dataclass, field
from typing import Any

from fuzzer.models import EndpointModel
from fuzzer.generator.mutation_catalog import get_mutations

#jedan konkretan test zahtev koji će fuzzer poslati ka API-ju
@dataclass
class TestScenario:
    endpoint: str
    method: str
    payload: dict
    path_params: dict
    query_params: dict
    header_params: dict
    mutation_type: str #vrsta mutacije (npr. "type_mutation", "boundary", "structure")
    mutated_field: str #koje polje je namerno "pokvareno"
    description: str = ""
    request_schema: dict = field(default_factory=dict)

# Po jedna validna vrednost za svaki tip — koristi se da osnovni zahtev bude
# potpuno ispravan, tako da se u testu menja samo jedno ciljano polje.
_VALID_DEFAULTS: dict[str, Any] = {
    "string": "test_value",
    "integer": 1,
    "number": 1.0,
    "boolean": True,
    "array": [],
    "object": {},
    "unknown": "test",
}

#vraća validnu vrednost za dati tip iz _VALID_DEFAULTS, a ako tip nije prepoznat, vraća 'test' kao rezervnu vrednost
def _default_value(schema_type: str) -> Any:
    return _VALID_DEFAULTS.get(schema_type, "test")

# Pravi validnu vrednost za polje koristeći raw šemu (enum/format/minimum) ako
# je dostupna, a inače pada nazad na generički _default_value po tipu
def _default_value_from_schema(field_type: str, field_raw_schema: dict) -> Any:
    if field_raw_schema.get("enum"):
        return field_raw_schema["enum"][0]
    if field_raw_schema.get("format") == "email":
        return "user@example.com"
    if field_raw_schema.get("format") in ("date", "date-time"):
        return "2024-01-01" if field_raw_schema["format"] == "date" else "2024-01-01T00:00:00Z"
    if "minimum" in field_raw_schema and field_type in ("integer", "number"):
        return field_raw_schema["minimum"]
    return _default_value(field_type)

# Pravi osnovno validno telo zahteva — svaki par (ime, tip) iz šeme
# postaje (ime, validna_vrednost_tog_tipa) u novom rečniku, koristeći raw
# šemu polja (enum/format/minimum) kad je dostupna
def _build_base_payload(endpoint: EndpointModel) -> dict:
    properties = endpoint.raw_request_schema.get("properties", {})
    return {
        f: _default_value_from_schema(t, properties.get(f, {}))
        for f, t in endpoint.request_schema.items()
    }

# Pravi rečnik validnih vrednosti za sve path parametre endpoint-a
def _build_base_path_params(endpoint: EndpointModel) -> dict:
    return {p.name: _default_value(p.schema_type) for p in endpoint.path_params}

# Pravi rečnik validnih vrednosti za sve query parametre endpoint-a
def _build_base_query_params(endpoint: EndpointModel) -> dict:
    return {p.name: _default_value(p.schema_type) for p in endpoint.query_params}

# Pravi rečnik validnih vrednosti za sve header parametre endpoint-a
def _build_base_header_params(endpoint: EndpointModel) -> dict:
    return {p.name: _default_value(p.schema_type) for p in endpoint.header_params}


# Za svako polje tela zahteva, isprobava sve loše vrednosti tog tipa iz kataloga —
# menja SAMO to jedno polje u kopiji validnog payload-a, dok ostalo ostaje ispravno,
# i pravi po jedan TestScenario za svaku kombinaciju (polje, loša vrednost)
def _generate_field_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    scenarios = []
    base = _build_base_payload(endpoint)
    path_params = _build_base_path_params(endpoint)
    query_params = _build_base_query_params(endpoint)
    header_params = _build_base_header_params(endpoint)

    for field_name, field_type in endpoint.request_schema.items():
        for bad_value in get_mutations(field_type):
            mutated = base.copy()  # kopija da se ne pokvari originalna baza
            mutated[field_name] = bad_value # menja se samo jedno polje
            scenarios.append(TestScenario(
                endpoint=endpoint.path,
                method=endpoint.method,
                payload=mutated,
                path_params=path_params,
                query_params=query_params,
                header_params=header_params,
                mutation_type="type_mutation" if not isinstance(bad_value, str) else "boundary",
                mutated_field=field_name,
                description=f"'{field_name}' ({field_type}) = {repr(bad_value)[:50]}",
                request_schema=endpoint.raw_request_schema,
            ))

    return scenarios

# Testira strukturu zahteva: 
# 1) izostavlja svako obavezno polje (jedno po jedno) — proverava da li API to odbija
# 2) dodaje nepostojeće polje koje nije u spec-u — proverava da li API ga ignoriše
# 3) dodavanje duboko ugnježdenog objekta (8 nivoa) — stres test parsera
def _generate_structure_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    scenarios = []
    base = _build_base_payload(endpoint)
    path_params = _build_base_path_params(endpoint)
    query_params = _build_base_query_params(endpoint)
    header_params = _build_base_header_params(endpoint)

    for required_field in endpoint.required_fields:
        scenarios.append(TestScenario(
            endpoint=endpoint.path,
            method=endpoint.method,
            payload={k: v for k, v in base.items() if k != required_field},
            path_params=path_params,
            query_params=query_params,
            header_params=header_params,
            mutation_type="structure",
            mutated_field=required_field,
            description=f"Nedostaje required polje '{required_field}'",
            request_schema=endpoint.raw_request_schema,
        ))

    scenarios.append(TestScenario(
        endpoint=endpoint.path,
        method=endpoint.method,
        payload={**base, "__extra_field__": "unexpected_value"},
        path_params=path_params,
        query_params=query_params,
        header_params=header_params,
        mutation_type="structure",
        mutated_field="__extra_field__",
        description="Nepostojece polje koje nije u spec-u",
        request_schema=endpoint.raw_request_schema,
    ))

    
    scenarios.append(TestScenario(
        endpoint=endpoint.path,
        method=endpoint.method,
        payload={**base, "__deep_nest__": {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": "deep"}}}}}}}}},
        path_params=path_params,
        query_params=query_params,
        header_params=header_params,
        mutation_type="structure",
        mutated_field="__deep_nest__",
        description="8 nivoa nestovanja",
        request_schema=endpoint.raw_request_schema,
    ))

    return scenarios

# Za svaki path parametar (deo URL putanje), isprobava sve loše vrednosti tog
# tipa iz kataloga — menja SAMO taj jedan parametar, telo ostaje validno
# (baseline) jer se ovde testira samo path parametar
def _generate_path_param_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    scenarios = []
    base_payload = _build_base_payload(endpoint)
    base_path = _build_base_path_params(endpoint)
    base_query = _build_base_query_params(endpoint)
    base_headers = _build_base_header_params(endpoint)

    for param in endpoint.path_params:
        for bad_value in get_mutations(param.schema_type):
            scenarios.append(TestScenario(
                endpoint=endpoint.path,
                method=endpoint.method,
                payload=base_payload,
                path_params={**base_path, param.name: bad_value},
                query_params=base_query,
                header_params=base_headers,
                mutation_type="type_mutation",
                mutated_field=param.name,
                description=f"Path param '{param.name}' = {repr(bad_value)[:50]}",
            ))

    return scenarios

# Za svaki query parametar, isprobava sve loše vrednosti tog tipa —
# menja SAMO taj parametar, telo zahteva ostaje validno i prisutno
# (za razliku od path parametara, ovde se telo ne prazni)
def _generate_query_param_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    scenarios = []
    base_payload = _build_base_payload(endpoint)
    base_path = _build_base_path_params(endpoint)
    base_query = _build_base_query_params(endpoint)
    base_headers = _build_base_header_params(endpoint)

    for param in endpoint.query_params:
        for bad_value in get_mutations(param.schema_type):
            scenarios.append(TestScenario(
                endpoint=endpoint.path,
                method=endpoint.method,
                payload=base_payload,
                path_params=base_path,
                query_params={**base_query, param.name: bad_value},
                header_params=base_headers,
                mutation_type="type_mutation" if not isinstance(bad_value, str) else "boundary",
                mutated_field=param.name,
                description=f"Query param '{param.name}' = {repr(bad_value)[:50]}",
            ))

    return scenarios

# Za svaki header parametar (HTTP zaglavlje), isprobava sve loše vrednosti
# tog tipa — menja SAMO taj header, telo i ostali parametri ostaju validni
def _generate_header_param_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    scenarios = []
    base_payload = _build_base_payload(endpoint)
    base_path = _build_base_path_params(endpoint)
    base_query = _build_base_query_params(endpoint)
    base_headers = _build_base_header_params(endpoint)

    for param in endpoint.header_params:
        for bad_value in get_mutations(param.schema_type):
            scenarios.append(TestScenario(
                endpoint=endpoint.path,
                method=endpoint.method,
                payload=base_payload,
                path_params=base_path,
                query_params=base_query,
                header_params={**base_headers, param.name: bad_value},
                mutation_type="type_mutation" if not isinstance(bad_value, str) else "boundary",
                mutated_field=param.name,
                description=f"Header param '{param.name}' = {repr(bad_value)[:50]}",
            ))

    return scenarios

# Pravi jedan potpuno validan, nemutirani zahtev za endpoint — kontrolni
# (baseline) scenario za poređenje sa rezultatima mutacija
def _generate_baseline_scenario(endpoint: EndpointModel) -> TestScenario:
    return TestScenario(
        endpoint=endpoint.path,
        method=endpoint.method,
        payload=_build_base_payload(endpoint),
        path_params=_build_base_path_params(endpoint),
        query_params=_build_base_query_params(endpoint),
        header_params=_build_base_header_params(endpoint),
        mutation_type="baseline",
        mutated_field="__baseline__",
        description="Kontrolni (baseline) zahtev — validan po specifikaciji",
        request_schema=endpoint.raw_request_schema,
    )

# Za svaki endpoint generiše sve relevantne mutacije (telo, path, query,
# header) i vraća jedinstvenu listu svih test scenarija za ceo API
def generate_scenarios(endpoints: list[EndpointModel]) -> list[TestScenario]:
    all_scenarios = []

    for endpoint in endpoints:
        # Kontrolni zahtev — uvek prvi u listi za ovaj endpoint
        all_scenarios.append(_generate_baseline_scenario(endpoint))
         # Ima telo zahteva — testiraj vrednosti polja i strukturu (obavezna/nepoznata polja)
        if endpoint.request_schema:
            all_scenarios += _generate_field_mutations(endpoint)
            all_scenarios += _generate_structure_mutations(endpoint)
         # Ima path parametre — testiraj loše vrednosti u putanji
        if endpoint.path_params:
            all_scenarios += _generate_path_param_mutations(endpoint)
        # Ima query parametre — testiraj loše vrednosti u query stringu
        if endpoint.query_params:
            all_scenarios += _generate_query_param_mutations(endpoint)
        # Ima header parametre — testiraj loše vrednosti u zaglavljima
        if endpoint.header_params:
            all_scenarios += _generate_header_param_mutations(endpoint)

    return all_scenarios
