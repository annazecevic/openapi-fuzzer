"""
fuzzer/reporter/report_generator.py
 
Generiše HTML izvještaj i JSON log iz liste TestResult objekata.
"""
 
import json
from datetime import datetime
from pathlib import Path
 
from jinja2 import Environment, FileSystemLoader
 
from fuzzer.models import TestResult
 
 
# Putanja do templates foldera
TEMPLATES_DIR = Path(__file__).parent / "templates"
 
 
def generate_html(
    results: list[TestResult],
    summary: dict,
    api_title: str = "Unknown API",
    api_version: str = "unknown",
    output_path: str = "report.html",
) -> str:
    """
    Generiše HTML izvještaj i snima ga na disk.
 
    Args:
        results:     lista TestResult objekata od Oraclea
        summary:     dict sa brojevima od oracle.summary()
        api_title:   naziv API-ja iz spec-a
        api_version: verzija API-ja iz spec-a
        output_path: gdje snimiti HTML fajl
 
    Returns:
        Putanja do snimljenog HTML fajla.
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("report.html.j2")
 
    html = template.render(
        title=api_title,
        version=api_version,
        generated_at=datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        summary=summary,
        results=results,
    )
 
    output = Path(output_path)
    output.write_text(html, encoding="utf-8")
    print(f"HTML izvještaj snimljen: {output.resolve()}")
    return str(output.resolve())
 
 
def generate_json(
    results: list[TestResult],
    summary: dict,
    api_title: str = "Unknown API",
    output_path: str = "report.json",
) -> str:
    """
    Generiše JSON log i snima ga na disk.
 
    Args:
        results:     lista TestResult objekata
        summary:     dict sa brojevima
        api_title:   naziv API-ja
        output_path: gdje snimiti JSON fajl
 
    Returns:
        Putanja do snimljenog JSON fajla.
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
 