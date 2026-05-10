from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
 
 
# ---------------------------------------------------------------------------
# Parameter model — query, path, header parametri
# ---------------------------------------------------------------------------
 
class ParameterModel(BaseModel):
    name: str
    location: str          # "query", "path", "header"
    required: bool = False
    schema_type: str = "string"
 
 
# ---------------------------------------------------------------------------
# EndpointModel — jedan API endpoint
# Koriste ga: Parser, Scenario Generator, HTTP Runner, Oracle
# ---------------------------------------------------------------------------
 
class EndpointModel(BaseModel):
    path: str
    method: str
    operation_id: Optional[str] = None
    query_params: List[ParameterModel] = Field(default_factory=list)
    path_params: List[ParameterModel] = Field(default_factory=list)
    request_schema: Dict[str, Any] = Field(default_factory=dict)
    raw_request_schema: Dict[str, Any] = Field(default_factory=dict)
    required_fields: List[str] = Field(default_factory=list)
    response_schemas: Dict[int, Dict[str, Any]] = Field(default_factory=dict)
 
    @property
    def has_request_body(self) -> bool:
        return len(self.request_schema) > 0
 
 
# ---------------------------------------------------------------------------
# TestResult — rezultat jednog fuzz testa
# Koriste ga: HTTP Runner, Oracle, Report Generator
# ---------------------------------------------------------------------------
 
class TestResult(BaseModel):
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    payload: Dict[str, Any] = Field(default_factory=dict)
    anomalies: List[str] = Field(default_factory=list)
    mutation_type: str = ""
    mutated_field: str = ""
    passed: bool = True
 
 
# ---------------------------------------------------------------------------
# ParsedSpec — rezultat parsiranja celog OpenAPI fajla
# ---------------------------------------------------------------------------
 
class ParsedSpec(BaseModel):
    title: str = "Unknown API"
    version: str = "unknown"
    openapi_version: str
    endpoints: List[EndpointModel] = Field(default_factory=list)
 
    @property
    def total_endpoints(self) -> int:
        return len(self.endpoints)
 
    def summary(self) -> str:
        return (
            f"API: {self.title} v{self.version}\n"
            f"OpenAPI: {self.openapi_version}\n"
            f"Endpoints: {self.total_endpoints}"
        )