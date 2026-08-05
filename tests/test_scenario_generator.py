import asyncio

from fuzzer.models import EndpointModel, ParameterModel
from fuzzer.generator.scenario_generator import (
    TestScenario,
    _default_value_from_schema,
    _generate_baseline_scenario,
    _generate_path_param_mutations,
)
from fuzzer.runner.http_runner import _run_one


def test_baseline_scenario_is_valid_and_marked():
    endpoint = EndpointModel(
        path="/books",
        method="POST",
        request_schema={"title": "string", "author": "string"},
        raw_request_schema={
            "properties": {"title": {"type": "string"}, "author": {"type": "string"}}
        },
        required_fields=["title", "author"],
    )

    scenario = _generate_baseline_scenario(endpoint)

    assert scenario.mutation_type == "baseline"
    assert scenario.payload == {"title": "test_value", "author": "test_value"}


def test_default_value_from_schema_uses_first_enum_value():
    value = _default_value_from_schema("string", {"enum": ["red", "green", "blue"]})
    assert value == "red"


def test_path_param_mutation_keeps_valid_body():
    endpoint = EndpointModel(
        path="/books/{bookId}",
        method="PUT",
        path_params=[ParameterModel(name="bookId", location="path", required=True, schema_type="integer")],
        request_schema={"title": "string", "author": "string"},
        required_fields=["title", "author"],
    )

    scenarios = _generate_path_param_mutations(endpoint)

    assert scenarios
    for scenario in scenarios:
        assert scenario.payload == {"title": "test_value", "author": "test_value"}


class _FakeResponse:
    status_code = 200
    content = b"{}"
    text = "{}"


class _FakeClient:
    class base_url:
        raw_path = b""

    def __init__(self):
        self.calls = []

    async def _record(self, method, url, headers=None, params=None, json=None):
        self.calls.append({"method": method, "params": params, "json": json})
        return _FakeResponse()

    async def get(self, url, headers=None, params=None):
        return await self._record("GET", url, headers, params, None)

    async def post(self, url, headers=None, params=None, json=None):
        return await self._record("POST", url, headers, params, json)

    async def put(self, url, headers=None, params=None, json=None):
        return await self._record("PUT", url, headers, params, json)

    async def delete(self, url, headers=None, params=None):
        return await self._record("DELETE", url, headers, params, None)


def test_query_params_sent_for_post_put_delete():
    for method in ("POST", "PUT", "DELETE"):
        scenario = TestScenario(
            endpoint="/books",
            method=method,
            payload={"title": "x"},
            path_params={},
            query_params={"limit": 5},
            header_params={},
            mutation_type="type_mutation",
            mutated_field="limit",
        )
        client = _FakeClient()

        asyncio.run(_run_one(
            scenario, client, token=None, timeout=5.0,
            semaphore=asyncio.Semaphore(1), delay=0.0,
        ))

        assert client.calls[0]["params"] == {"limit": 5}
