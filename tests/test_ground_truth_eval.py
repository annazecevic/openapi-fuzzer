import json

import yaml

from fuzzer.oracle.ground_truth_eval import evaluate_against_ground_truth


KNOWN_BUGS = [
    {
        "id": "BUG-01",
        "endpoint": "/books",
        "method": "POST",
        "field": "title",
        "description": "Server puca (500) ako je title lista umesto string",
        "expected_anomaly": "SERVER_FAILURE",
        "findable_by_tool": True,
    },
    {
        "id": "BUG-02",
        "endpoint": "/books",
        "method": "POST",
        "field": "author",
        "description": "Prihvata zahtev bez obaveznog author polja, vraca 201",
        "expected_anomaly": "CONTRACT_MISMATCH",
        "findable_by_tool": True,
    },
]


def _write_ground_truth(tmp_path):
    known_bugs_path = tmp_path / "known_bugs.yaml"
    known_bugs_path.write_text(yaml.dump(KNOWN_BUGS), encoding="utf-8")
    return str(known_bugs_path)


def _write_report(tmp_path, results):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"results": results}), encoding="utf-8")
    return str(report_path)


def test_matching_result_gives_true_positive(tmp_path):
    known_bugs_path = _write_ground_truth(tmp_path)
    report_path = _write_report(tmp_path, [
        {
            "endpoint": "/books",
            "method": "POST",
            "mutated_field": "title",
            "anomalies": ["SERVER_FAILURE: Status 500 — server crash na mutiranom ulazu"],
        },
    ])

    evaluation = evaluate_against_ground_truth(report_path, known_bugs_path)

    assert len(evaluation["true_positives"]) == 1
    assert evaluation["true_positives"][0]["bug_id"] == "BUG-01"
    assert evaluation["false_positives"] == []


def test_unmatched_anomaly_gives_false_positive(tmp_path):
    known_bugs_path = _write_ground_truth(tmp_path)
    report_path = _write_report(tmp_path, [
        {
            "endpoint": "/users",
            "method": "POST",
            "mutated_field": "username",
            "anomalies": ["CONTRACT_MISMATCH: Server vratio 201 na payload koji krši šemu"],
        },
    ])

    evaluation = evaluate_against_ground_truth(report_path, known_bugs_path)

    assert evaluation["true_positives"] == []
    assert len(evaluation["false_positives"]) == 1
    assert evaluation["false_positives"][0]["mutated_field"] == "username"


def test_bug_absent_from_results_gives_false_negative(tmp_path):
    known_bugs_path = _write_ground_truth(tmp_path)
    report_path = _write_report(tmp_path, [
        {
            "endpoint": "/books",
            "method": "POST",
            "mutated_field": "title",
            "anomalies": ["SERVER_FAILURE: Status 500 — server crash na mutiranom ulazu"],
        },
    ])

    evaluation = evaluate_against_ground_truth(report_path, known_bugs_path)

    assert evaluation["false_negatives"] == ["BUG-02"]


SAME_TRIPLE_BUGS = [
    {
        "id": "BUG-01",
        "endpoint": "/books",
        "method": "POST",
        "field": "title",
        "description": "Server puca (500) ako je title lista umesto string",
        "expected_anomaly": "SERVER_FAILURE",
        "findable_by_tool": True,
    },
    {
        "id": "BUG-02",
        "endpoint": "/books",
        "method": "POST",
        "field": "title",
        "description": "Prihvata zahtev bez obaveznog title polja, vraca 201",
        "expected_anomaly": "CONTRACT_MISMATCH",
        "findable_by_tool": True,
    },
]


def test_same_endpoint_method_field_different_anomaly_are_distinguished(tmp_path):
    known_bugs_path = tmp_path / "known_bugs.yaml"
    known_bugs_path.write_text(yaml.dump(SAME_TRIPLE_BUGS), encoding="utf-8")
    report_path = _write_report(tmp_path, [
        {
            "endpoint": "/books",
            "method": "POST",
            "mutated_field": "title",
            "anomalies": ["SERVER_FAILURE: Status 500 — server crash na mutiranom ulazu"],
        },
        {
            "endpoint": "/books",
            "method": "POST",
            "mutated_field": "title",
            "anomalies": ["CONTRACT_MISMATCH: Server vratio 201 na payload koji krši šemu"],
        },
    ])

    evaluation = evaluate_against_ground_truth(report_path, str(known_bugs_path))

    matched_ids = sorted(tp["bug_id"] for tp in evaluation["true_positives"])
    assert matched_ids == ["BUG-01", "BUG-02"]
    assert evaluation["false_positives"] == []
    assert evaluation["false_negatives"] == []
