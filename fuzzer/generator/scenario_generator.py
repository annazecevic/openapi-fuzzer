"""
fuzzer/generator/scenario_generator.py
 
Prima listu EndpointModel objekata i generiše sve test scenarije.
Svaki scenario = jedan HTTP zahtjev sa jednim pokvarenim poljem.
"""
 
from dataclasses import dataclass, field
from typing import Any
 
from fuzzer.models import EndpointModel
from fuzzer.generator.mutation_catalog import get_mutations
 
 
# ---------------------------------------------------------------------------
# TestScenario — jedan spreman HTTP zahtjev
# ---------------------------------------------------------------------------
 
@dataclass
class TestScenario:
    endpoint: str           # npr. "/users"
    method: str             # npr. "POST"
    payload: dict           # JSON body koji šaljemo
    path_params: dict       # npr. {"bookId": 1}
    query_params: dict      # npr. {"limit": 10}
    mutation_type: str      # "boundary", "type_mutation", "structure"
    mutated_field: str      # koje polje smo pokvarili, npr. "username"
    description: str = ""   # kratko objašnjenje šta ovaj scenario testira
 
 
# ---------------------------------------------------------------------------
# Validne default vrednosti po tipu
# Koristimo ih za polja koja NE mutiramo u tom scenariju
# ---------------------------------------------------------------------------
 
_VALID_DEFAULTS: dict[str, Any] = {
    "string": "test_value",
    "integer": 1,
    "number": 1.0,
    "boolean": True,
    "array": [],
    "object": {},
    "unknown": "test",
}
 
 
def _default_value(schema_type: str) -> Any:
    """Vraća validnu default vrednost za dati tip."""
    return _VALID_DEFAULTS.get(schema_type, "test")
 
 
# ---------------------------------------------------------------------------
# Generisanje base payload-a
# Sva polja su validna — koristimo ga kao osnovu za mutacije
# ---------------------------------------------------------------------------
 
def _build_base_payload(endpoint: EndpointModel) -> dict:
    """
    Pravi payload gdje su sva polja validna.
    Svaka mutacija kreće od ovog payload-a i mijenja jedno polje.
    """
    payload = {}
    for field_name, field_type in endpoint.request_schema.items():
        payload[field_name] = _default_value(field_type)
    return payload
 
 
def _build_base_path_params(endpoint: EndpointModel) -> dict:
    """Pravi validne path parametre, npr. {"bookId": 1}."""
    return {p.name: _default_value(p.schema_type) for p in endpoint.path_params}
 
 
def _build_base_query_params(endpoint: EndpointModel) -> dict:
    """Pravi validne query parametre, npr. {"limit": 10}."""
    return {p.name: _default_value(p.schema_type) for p in endpoint.query_params}
 
 
# ---------------------------------------------------------------------------
# Tri vrste mutacija
# ---------------------------------------------------------------------------
 
def _generate_field_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    """
    Za svako polje u request body-ju generiše scenarije
    gdje je to jedno polje pokvareno, a ostala su validna.
 
    Pokriva: boundary i type_mutation (oboje dolaze iz kataloga).
    """
    scenarios = []
    base_payload = _build_base_payload(endpoint)
    path_params = _build_base_path_params(endpoint)
    query_params = _build_base_query_params(endpoint)
 
    for field_name, field_type in endpoint.request_schema.items():
        mutations = get_mutations(field_type)
 
        for bad_value in mutations:
            # Kopiraj base payload i pokvar samo ovo jedno polje
            mutated_payload = base_payload.copy()
            mutated_payload[field_name] = bad_value
 
            scenarios.append(TestScenario(
                endpoint=endpoint.path,
                method=endpoint.method,
                payload=mutated_payload,
                path_params=path_params,
                query_params=query_params,
                mutation_type="type_mutation" if not isinstance(bad_value, str) else "boundary",
                mutated_field=field_name,
                description=f"Polje '{field_name}' ({field_type}) = {repr(bad_value)[:50]}",
            ))
 
    return scenarios
 
 
def _generate_structure_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    """
    Generiše scenarije gdje je struktura payload-a pogrešna:
    1. Nedostaje required polje
    2. Dodat extra nepostojeće polje
    """
    scenarios = []
    base_payload = _build_base_payload(endpoint)
    path_params = _build_base_path_params(endpoint)
    query_params = _build_base_query_params(endpoint)
 
    # 1. Ukloni svako required polje jedno po jedno
    for required_field in endpoint.required_fields:
        mutated_payload = {
            k: v for k, v in base_payload.items()
            if k != required_field
        }
        scenarios.append(TestScenario(
            endpoint=endpoint.path,
            method=endpoint.method,
            payload=mutated_payload,
            path_params=path_params,
            query_params=query_params,
            mutation_type="structure",
            mutated_field=required_field,
            description=f"Nedostaje required polje '{required_field}'",
        ))
 
    # 2. Dodaj extra polje koje ne postoji u spec-u
    extra_payload = base_payload.copy()
    extra_payload["__extra_field__"] = "unexpected_value"
    scenarios.append(TestScenario(
        endpoint=endpoint.path,
        method=endpoint.method,
        payload=extra_payload,
        path_params=path_params,
        query_params=query_params,
        mutation_type="structure",
        mutated_field="__extra_field__",
        description="Dodat nepostojeći field '__extra_field__'",
    ))
 
    return scenarios
 
 
def _generate_path_param_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    """
    Generiše scenarije gdje su path parametri pokvareni.
    Npr. /books/{bookId} → šaljemo bookId = "abc", -1, None...
    """
    scenarios = []
    base_path_params = _build_base_path_params(endpoint)
    base_query_params = _build_base_query_params(endpoint)
 
    for param in endpoint.path_params:
        mutations = get_mutations(param.schema_type)
 
        for bad_value in mutations:
            mutated_path_params = base_path_params.copy()
            mutated_path_params[param.name] = bad_value
 
            scenarios.append(TestScenario(
                endpoint=endpoint.path,
                method=endpoint.method,
                payload={},
                path_params=mutated_path_params,
                query_params=base_query_params,
                mutation_type="type_mutation",
                mutated_field=param.name,
                description=f"Path param '{param.name}' = {repr(bad_value)[:50]}",
            ))
 
    return scenarios
 
 
# ---------------------------------------------------------------------------
# Glavni generator
# ---------------------------------------------------------------------------
 
def generate_scenarios(endpoints: list[EndpointModel]) -> list[TestScenario]:
    """
    Prima listu EndpointModel objekata.
    Vraća sve TestScenario objekte za sve endpointe.
 
    Primer:
        spec = parse_file("examples/bookstore.yaml")
        scenarios = generate_scenarios(spec.endpoints)
        print(len(scenarios))  # npr. 150+
    """
    all_scenarios = []
 
    for endpoint in endpoints:
        # Mutacije na request body poljima
        if endpoint.request_schema:
            all_scenarios += _generate_field_mutations(endpoint)
            all_scenarios += _generate_structure_mutations(endpoint)
 
        # Mutacije na path parametrima
        if endpoint.path_params:
            all_scenarios += _generate_path_param_mutations(endpoint)
 
    return all_scenarios
 