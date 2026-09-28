# Zajednički Pydantic modeli podataka koje koriste svi delovi fuzzera —
# parser ih pravi iz OpenAPI spec-a, generator i runner ih čitaju, a oracle
# i reporter rade nad TestResult objektima. Pydantic (za razliku od obične
# @dataclass) automatski validira tipove polja pri kreiranju objekta.

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

# Jedan parametar endpoint-a (query/path/header) — ime, gde se nalazi,
# da li je obavezan, prost tip i originalna šema (za minimum/maximum/enum...)
class ParameterModel(BaseModel):
    name: str
    location: str  # "query", "path" ili "header"
    required: bool = False
    schema_type: str = "string"  # prost tip: string/integer/number/boolean/array/object/unknown
    raw_schema: Dict[str, Any] = Field(default_factory=dict)  # originalna šema parametra iz spec-a

# Jedan potpuno parsiran endpoint (putanja + HTTP metoda) — pravi ga
# _extract_endpoint() u openapi_parser.py
class EndpointModel(BaseModel):
    path: str
    method: str
    operation_id: Optional[str] = None
    query_params: List[ParameterModel] = Field(default_factory=list)
    path_params: List[ParameterModel] = Field(default_factory=list)
    header_params: List[ParameterModel] = Field(default_factory=list)
    request_schema: Dict[str, Any] = Field(default_factory=dict)      # pojednostavljeno: {ime_polja: tip}
    raw_request_schema: Dict[str, Any] = Field(default_factory=dict)  # originalna JSON šema tela zahteva
    required_fields: List[str] = Field(default_factory=list)
    response_schemas: Dict[int, Dict[str, Any]] = Field(default_factory=dict)  # {status_kod: JSON šema odgovora}

    # @property — koristi se kao endpoint.has_request_body, bez zagrada
    @property
    def has_request_body(self) -> bool:
        return len(self.request_schema) > 0

# Rezultat jednog izvršenog testa — pravi ga _run_one() u http_runner.py,
# a detector.py mu naknadno dopunjuje anomalies/passed/baseline_valid
class TestResult(BaseModel):
    endpoint: str
    method: str
    status_code: int  # 0 ako odgovor nije ni stigao (timeout/konekcija/greška klijenta)
    response_time_ms: float
    payload: Dict[str, Any] = Field(default_factory=dict)
    response_body: Optional[str] = None
    response_size_bytes: int = 0
    anomalies: List[str] = Field(default_factory=list)
    mutation_type: str = ""  # "baseline", "boundary", "type_mutation", "injection" ili "structure"
    mutated_field: str = ""
    passed: bool = True
    request_schema: Dict[str, Any] = Field(default_factory=dict)
    error_category: Optional[str] = None  # "TIMEOUT", "CONNECT_ERROR", "CONNECTION_CLOSED" (server zatvorio konekciju i posle ponovljenog pokušaja) ili "CLIENT_ERROR" (greška fuzzera, zahtev nije poslat)
    error_message: Optional[str] = None
    baseline_valid: bool = True  # False ako je kontrolni zahtev za isti endpoint pao
    response_schema: Dict[str, Any] = Field(default_factory=dict)  # dokumentovana šema za dobijeni status kod
    response_json: Optional[Any] = None

# Veza između endpointa koji proizvodi resurs (npr. POST vraća id) i
# endpointa koji taj id koristi kao path parametar (npr. GET/PUT/DELETE
# po id-ju) — pravi je extract_resource_links() u dependency_graph.py
class ResourceLink(BaseModel):
    producer_endpoint: str      # npr. "/books"
    producer_method: str        # npr. "POST"
    producer_field: str         # npr. "id" — polje iz response šeme
    consumer_endpoint: str      # npr. "/books/{bookId}"
    consumer_method: str        # npr. "GET" — metoda potrošača (GET/PUT/DELETE)
    consumer_param: str         # npr. "bookId" — path param koji koristi tu vrednost

# Finalni, kompletan rezultat parsiranja spec fajla — pravi ga _parse_raw()
# u openapi_parser.py; sadrži sve endpointe i zavisnosti između njih
class ParsedSpec(BaseModel):
    title: str = "Unknown API"
    version: str = "unknown"
    openapi_version: str
    endpoints: List[EndpointModel] = Field(default_factory=list)
    resource_links: List[ResourceLink] = Field(default_factory=list)

    @property
    def total_endpoints(self) -> int:
        return len(self.endpoints)

    # Obična metoda (ne @property) — vraća čitljiv tekstualni pregled spec-a
    def summary(self) -> str:
        return (
            f"API: {self.title} v{self.version}\n"
            f"OpenAPI: {self.openapi_version}\n"
            f"Endpoints: {self.total_endpoints}"
        )
