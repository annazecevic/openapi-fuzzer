
# Dockerfile
# Pakuje OpenAPI Fuzzer u Docker kontejner
 
FROM python:3.12-slim
 
# Radni direktorijum unutar kontejnera
WORKDIR /app
 
# Kopiraj dependency fajlove prvo (cache layer)
COPY pyproject.toml .
 
# Instaliraj zavisnosti
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Kopiraj ostatak projekta
COPY fuzzer/ ./fuzzer/
COPY examples/ ./examples/
 
# Output folder za reporte
RUN mkdir -p /app/reports
 
# Pokretanje fuzzera
CMD ["python3", "-m", "fuzzer", "--help"]
 