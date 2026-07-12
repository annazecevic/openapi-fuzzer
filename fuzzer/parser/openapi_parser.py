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

_SUPPORTED_METHODS = frozenset({"get", "post", "put", "delete"})
_NON_OPERATION_KEYS = frozenset({"summary", "description", "servers", "parameters", "$ref"})


def parse_file(path: str | Path) -> ParsedSpec:
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
    raw = _load_raw(content)
    return _parse_raw(raw)


def _load_raw(content: str) -> dict[str, Any]:
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
        raise OpenAPIValidationError("Spec fajl je prazan ili sadrži samo komentare.")

    return result


def _parse_raw(raw: dict[str, Any]) -> ParsedSpec:
    validate_spec(raw)

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
    merged_params = _merge_parameters(path_level_params, operation.get("parameters", []))

    query_params: list[ParameterModel] = []
    path_params: list[ParameterModel] = []
    header_params: list[ParameterModel] = []

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
        elif param.location == "header":
            header_params.append(param)

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
        header_params=header_params,
        request_schema=request_schema,
        raw_request_schema=raw_request_schema,
        required_fields=required_fields,
        response_schemas=response_schemas,
    )


def _parse_parameter(raw: dict[str, Any]) -> ParameterModel | None:
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
    if not schema or not isinstance(schema, dict):
        return {}

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
    if not schema or not isinstance(schema, dict):
        return "unknown"

    t = schema.get("type")

    if t == "array":
        return "array"
    if t == "object" or "properties" in schema:
        return "object"
    if t in ("string", "integer", "number", "boolean"):
        return t

    for combiner in ("allOf", "anyOf", "oneOf"):
        if combiner in schema:
            subs = schema[combiner]
            if isinstance(subs, list) and subs:
                return _resolve_type(subs[0])

    return "unknown"


def _merge_parameters(path_params: list[dict], op_params: list[dict]) -> list[dict]:
    # Operation-level parametri imaju prioritet nad path-level pri konfliktu
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


def _resolve_refs(node: Any, root: dict[str, Any], _depth: int = 0) -> Any:
    # Max dubina 50 — zaštita od kružnih $ref referenci u spec-u
    if _depth > 50:
        logger.warning("Dostignut max depth za $ref razrešavanje — moguća kružna referenca")
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
