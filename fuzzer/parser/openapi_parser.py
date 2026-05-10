"""
fuzzer/parser/openapi_parser.py
 
Glavna logika parsiranja: OpenAPI 3.x YAML/JSON → lista EndpointModel objekata.
 
Odgovornosti:
  1. Učitaj YAML ili JSON fajl
  2. Validiraj strukturu (via validator.py)
  3. Razreši inline $ref reference
  4. Izvuci endpointe sa parametrima i schemama
  5. Vrati ParsedSpec sa čistim EndpointModel objektima
"""
 
from __future__ import annotations
 
import copy
import json
import logging
from pathlib import Path
from typing import Any
 
import yaml
 
from fuzzer.models import EndpointModel, ParameterModel, ParsedSpec
from fuzzer.parser.validator import OpenAPIValidationError, validate_spec
 
logger = logging.getLogger(__name__)
 
# HTTP metode koje fuzzer podržava u MVP
_SUPPORTED_METHODS = frozenset({"get", "post", "put", "delete"})
 
# Ključevi unutar path item-a koji NISU operacije
_NON_OPERATION_KEYS = frozenset({"summary", "description", "servers", "parameters", "$ref"})
 
 
# ---------------------------------------------------------------------------
# Javni API
# ---------------------------------------------------------------------------
 
def parse_file(path: str | Path) -> ParsedSpec:
    """
    Parsira OpenAPI 3.x spec iz fajla (.yaml, .yml ili .json).
 
    Raises:
        FileNotFoundError: fajl ne postoji
        ValueError: nepodržana ekstenzija
        OpenAPIValidationError: spec nije validan
    """
    path = Path(path)
 
    suffix = path.suffix.lower()
    if suffix not in (".yaml", ".yml", ".json"):
        raise ValueError(
            f"Nepodržana ekstenzija: '{suffix}'. Očekivano: .yaml, .yml ili .json"
        )
 
    if not path.exists():
        raise FileNotFoundError(f"Spec fajl nije pronađen: {path}")
 
    content = path.read_text(encoding="utf-8")
    logger.debug("Učitan fajl: %s (%d bajta)", path, len(content))
 
    return parse_string(content)
 
 
def parse_string(content: str) -> ParsedSpec:
    """
    Parsira OpenAPI 3.x spec iz YAML ili JSON stringa.
    Format se auto-detektuje.
    """
    raw = _load_raw(content)
    return _parse_raw(raw)
 
 
# ---------------------------------------------------------------------------
# Interno: učitavanje
# ---------------------------------------------------------------------------
 
def _load_raw(content: str) -> dict[str, Any]:
    """Deserijalizuje YAML ili JSON string u Python dict."""
    stripped = content.lstrip()
 
    if stripped.startswith("{"):
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenAPIValidationError(f"JSON parse greška: {exc}") from exc
 
    try:
        result = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise OpenAPIValidationError(f"YAML parse greška: {exc}") from exc
 
    if result is None:
        raise OpenAPIValidationError(
            "Spec fajl je prazan ili sadrži samo komentare."
        )
 
    return result
 
 
# ---------------------------------------------------------------------------
# Interno: parsiranje
# ---------------------------------------------------------------------------
 
def _parse_raw(raw: dict[str, Any]) -> ParsedSpec:
    """Validira i izvlači ParsedSpec iz raw dict-a."""
    validate_spec(raw)
 
    # Razreši inline $ref-ove prije ekstrakcije
    resolved = _resolve_refs(raw, raw)
 
    info = resolved.get("info", {})
    endpoints: list[EndpointModel] = []
    skipped: list[str] = []
 
    for path_str, path_item in resolved.get("paths", {}).items():
        if not isinstance(path_item, dict):
            skipped.append(path_str)
            continue
 
        path_level_params = path_item.get("parameters", [])
 
        for method_str, operation in path_item.items():
            if method_str in _NON_OPERATION_KEYS:
                continue
            if method_str not in _SUPPORTED_METHODS:
                logger.debug("Preskačem nepodržanu metodu '%s' na %s", method_str.upper(), path_str)
                continue
            if not isinstance(operation, dict):
                skipped.append(f"{method_str.upper()} {path_str}")
                continue
 
            try:
                ep = _extract_endpoint(path_str, method_str, operation, path_level_params)
                endpoints.append(ep)
                logger.debug("Ekstraktovan: %s %s", method_str.upper(), path_str)
            except Exception as exc:
                logger.warning("Greška pri ekstrakciji %s %s: %s", method_str.upper(), path_str, exc)
                skipped.append(f"{method_str.upper()} {path_str}")
 
    if skipped:
        logger.info("Preskočeni pathovi: %s", skipped)
 
    return ParsedSpec(
        title=str(info.get("title", "Unknown API")),
        version=str(info.get("version", "unknown")),
        openapi_version=str(resolved.get("openapi", "")),
        endpoints=endpoints,
    )
 
 
def _extract_endpoint(
    path: str,
    method: str,
    operation: dict[str, Any],
    path_level_params: list[dict],
) -> EndpointModel:
    """Konvertuje jednu OpenAPI operaciju u EndpointModel."""
 
    merged_params = _merge_parameters(path_level_params, operation.get("parameters", []))
 
    query_params: list[ParameterModel] = []
    path_params: list[ParameterModel] = []
 
    for param_raw in merged_params:
        if not isinstance(param_raw, dict):
            continue
        param = _parse_parameter(param_raw)
        if param is None:
            continue
        if param.location == "query":
            query_params.append(param)
        elif param.location == "path":
            path_params.append(param)
 
    # Request body — samo JSON u MVP
    request_schema: dict[str, Any] = {}
    raw_request_schema: dict[str, Any] = {}
    required_fields: list[str] = []
 
    request_body = operation.get("requestBody")
    if isinstance(request_body, dict):
        json_content = request_body.get("content", {}).get("application/json", {})
        if json_content:
            schema = json_content.get("schema", {})
            raw_request_schema = schema
            required_fields = schema.get("required", [])
            request_schema = _flatten_schema(schema)
 
    # Response schemas — čuvamo za Oracle
    response_schemas: dict[int, dict[str, Any]] = {}
    for status_str, resp_obj in operation.get("responses", {}).items():
        try:
            code = int(status_str)
        except (ValueError, TypeError):
            continue
        if isinstance(resp_obj, dict):
            json_resp = resp_obj.get("content", {}).get("application/json", {})
            if json_resp:
                response_schemas[code] = json_resp.get("schema", {})
 
    return EndpointModel(
        path=path,
        method=method.upper(),
        operation_id=operation.get("operationId"),
        query_params=query_params,
        path_params=path_params,
        request_schema=request_schema,
        raw_request_schema=raw_request_schema,
        required_fields=required_fields,
        response_schemas=response_schemas,
    )
 
 
def _parse_parameter(raw: dict[str, Any]) -> ParameterModel | None:
    """Parsira jedan OpenAPI parameter objekat."""
    name = raw.get("name")
    location = raw.get("in")
 
    if not name or not location:
        return None
    if location not in ("query", "path", "header", "cookie"):
        return None
 
    schema = raw.get("schema", {})
    schema_type = _resolve_type(schema)
 
    return ParameterModel(
        name=str(name),
        location=location,
        required=bool(raw.get("required", location == "path")),
        schema_type=schema_type,
    )
 
 
def _flatten_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Pretvara JSON Schema objekat u flat {ime_polja: tip} mapu.
 
    Primjer:
        {"type": "object", "properties": {"name": {"type": "string"}}}
        → {"name": "string"}
    """
    if not schema or not isinstance(schema, dict):
        return {}
 
    # allOf / anyOf / oneOf — spajamo properties iz svih sub-schema
    for combiner in ("allOf", "anyOf", "oneOf"):
        if combiner in schema:
            merged: dict[str, Any] = {}
            for sub in schema[combiner]:
                if isinstance(sub, dict):
                    merged.update(_flatten_schema(sub))
            return merged
 
    properties = schema.get("properties", {})
    if not properties:
        return {}
 
    return {
        field: _resolve_type(field_schema)
        for field, field_schema in properties.items()
        if isinstance(field_schema, dict)
    }
 
 
def _resolve_type(schema: dict[str, Any]) -> str:
    """Razrješava JSON Schema node u jednostavan tip string."""
    if not schema or not isinstance(schema, dict):
        return "unknown"
 
    t = schema.get("type")
 
    if t == "array":
        return "array"
    if t == "object" or "properties" in schema:
        return "object"
    if t in ("string", "integer", "number", "boolean"):
        return t
 
    # Pokušaj iz combiners
    for combiner in ("allOf", "anyOf", "oneOf"):
        if combiner in schema:
            subs = schema[combiner]
            if isinstance(subs, list) and subs:
                return _resolve_type(subs[0])
 
    return "unknown"
 
 
def _merge_parameters(path_params: list[dict], op_params: list[dict]) -> list[dict]:
    """
    Spaja path-level i operation-level parametre.
    Operation-level parametri pobjeđuju pri konfliktu (isto ime + location).
    """
    op_index = {
        (p["name"], p["in"]): p
        for p in op_params
        if isinstance(p, dict) and "name" in p and "in" in p
    }
    result = list(op_params)
    for p in path_params:
        if isinstance(p, dict) and "name" in p and "in" in p:
            if (p["name"], p["in"]) not in op_index:
                result.append(p)
    return result
 
 
# ---------------------------------------------------------------------------
# Interno: $ref razrješavanje
# ---------------------------------------------------------------------------
 
def _resolve_refs(node: Any, root: dict[str, Any], _depth: int = 0) -> Any:
    """
    Rekurzivno razrješava inline $ref pointere unutar istog dokumenta.
    Eksterni $ref-ovi (http://, file://) se preskačaju — van MVP scopea.
    Max dubina: 50 (zaštita od kružnih referenci).
    """
    if _depth > 50:
        logger.warning("Dostignut max depth za $ref razrješavanje — moguća kružna referenca")
        return node
 
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if isinstance(ref, str) and ref.startswith("#"):
                resolved = _resolve_internal_ref(ref, root)
                if resolved is not None:
                    return _resolve_refs(copy.deepcopy(resolved), root, _depth + 1)
            else:
                logger.debug("Preskačem eksterni $ref: %s", ref)
            return node
 
        return {k: _resolve_refs(v, root, _depth + 1) for k, v in node.items()}
 
    if isinstance(node, list):
        return [_resolve_refs(item, root, _depth + 1) for item in node]
 
    return node
 
 
def _resolve_internal_ref(ref: str, root: dict[str, Any]) -> Any | None:
    """Razrješava JSON Pointer kao '#/components/schemas/User' u root dokumentu."""
    if not ref.startswith("#/"):
        return root if ref == "#" else None
 
    parts = ref[2:].split("/")
    current: Any = root
 
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
 
    return current