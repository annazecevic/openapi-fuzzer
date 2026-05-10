from fuzzer.parser import parse_file

spec = parse_file("examples/bookstore.yaml")
print(spec.summary())
print()

for ep in spec.endpoints:
    print(f"{ep.method:6s} {ep.path}")
    if ep.path_params:
        for p in ep.path_params:
            print(f"         path param: {p.name} ({p.schema_type})")
    if ep.query_params:
        for p in ep.query_params:
            print(f"         query param: {p.name} ({p.schema_type}, required={p.required})")
    if ep.request_schema:
        print(f"         request body: {ep.request_schema}")
        print(f"         required: {ep.required_fields}")

from fuzzer.generator.mutation_catalog import get_mutations

print(get_mutations("string"))
print(get_mutations("integer"))
print(get_mutations("xyz"))

from fuzzer.generator.scenario_generator import generate_scenarios

spec = parse_file("examples/bookstore.yaml")
scenarios = generate_scenarios(spec.endpoints)

print(f"\nUkupno scenarija: {len(scenarios)}")
print()

# Prikaži prvih 5
for s in scenarios[:5]:
    print(f"{s.method} {s.endpoint}")
    print(f"  tip:    {s.mutation_type}")
    print(f"  polje:  {s.mutated_field}")
    print(f"  opis:   {s.description}")
    print(f"  payload: {s.payload}")
    print()

from fuzzer.runner.http_runner import run_all

results = run_all(scenarios[:10], base_url="http://localhost:8080")

print(f"\nUkupno rezultata: {len(results)}")
for r in results[:5]:
    print(f"{r.method} {r.endpoint} → {r.status_code} ({r.response_time_ms}ms)")

from fuzzer.oracle.detector import analyze_results, summary

results = analyze_results(results)

print("\n=== ANOMALIJE ===")
for r in results:
    if r.anomalies:
        print(f"\n{r.method} {r.endpoint} — polje: {r.mutated_field}")
        for a in r.anomalies:
            print(f"  ⚠ {a}")

print("\n=== SUMMARY ===")
s = summary(results)
for k, v in s.items():
    print(f"  {k}: {v}")    