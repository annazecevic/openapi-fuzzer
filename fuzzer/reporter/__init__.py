# Javni interfejs fuzzer.reporter paketa — generisanje HTML i JSON izveštaja
# (PDF se uvozi direktno iz report_generator, jer zahteva opcioni xhtml2pdf).

from fuzzer.reporter.report_generator import generate_html, generate_json

__all__ = ["generate_html", "generate_json"]
