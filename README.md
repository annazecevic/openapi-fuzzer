# OpenAPI Fuzzer

Alat za automatizovano bezbednosno testiranje REST API-ja zasnovan na OpenAPI specifikaciji.

Čita OpenAPI `.yaml` ili `.json` fajl, automatski generiše stotine namerno pogrešnih HTTP zahteva i analizira odgovore u potrazi za bezbednosnim propustima.

---

## Tipovi anomalija koje alat detektuje

| Anomalija | Opis | Primer |
|---|---|---|
| **Server Failure** | API vraća 5xx ili ne odgovara | `POST /books` sa `title=[]` → 500 |
| **Contract Mismatch** | API vraća 2xx na payload koji krši OpenAPI šemu zahteva | `POST /users` bez `email` polja → 201 (krši required) |
| **Response Contract** | API vraća odgovor koji ne poštuje dokumentovanu šemu odgovora | `PUT /profile/{userId}` → 200 bez obaveznog `lessonCompleted` polja u telu odgovora |
| **Performance Anomaly** | Odgovor sporiji od 2 sekunde | `POST /books` sa 50.000 znakova → timeout |

---

## Dependency graph — automatsko povezivanje zavisnih resursa

Alat statički analizira spec (bez izvršavanja zahteva) i prepoznaje zavisnosti između endpointa: kada POST endpoint u dokumentovanom 2xx odgovoru vraća polje `id`, a neki drugi endpoint (GET/PUT/DELETE) deli isti prefiks putanje sa path parametrom (npr. `/books` → `/books/{bookId}`), alat pre glavnog testiranja izvrši taj POST zahtev, izvuče stvaran `id` iz odgovora, i koristi ga umesto izmišljene podrazumevane vrednosti pri testiranju zavisnog endpointa. Na taj način mutacije na poljima resursa (ne na samom id-ju) testiraju stvarno postojeći zapis, ne izmišljen identifikator koji možda ne postoji.

**Ograničenje:** heuristika prepoznaje samo konvenciju gde je identifikator u odgovoru nazvan tačno `id` — drugačije imenovani identifikatori (npr. `bookId`, `uuid`) se ne prepoznaju.

---

## Arhitektura

```
OpenAPI YAML/JSON
       │
       ▼
  ┌─────────┐     ┌───────────────┐     ┌────────────┐
  │  Parser │────▶│   Generator   │────▶│ HTTP Runner│
  └─────────┘     └───────────────┘     └────────────┘
                  N test scenarija*          │
                                             ▼
                                      ┌─────────────┐
                                      │    Oracle   │ ← detektuje anomalije
                                      └─────────────┘
                                             │
                                      ┌─────────────┐
                                      │  Reporter   │ → report.html / report.pdf / report.json
                                      └─────────────┘
```
\* Tačan broj generisanih scenarija zavisi od učitane specifikacije: po jedan
`baseline` scenario za svaki endpoint, uz dodatne `type_mutation` / `boundary`
/ `injection` / `structure` mutacije za svako polje odnosno parametar.

---

## Preduslovi

- **Python 3.12+**
- **Docker** (samo za pokretanje putem Docker-a)

Provera instalirane verzije Python-a:
```bash
python3 --version
```

---

## Način 1 — Docker (pokretanje jednom komandom)

Ova komanda automatski pokreće mock API i fuzzer, bez potrebe za dodatnom instalacijom zavisnosti.

```bash
docker compose up
```

Generisani izveštaj se čuva u folderu `reports/`.

---

## Način 2 — Lokalno pokretanje (veća kontrola nad parametrima)

### Korak 1 — Instalacija zavisnosti

```bash
pip install -r requirements.txt
```

### Korak 2 — Pokretanje ciljnog API-ja

**Opcija A — Mock API** (lokalni testni server koji je namerno ranjiv):
```bash
uvicorn mock_api:app --port 8080
```

**Opcija B — WebGoat** (OWASP ranjiva aplikacija za testiranje):
```bash
docker start webgoat
# ili, prilikom prvog pokretanja:
docker run -d --name webgoat -p 8081:8080 webgoat/webgoat
```
WebGoat aplikacija je dostupna na `http://localhost:8081/WebGoat`, gde je potrebno napraviti nalog i prijaviti se.

### Korak 3 — Pokretanje alata

```bash
python3 -m fuzzer --spec <putanja_do_spec> --url <adresa_api>
```

---

## Primeri pokretanja

### Primer 1 — Mock API (bookstore)
```bash
# Terminal 1
uvicorn mock_api:app --port 8080

# Terminal 2
python3 -m fuzzer \
  --spec examples/bookstore.yaml \
  --url http://localhost:8080 \
  --output-dir ./reports
```

### Primer 2 — WebGoat sa autentifikacijom
```bash
# Kopiraj JSESSIONID iz browser DevTools (F12 → Network → bilo koji zahtev → Cookie header)
python3 -m fuzzer \
  --spec examples/webgoat_idor.yaml \
  --url http://localhost:8081 \
  --token "JSESSIONID=ABC123tvojtoken" \
  --output-dir ./reports
```

### Primer 3 — Sa PDF izveštajem i ograničenim brojem zahteva u sekundi (rate-limiting)
```bash
python3 -m fuzzer \
  --spec examples/bookstore.yaml \
  --url http://localhost:8080 \
  --rate-limit 10 \
  --pdf \
  --output-dir ./reports
```

### Primer 4 — JSON spec fajl (umesto YAML)
Parser podjednako podržava `.json` spec fajlove — `examples/bookstore.json` je isti Bookstore API kao `examples/bookstore.yaml`, samo u JSON formatu:
```bash
python3 -m fuzzer \
  --spec examples/bookstore.json \
  --url http://localhost:8080 \
  --output-dir ./reports
```

### Primer 5 — Spotify (studentski projekat)
```bash
# Pokreni Spotify servise (samo prvi put, gradi Docker image):
cd /putanja/do/spotify && docker compose -f docker-compose.fuzzer.yml up -d

# User Service (port 9080) — autentifikacija, OTP, magic-link
python3 -m fuzzer \
  --spec examples/spotify_user_service.yaml \
  --url http://localhost:9080 \
  --output-dir reports/spotify-user \
  --concurrency 3 \
  --pdf

# Content Service (port 9081) — žanrovi, izvođači, albumi, pesme
python3 -m fuzzer \
  --spec examples/spotify_content_service.yaml \
  --url http://localhost:9081 \
  --output-dir reports/spotify-content \
  --concurrency 5 \
  --pdf
```

---

## Scenariji testiranja (sekcija 4.2 specifikacije)

Alat pokriva tri propisana scenarija napada, pri čemu svaki scenario odgovara određenom tipu mutacije:

| Scenario | Opis | Tip mutacije | Primer |
|---|---|---|---|
| **Scenario 1** — Enumeracija resursa | Mutiranje ID parametara u putanjama (`/profile/{userId}`) — testira kako endpoint reaguje na neočekivane/nevalidne vrednosti identifikatora resursa (ne dokazuje samo po sebi IDOR, koji je pitanje autorizacije) | `type_mutation`/`boundary`/`injection` na path params | `userId = -1, null, 99999999, "abc"` |
| **Scenario 2** — Type Confusion | Slanje pogrešnih tipova na POST/PUT endpointe | `type_mutation` + `boundary` na body polju | `title = None, [], True, "A"×10000` |
| **Scenario 3** — Schema Violation | Uklanjanje obaveznih polja, duboko nestovanje, prototype pollution | `structure` | `__deep_nest__` (8 nivoa), `__proto__` injection, nedostaje required polje |

`boundary` mutacije uključuju i vrednosti IZRAČUNATE iz stvarno deklarisanih `minimum`/`maximum`/`maxLength`/`minLength` granica u OpenAPI šemi (ne samo generičke fiksne vrednosti iz statičnog kataloga) — npr. za polje sa `maximum: 2030` alat testira i `2030` (na granici) i `2031` (jedan iznad).

---

## Parametri komandne linije

| Argument | Obavezno | Opis | Podrazumevana vrednost |
|---|---|---|---|
| `--spec` | Da | Putanja do OpenAPI YAML ili JSON fajla | — |
| `--url` | Da | Adresa ciljnog API-ja, npr. `http://localhost:8080` | — |
| `--token` | Ne | Token za autentifikaciju — kao Bearer token (`abc123`) ili kao Cookie (`JSESSIONID=abc123`) | — |
| `--output-dir` | Ne | Folder za izveštaje | `.` (trenutni folder) |
| `--concurrency` | Ne | Broj paralelnih zahteva | `1` |
| `--rate-limit` | Ne | Maksimalan broj zahteva u sekundi, 0 = bez ograničenja (token bucket rate limiting, ne fiksna pauza) | `0` |
| `--timeout` | Ne | Timeout po zahtevu u sekundama | `10` |
| `--pdf` | Ne | Generisanje PDF izveštaja | isključeno |

---

## Tumačenje izlaza programa

```
[1/5] Parsiranje OpenAPI spec-a: examples/bookstore.yaml
      API: Bookstore API v1.0.0
OpenAPI: 3.0.3
Endpoints: 6

[2/5] Generisanje test scenarija...
      Generisano 234 scenarija

[3/5] Izvršavanje fuzz testova na: http://localhost:8080 (konkurentnost: 1)
      [1/234] GET /books (baseline: __baseline__) → 200
      [2/234] GET /books (boundary: limit) → 200
      ...

[4/5] Analiza rezultata...
      Ukupno:               234        ← koliko testova je pokrenuto
      Prošlo:               165        ← bez anomalija
      Anomalija:            69         ← pronađeni propusti
        - Server Failure:     1        ← API se srušio (500)
        - Contract Mismatch:  68       ← API prihvatio ulaz koji krši šemu zahteva
        - Response Contract:  0        ← odgovor krši dokumentovanu šemu odgovora
        - Performance:        0        ← spori odgovori
      Nepouzdani rezultati: 0 (baseline pao) ← mutacije čiji je kontrolni zahtev i sam pao
      API Coverage:         6/6 endpointa (100.0%)

[5/5] Generisanje izveštaja...
      HTML izveštaj snimljen: reports/report.html
      JSON log snimljen:       reports/report.json
```

---

## Generisani izveštaji

Nakon izvršavanja, u direktorijumu zadatom parametrom `--output-dir` generišu se tri fajla:

| Fajl | Opis |
|---|---|
| `report.html` | Vizuelni izveštaj, namenjen pregledu u veb pregledaču |
| `report.json` | Mašinski čitljiv log svih rezultata |
| `report.pdf` | PDF verzija izveštaja (generiše se samo uz `--pdf` opciju) |

---

## Evaluacija preciznosti alata (sekcija 5.2)

Koristi se za merenje preciznosti alata, odnosno za utvrđivanje koliki procenat prijavljenih anomalija predstavlja stvarne propuste. Postoje dva pristupa, u zavisnosti od toga da li unapred postoji poznata lista bagova u ciljnom API-ju.

### Opcija A — Ground truth evaluacija (preporučeno, ukoliko postoji unapred pripremljena lista bagova)

Za potrebe `mock_api.py` postoji fajl `ground_truth/known_bugs.yaml` — lista bagova definisana **unapred, pre pokretanja alata** (svaki bag sadrži polja `endpoint`, `method`, `field`, `expected_anomaly` i `findable_by_tool`). Skripta `fuzzer/oracle/ground_truth_eval.py` automatski poredi `report.json` sa tom listom, bez potrebe za ručnom anotacijom.

```bash
python3 -m fuzzer.oracle.ground_truth_eval \
  --report reports/report.json \
  --known-bugs ground_truth/known_bugs.yaml
```

Izlaz prikazuje koji su bag ID-jevi pronađeni, koji su promašeni, koji su lažni pozitivi (sa podacima o endpoint-u, metodi i mutiranom polju za svaki), bagove koje alat po dizajnu ne može da otkrije (npr. IDOR, koji je pitanje autorizacije, a ne šeme), kao i finalne Precision/Recall/F1 metrike (računate isključivo na osnovu bagova sa `findable_by_tool: true`).

Primer ispisa (skraćeno):
```
── Ground Truth Evaluacija ───────────────────────────
  Pronađeni bagovi (6):
    ✓ BUG-01
    ✓ BUG-02
    ✓ BUG-03
    ✓ BUG-04
    ✓ BUG-06
    ✓ BUG-07

  Lažni pozitivi (45):
    ? POST /books (polje: year)
        CONTRACT_MISMATCH: Server vratio 201 na payload koji krši šemu ('abc' is not of type 'integer') — polje 'year'
    ...

  Poznati, očekivani propusti (alat ih po dizajnu ne može naći):
    • BUG-05

  Precision: 0.3478
  Recall:    1.0000
  F1 Score:  0.5161
──────────────────────────────────────────────────────
```
Nizak precision u ovom primeru ne ukazuje na grešku u oracle-u — mock API namerno sadrži više propusta u validaciji tipova nego što `known_bugs.yaml` pokriva, pa svaki lažni pozitiv iz liste zapravo predstavlja stvarnu, samo neanotiranu grešku u `mock_api.py`.

### Opcija B — Ručna F1 anotacija (kada ne postoji unapred pripremljena lista bagova)

#### Korak 1 — Priprema fajla za anotaciju
```bash
python3 -m fuzzer.oracle.annotate \
  --input reports/report.json \
  --output reports/annotate.json
```

#### Korak 2 — Ručna anotacija fajla `reports/annotate.json`
Za svaku anomaliju potrebno je postaviti:
```json
"true_positive": true    ← stvarni bezbednosni propust
"true_positive": false   ← lažna uzbuna
```
Na kraju fajla potrebno je dodati:
```json
"false_negatives": 1    ← propusti koje fuzzer nije pronašao
```

#### Korak 3 — Izračunavanje F1 mere
```bash
python3 -m fuzzer.oracle.f1_score --ground-truth reports/annotate.json
```

Primer ispisa:
```
── F1 Score Evaluacija ──────────────────────────────
  True Positives  (TP): 64
  False Positives (FP): 0
  False Negatives (FN): 1
  Precision:            1.0000
  Recall:               0.9846
  F1 Score:             0.9922
─────────────────────────────────────────────────────
```

---

## Struktura projekta

```
openapi-fuzzer/
│
├── fuzzer/
│   ├── __main__.py          ← ulazna tačka, CLI argumenti
│   ├── models.py            ← zajednički data modeli
│   │
│   ├── parser/
│   │   ├── openapi_parser.py    ← čita OpenAPI YAML/JSON
│   │   ├── validator.py         ← validacija OpenAPI 3.x strukture
│   │   └── dependency_graph.py  ← prepoznaje zavisnosti između endpointa (producer → consumer)
│   │
│   ├── generator/
│   │   ├── mutation_catalog.py   ← baza loših vrednosti po tipu
│   │   └── scenario_generator.py ← pravi test scenarije (Scenario 1/2/3)
│   │
│   ├── runner/
│   │   ├── http_runner.py   ← šalje HTTP zahteve (asyncio, konkurentnost)
│   │   └── rate_limiter.py  ← globalni token-bucket rate limiter
│   │
│   ├── oracle/
│   │   ├── detector.py            ← detektuje anomalije (Server Failure, Contract Mismatch, Performance)
│   │   ├── f1_score.py            ← računa F1 Score (Precision, Recall)
│   │   ├── annotate.py            ← priprema fajl za ručnu anotaciju
│   │   └── ground_truth_eval.py   ← automatska evaluacija protiv unapred pripremljene liste bagova
│   │
│   └── reporter/
│       ├── report_generator.py    ← generiše HTML/PDF/JSON
│       └── templates/
│           ├── report.html.j2     ← HTML template (interaktivni)
│           └── report.pdf.j2      ← PDF template (xhtml2pdf kompatibilan)
│
├── examples/
│   ├── bookstore.yaml              ← primer spec-a za mock API
│   ├── bookstore.json              ← isti primer spec-a u JSON formatu
│   ├── webgoat_idor.yaml           ← WebGoat IDOR spec (Scenario 1 — enumeracija)
│   ├── spotify_user_service.yaml   ← Spotify User Service spec (port 9080)
│   └── spotify_content_service.yaml← Spotify Content Service spec (port 9081)
│
├── ground_truth/
│   └── known_bugs.yaml              ← unapred definisana lista poznatih bagova za mock_api.py
│
├── tests/                   ← 30 unit testa (pytest)
│   ├── test_oracle.py               ← detektor anomalija (contract/response/server failure)
│   ├── test_scenario_generator.py   ← generisanje scenarija i mutacioni katalog
│   ├── test_rate_limiter.py         ← token-bucket rate limiter
│   ├── test_ground_truth_eval.py    ← ground truth evaluacija
│   ├── test_parser.py               ← YAML/JSON parsiranje spec fajlova
│   └── test_dependency_graph.py     ← prepoznavanje zavisnosti između endpointa
│
├── mock_api.py              ← lokalni ranjivi API za demonstraciju
├── docker-compose.yml       ← pokreće mock API + fuzzer jednom komandom (+ PDF)
├── Dockerfile               ← Docker image za fuzzer
├── requirements.txt         ← Python zavisnosti
└── README.md                ← dokumentacija projekta
```

---

## Pregled najčešće korišćenih komandi

```bash
# Instalacija zavisnosti (jednokratno)
pip install -r requirements.txt

# Pokretanje mock API-ja (u zasebnom terminalu)
uvicorn mock_api:app --port 8080

# Osnovno pokretanje
python3 -m fuzzer --spec examples/bookstore.yaml --url http://localhost:8080

# Sa svim opcijama
python3 -m fuzzer \
  --spec examples/webgoat_idor.yaml \
  --url http://localhost:8081 \
  --token "JSESSIONID=tvoj_token" \
  --concurrency 5 \
  --rate-limit 10 \
  --timeout 15 \
  --pdf \
  --output-dir ./reports

# Docker (sve odjednom)
docker compose up

# F1 Score
python3 -m fuzzer.oracle.annotate --input reports/report.json --output reports/annotate.json
python3 -m fuzzer.oracle.f1_score --ground-truth reports/annotate.json
```

---

## Povratne vrednosti (exit kodovi)

| Kod | Značenje |
|---|---|
| `0` | Izvršavanje završeno, nisu pronađene anomalije |
| `1` | Izvršavanje završeno, pronađene su anomalije |
| `2` | Greška pri pokretanju (neispravan spec, API nedostupan) |
