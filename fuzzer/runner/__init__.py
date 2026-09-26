# Javni interfejs fuzzer.runner paketa — izvozi run_all(), koja izvršava
# listu test scenarija kao HTTP zahteve ka ciljnom API-ju.

from fuzzer.runner.http_runner import run_all

__all__ = ["run_all"]
