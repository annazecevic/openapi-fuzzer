# Javni interfejs fuzzer.oracle paketa — oracle odlučuje da li je odgovor
# servera anomalija. annotate.py, f1_score.py i ground_truth_eval.py su
# zasebne CLI skripte za evaluaciju tačnosti alata.

from fuzzer.oracle.detector import analyze_results, summary

__all__ = ["analyze_results", "summary"]
