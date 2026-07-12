from dataclasses import dataclass, field
from typing import Any

from fuzzer.models import EndpointModel
from fuzzer.generator.mutation_catalog import get_mutations


@dataclass
class TestScenario:
    endpoint: str
    method: str
    payload: dict
    path_params: dict
    query_params: dict
    header_params: dict
    mutation_type: str
    mutated_field: str
    description: str = ""


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
    return _VALID_DEFAULTS.get(schema_type, "test")


def _build_base_payload(endpoint: EndpointModel) -> dict:
    return {f: _default_value(t) for f, t in endpoint.request_schema.items()}


def _build_base_path_params(endpoint: EndpointModel) -> dict:
    return {p.name: _default_value(p.schema_type) for p in endpoint.path_params}


def _build_base_query_params(endpoint: EndpointModel) -> dict:
    return {p.name: _default_value(p.schema_type) for p in endpoint.query_params}


def _build_base_header_params(endpoint: EndpointModel) -> dict:
    return {p.name: _default_value(p.schema_type) for p in endpoint.header_params}


def _generate_field_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    scenarios = []
    base = _build_base_payload(endpoint)
    path_params = _build_base_path_params(endpoint)
    query_params = _build_base_query_params(endpoint)
    header_params = _build_base_header_params(endpoint)

    for field_name, field_type in endpoint.request_schema.items():
        for bad_value in get_mutations(field_type):
            mutated = base.copy()
            mutated[field_name] = bad_value
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
            ))

    return scenarios


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
    ))

    # Scenario 3 iz spec-a — duboko nestovanje kao stres test parsera
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
    ))

    return scenarios


def _generate_path_param_mutations(endpoint: EndpointModel) -> list[TestScenario]:
    scenarios = []
    base_path = _build_base_path_params(endpoint)
    base_query = _build_base_query_params(endpoint)
    base_headers = _build_base_header_params(endpoint)

    for param in endpoint.path_params:
        for bad_value in get_mutations(param.schema_type):
            scenarios.append(TestScenario(
                endpoint=endpoint.path,
                method=endpoint.method,
                payload={},
                path_params={**base_path, param.name: bad_value},
                query_params=base_query,
                header_params=base_headers,
                mutation_type="type_mutation",
                mutated_field=param.name,
                description=f"Path param '{param.name}' = {repr(bad_value)[:50]}",
            ))

    return scenarios


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


def generate_scenarios(endpoints: list[EndpointModel]) -> list[TestScenario]:
    all_scenarios = []

    for endpoint in endpoints:
        if endpoint.request_schema:
            all_scenarios += _generate_field_mutations(endpoint)
            all_scenarios += _generate_structure_mutations(endpoint)

        if endpoint.path_params:
            all_scenarios += _generate_path_param_mutations(endpoint)

        if endpoint.query_params:
            all_scenarios += _generate_query_param_mutations(endpoint)

        if endpoint.header_params:
            all_scenarios += _generate_header_param_mutations(endpoint)

    return all_scenarios
