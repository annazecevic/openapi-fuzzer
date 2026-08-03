from fuzzer.models import TestResult
from fuzzer.oracle.detector import detect


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
