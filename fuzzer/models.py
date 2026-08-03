from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

# Pydantic model jednog parametra endpoint-a (query/path/header) —
# automatski validira tipove, za razliku od obične @dataclass
class ParameterModel(BaseModel):
    name: str
    location: str  # "query", "path", "header"
    required: bool = False
    schema_type: str = "string"

# Pydantic model jednog potpuno parsiranog endpoint-a — ovo pravi
# _extract_endpoint() u parseru
class EndpointModel(BaseModel):
    path: str
    method: str
    operation_id: Optional[str] = None
    query_params: List[ParameterModel] = Field(default_factory=list)
    path_params: List[ParameterModel] = Field(default_factory=list)
    header_params: List[ParameterModel] = Field(default_factory=list)
    request_schema: Dict[str, Any] = Field(default_factory=dict)
    raw_request_schema: Dict[str, Any] = Field(default_factory=dict)
    required_fields: List[str] = Field(default_factory=list)
    response_schemas: Dict[int, Dict[str, Any]] = Field(default_factory=dict)
    # @property — koristi se kao endpoint.has_request_body, bez zagrada
    @property
    def has_request_body(self) -> bool:
        return len(self.request_schema) > 0

# Pydantic model rezultata jednog izvršenog testa — ovo pravi
# _run_one() u runner fajlu
class TestResult(BaseModel):
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    payload: Dict[str, Any] = Field(default_factory=dict)
    response_body: Optional[str] = None
    response_size_bytes: int = 0
    anomalies: List[str] = Field(default_factory=list)
    mutation_type: str = ""
    mutated_field: str = ""
    passed: bool = True
    request_schema: Dict[str, Any] = Field(default_factory=dict)
    error_category: Optional[str] = None
    error_message: Optional[str] = None

# Finalni, kompletan rezultat parsiranja spec fajla — ovo pravi
# _parse_raw() u parseru, sadrži listu svih EndpointModel objekata
class ParsedSpec(BaseModel):
    title: str = "Unknown API"
    version: str = "unknown"
    openapi_version: str
    endpoints: List[EndpointModel] = Field(default_factory=list)

    @property
    def total_endpoints(self) -> int:
        return len(self.endpoints)
# Obična metoda (ne @property) — generiše čitljiv tekstualni pregled spec-a
    def summary(self) -> str:
        return (
            f"API: {self.title} v{self.version}\n"
            f"OpenAPI: {self.openapi_version}\n"
            f"Endpoints: {self.total_endpoints}"
        )
