import json

from fuzzer.models import TestResult
from fuzzer.reporter.report_generator import _render_html, _render_pdf_html
from fuzzer.reporter.rerender import load_report


XSS = "<script>alert(1)</script>"


def _summary(**extra) -> dict:
    base = {
        "total": 1,
        "passed": 0,
        "failed": 1,
        "not_executed": 0,
        "server_failures": 1,
        "contract_mismatches": 0,
        "response_contract_mismatches": 0,
        "performance_anomalies": 0,
        "unreliable_results": 0,
    }
    base.update(extra)
    return base


def _xss_result() -> TestResult:
    return TestResult(
        endpoint="/books",
        method="POST",
        status_code=500,
        response_time_ms=12.3,
        payload={"title": XSS},
        response_body=f"error near {XSS}",
        anomalies=[f"SERVER_FAILURE: Status 500 — {XSS}"],
        mutation_type="injection",
        mutated_field="title",
        passed=False,
    )


def test_html_escapes_payload_script():
    html = _render_html([_xss_result()], _summary(), "Test API", "1.0.0")

    assert XSS not in html
    assert "&lt;script&gt;" in html


def test_pdf_html_escapes_script():
    # _render_pdf_html samo popunjava šablon — xhtml2pdf nije potreban.
    # PDF šablon ne prikazuje payload, pa se <script> ubacuje u polja koja
    # prikazuje: mutirano polje i naziv API-ja
    result = _xss_result()
    result.mutated_field = XSS
    html = _render_pdf_html([result], _summary(), XSS, "1.0.0")

    assert XSS not in html
    assert "&lt;script&gt;" in html


def test_html_first_line_is_doctype():
    html = _render_html([], _summary(total=0, failed=0, server_failures=0), "Test API", "1.0.0")
    assert html.splitlines()[0] == "<!DOCTYPE html>"


def test_html_renders_without_coverage_and_not_executed_keys():
    summary = _summary()
    del summary["not_executed"]
    html = _render_html([_xss_result()], summary, "Test API", "1.0.0")

    assert "API Coverage" not in html
    assert "Nije izvršeno" in html


def test_html_shows_response_contract_and_unreliable():
    result = TestResult(
        endpoint="/books/{id}",
        method="GET",
        status_code=200,
        response_time_ms=5.0,
        anomalies=["RESPONSE_CONTRACT_MISMATCH: Odgovor ne odgovara šemi"],
        mutation_type="boundary",
        passed=False,
        baseline_valid=False,
    )
    summary = _summary(server_failures=0, response_contract_mismatches=1, unreliable_results=1)
    html = _render_html([result], summary, "Test API", "1.0.0")

    assert 'data-cats="rc"' in html
    assert "Nepouzdani rezultati" in html
    assert "nepouzdano" in html


def test_rerender_computes_missing_not_executed(tmp_path):
    client_error = TestResult(
        endpoint="/x", method="GET", status_code=0, response_time_ms=0.0,
        error_category="CLIENT_ERROR", passed=True,
    )
    report = {
        "api": "Old API",
        "summary": {"total": 2, "passed": 1, "failed": 1},
        "results": [client_error.model_dump(), _xss_result().model_dump()],
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    results, summary, title, version = load_report(str(path))

    assert len(results) == 2
    assert summary["not_executed"] == 1
    assert title == "Old API"
    assert version == "1.0.0"
