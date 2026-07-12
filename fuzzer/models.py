from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class ParameterModel(BaseModel):
    name: str
    location: str  # "query", "path", "header"
    required: bool = False
    schema_type: str = "string"


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

    @property
    def has_request_body(self) -> bool:
        return len(self.request_schema) > 0


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
