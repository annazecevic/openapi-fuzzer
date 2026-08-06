from fuzzer.models import TestResult
from fuzzer.oracle.detector import analyze_results, detect


SCHEMA = {
    "type": "object",
    "properties": {
        "age": {"type": "integer", "minimum": 0},
    },
    "required": ["age"],
}


def _result(status_code: int, payload: dict, request_schema: dict) -> TestResult:
    return TestResult(
        endpoint="/users",
        method="POST",
        status_code=status_code,
        response_time_ms=10.0,
        payload=payload,
        mutated_field="age",
        request_schema=request_schema,
    )


def test_valid_payload_with_200_no_mismatch():
    result = _result(200, {"age": 5}, SCHEMA)
    anomalies = detect(result)
    assert not any("CONTRACT_MISMATCH" in a for a in anomalies)


def test_invalid_payload_with_200_gives_mismatch():
    result = _result(200, {"age": -5}, SCHEMA)
    anomalies = detect(result)
    assert any("CONTRACT_MISMATCH" in a for a in anomalies)


def test_invalid_payload_with_400_no_mismatch():
    result = _result(400, {"age": -5}, SCHEMA)
    anomalies = detect(result)
    assert not any("CONTRACT_MISMATCH" in a for a in anomalies)


def test_empty_request_schema_no_mismatch():
    result = _result(200, {"age": -5}, {})
    anomalies = detect(result)
    assert not any("CONTRACT_MISMATCH" in a for a in anomalies)


def _error_result(error_category: str | None) -> TestResult:
    return TestResult(
        endpoint="/users",
        method="POST",
        status_code=0,
        response_time_ms=10.0,
        mutated_field="age",
        error_category=error_category,
    )


def test_timeout_gives_server_failure():
    result = _error_result("TIMEOUT")
    anomalies = detect(result)
    assert any("SERVER_FAILURE" in a for a in anomalies)


def test_connect_error_gives_server_failure():
    result = _error_result("CONNECT_ERROR")
    anomalies = detect(result)
    assert any("SERVER_FAILURE" in a for a in anomalies)


def test_client_error_no_server_failure():
    result = _error_result("CLIENT_ERROR")
    anomalies = detect(result)
    assert not any("SERVER_FAILURE" in a for a in anomalies)


def test_failed_baseline_marks_other_results_unreliable():
    baseline = TestResult(
        endpoint="/users",
        method="POST",
        status_code=500,
        response_time_ms=10.0,
        mutation_type="baseline",
        mutated_field="__baseline__",
    )
    mutation = TestResult(
        endpoint="/users",
        method="POST",
        status_code=201,
        response_time_ms=10.0,
        mutation_type="type_mutation",
        mutated_field="age",
    )

    results = analyze_results([baseline, mutation])

    assert results[1].baseline_valid is False


RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["lessonCompleted"],
    "properties": {
        "lessonCompleted": {"type": "boolean"},
        "feedback": {"type": "string"},
    },
}


def _response_result(response_json: dict | None, response_schema: dict) -> TestResult:
    return TestResult(
        endpoint="/WebGoat/IDOR/profile/{userId}",
        method="PUT",
        status_code=200,
        response_time_ms=10.0,
        mutated_field="__baseline__",
        response_schema=response_schema,
        response_json=response_json,
    )


def test_valid_response_json_no_response_contract_mismatch():
    result = _response_result({"lessonCompleted": True, "feedback": "ok"}, RESPONSE_SCHEMA)
    anomalies = detect(result)
    assert not any("RESPONSE_CONTRACT_MISMATCH" in a for a in anomalies)


def test_response_json_missing_required_field_gives_response_contract_mismatch():
    result = _response_result({"feedback": "ok"}, RESPONSE_SCHEMA)
    anomalies = detect(result)
    assert any("RESPONSE_CONTRACT_MISMATCH" in a for a in anomalies)
