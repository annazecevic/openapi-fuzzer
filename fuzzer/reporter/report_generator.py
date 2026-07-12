"""
fuzzer/reporter/report_generator.py

Generiše HTML, PDF i JSON izveštaj iz liste TestResult objekata.
"""

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from fuzzer.models import TestResult


TEMPLATES_DIR = Path(__file__).parent / "templates"


def _render_html(
    results: list[TestResult],
    summary: dict,
    api_title: str,
    api_version: str,
) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("report.html.j2")
    return template.render(
        title=api_title,
        version=api_version,
        generated_at=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        summary=summary,
        results=results,
    )


def generate_html(
    results: list[TestResult],
    summary: dict,
    api_title: str = "Unknown API",
    api_version: str = "unknown",
    output_path: str = "report.html",
) -> str:
    """
    Generiše HTML izveštaj i snima ga na disk.
    Vraća putanju do snimljenog fajla.
    """
    html = _render_html(results, summary, api_title, api_version)
    output = Path(output_path)
    output.write_text(html, encoding="utf-8")
    print(f"HTML izveštaj snimljen: {output.resolve()}")
    return str(output.resolve())


def _render_pdf_html(
    results: list[TestResult],
    summary: dict,
    api_title: str,
    api_version: str,
) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("report.pdf.j2")
    return template.render(
        title=api_title,
        version=api_version,
        generated_at=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        summary=summary,
        results=results,
    )


def generate_pdf(
    results: list[TestResult],
    summary: dict,
    api_title: str = "Unknown API",
    api_version: str = "unknown",
    output_path: str = "report.pdf",
) -> str:
    """
    Generiše PDF izveštaj iz namenskog PDF predloška.
    Vraća putanju do snimljenog fajla.
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        raise RuntimeError(
            "PDF generisanje zahteva xhtml2pdf: pip install xhtml2pdf"
        )

    html = _render_pdf_html(results, summary, api_title, api_version)
    output = Path(output_path)

    with open(output, "wb") as pdf_file:
        result = pisa.CreatePDF(html, dest=pdf_file, encoding="utf-8")

    if result.err:
        raise RuntimeError(f"PDF konverzija nije uspjela (xhtml2pdf greška: {result.err})")

    print(f"PDF izveštaj snimljen: {output.resolve()}")
    return str(output.resolve())


def generate_json(
    results: list[TestResult],
    summary: dict,
    api_title: str = "Unknown API",
    output_path: str = "report.json",
) -> str:
    """
    Generiše JSON log i snima ga na disk.
    Vraća putanju do snimljenog fajla.
    """
    log = {
        "api": api_title,
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "results": [r.model_dump() for r in results],
    }

    output = Path(output_path)
    output.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(f"JSON log snimljen: {output.resolve()}")
    return str(output.resolve())
