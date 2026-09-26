# Parser OpenAPI 3.x specifikacije — učitava YAML ili JSON fajl, validira
# osnovnu strukturu, razrešava interne $ref reference, i za svaku podržanu
# HTTP operaciju pravi EndpointModel (parametri, telo zahteva, šeme odgovora).
# Na kraju pronalazi zavisnosti između endpointa i sve vraća kao ParsedSpec.

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

import yaml

from fuzzer.models import EndpointModel, ParameterModel, ParsedSpec
from fuzzer.parser.dependency_graph import extract_resource_links
from fuzzer.parser.validator import OpenAPIValidationError, validate_spec

logger = logging.getLogger(__name__)  # logger za praćenje rada parsera

_SUPPORTED_METHODS = frozenset({"get", "post", "put", "delete"})  # HTTP metode koje fuzzer podržava
_NON_OPERATION_KEYS = frozenset({"summary", "description", "servers", "parameters", "$ref"})  # ključevi u path objektu koji nisu HTTP operacije

# Javna ulazna tačka — proverava ekstenziju i postojanje fajla, čita ga kao
# tekst i prosleđuje sadržaj funkciji parse_string()
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

# Parsira spec zadat kao tekst u dve faze: tekst → Python rečnik (_load_raw),
# pa rečnik → ParsedSpec (_parse_raw)
def parse_string(content: str) -> ParsedSpec:
    raw = _load_raw(content)
    return _parse_raw(raw)

# Pretvara tekst spec-a u Python rečnik — ako počinje sa "{" čita se kao JSON,
# inače kao YAML; greške u sintaksi se prijavljuju kao OpenAPIValidationError
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

    # Prazan fajl (ili samo komentari) daje None umesto rečnika
    if result is None:
        raise OpenAPIValidationError("Spec fajl je prazan ili sadrži samo komentare.")

    return result

# Od sirovog rečnika pravi finalni ParsedSpec: validira strukturu, razrešava
# $ref reference, prolazi kroz sve putanje i operacije i izvlači endpointe;
# neispravni delovi se preskaču i beleže u log umesto da obore ceo parser
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

        # Parametri definisani na nivou putanje važe za sve njene operacije
        path_level_params = path_item.get("parameters", [])

        # Prolazi kroz sve ključeve path objekta (get, post, parameters, summary...)
        for method_str, operation in path_item.items():
            # Ključ nije HTTP operacija (summary, description, servers, parameters, $ref)
            if method_str in _NON_OPERATION_KEYS:
                continue
            # HTTP metoda koju fuzzer ne podržava (npr. patch, head, options)
            if method_str not in _SUPPORTED_METHODS:
                logger.debug("Preskačem nepodržanu metodu '%s' na %s", method_str.upper(), path_str)
                continue
            # Sadržaj operacije mora biti rečnik
            if not isinstance(operation, dict):
                skipped.append(f"{method_str.upper()} {path_str}")
                continue
            # Izvlačenje podataka o endpointu — jedan loš endpoint ne sme
            # da obori parsiranje celog spec-a
            try:
                ep = _extract_endpoint(path_str, method_str, operation, path_level_params)
                endpoints.append(ep)
            except Exception as exc:
                logger.warning("Greška pri ekstrakciji %s %s: %s", method_str.upper(), path_str, exc)
                skipped.append(f"{method_str.upper()} {path_str}")

    if skipped:
        logger.info("Preskočeni pathovi: %s", skipped)

    resource_links = extract_resource_links(endpoints)

    return ParsedSpec(
        title=str(info.get("title", "Unknown API")),
        version=str(info.get("version", "unknown")),
        openapi_version=str(resolved.get("openapi", "")),  # verzija OpenAPI standarda kojom je spec napisan
        endpoints=endpoints,
        resource_links=resource_links,
    )

# Izvlači sve detalje jednog endpointa (putanja + metoda): parametre
# razvrstane po lokaciji, JSON šemu tela zahteva i JSON šeme odgovora
def _extract_endpoint(
    path: str,
    method: str,
    operation: dict[str, Any],
    path_level_params: list[dict],
) -> EndpointModel:
    # Spaja parametre sa nivoa putanje i sa nivoa operacije
    merged_params = _merge_parameters(path_level_params, operation.get("parameters", []))

    query_params: list[ParameterModel] = []
    path_params: list[ParameterModel] = []
    header_params: list[ParameterModel] = []

    for param_raw in merged_params:
        # Loše napisan parametar (npr. string umesto objekta) se preskače
        if not isinstance(param_raw, dict):
            continue
        param = _parse_parameter(param_raw)
        if param is None:  # nedostaje ime ili lokacija
            continue
        # Razvrstava parametar u odgovarajuću listu po lokaciji
        if param.location == "query":
            query_params.append(param)
        elif param.location == "path":
            path_params.append(param)
        elif param.location == "header":
            header_params.append(param)

    request_schema: dict[str, Any] = {}      # pojednostavljena šema {ime_polja: tip} — fuzzer iz nje vidi koja polja postoje
    raw_request_schema: dict[str, Any] = {}  # originalna, nepromenjena JSON šema tela (za jsonschema validaciju)
    required_fields: list[str] = []          # nazivi obaveznih polja

    # Telo zahteva se čita samo iz application/json sadržaja
    request_body = operation.get("requestBody")
    if isinstance(request_body, dict):
        json_content = request_body.get("content", {}).get("application/json", {})
        if json_content:
            schema = json_content.get("schema", {})
            raw_request_schema = schema
            required_fields = schema.get("required", [])
            request_schema = _flatten_schema(schema)

    # Šeme odgovora po status kodu — ključevi koji nisu broj (npr. "default") se preskaču
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

# Pretvara jedan sirovi parametar iz spec-a u ParameterModel; vraća None ako
# parametar nema ime, nema lokaciju, ili lokacija nije poznata OpenAPI vrednost
def _parse_parameter(raw: dict[str, Any]) -> ParameterModel | None:
    name = raw.get("name")
    location = raw.get("in")
    # Bez imena ili lokacije parametar nema smisla — odbacuje se
    if not name or not location:
        return None
    # Lokacija mora biti jedna od poznatih OpenAPI vrednosti
    if location not in ("query", "path", "header", "cookie"):
        return None

    schema = raw.get("schema", {})  # šema opisuje tip podatka parametra
    schema_type = _resolve_type(schema)

    return ParameterModel(
        name=str(name),
        location=location,
        required=bool(raw.get("required", location == "path")),  # path parametri su po standardu uvek obavezni
        schema_type=schema_type,
        raw_schema=schema,
    )

# Pretvara JSON šemu objekta u prostu mapu {ime_polja: tip}; kod allOf/anyOf/
# oneOf spaja polja svih pod-šema u jednu mapu
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

# Za jednu JSON šemu određuje prost tip (string/integer/number/boolean/array/
# object); kod allOf/anyOf/oneOf uzima tip prve pod-šeme, a ako tip ne može
# da se odredi vraća "unknown"
def _resolve_type(schema: dict[str, Any]) -> str:
    if not schema or not isinstance(schema, dict):
        return "unknown"

    t = schema.get("type")

    if t == "array":
        return "array"
    # Šema sa "properties" je objekat i kad "type" nije eksplicitno naveden
    if t == "object" or "properties" in schema:
        return "object"
    if t in ("string", "integer", "number", "boolean"):
        return t

    for combiner in ("allOf", "anyOf", "oneOf"):
        if combiner in schema:
            subs = schema[combiner]
            if isinstance(subs, list) and subs:
                return _resolve_type(subs[0])  # uzima se samo tip prve pod-šeme

    return "unknown"

# Spaja parametre sa nivoa putanje i sa nivoa operacije; parametar se
# identifikuje parom (ime, lokacija), a operation-level ima prioritet
def _merge_parameters(path_params: list[dict], op_params: list[dict]) -> list[dict]:
    # Indeks operation-level parametara za brzu proveru da li parametar već postoji
    op_index = {
        (p["name"], p["in"]): p  # ključ je par (ime, lokacija), vrednost je ceo parametar
        for p in op_params
        if isinstance(p, dict) and "name" in p and "in" in p  # samo ispravno definisani
    }
    # Operation-level parametri su osnova rezultata (oni imaju prioritet)
    result = list(op_params)
    # Dodaju se path-level parametri koji NISU već pokriveni operation-level parametrima
    for p in path_params:
        if isinstance(p, dict) and "name" in p and "in" in p:
            if (p["name"], p["in"]) not in op_index:
                result.append(p)
    return result

# Rekurzivno prolazi kroz ceo spec i svaku internu $ref referencu (npr.
# "#/components/schemas/Book") zamenjuje njenim stvarnim sadržajem; eksterne
# ili nepronađene reference ostaju nepromenjene
def _resolve_refs(node: Any, root: dict[str, Any], _depth: int = 0) -> Any:
    # Zaštita od beskonačne rekurzije kod kružnih referenci
    if _depth > 50:
        logger.warning("Dostignut max depth za $ref razrešavanje — moguća kružna referenca")
        return node

    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if isinstance(ref, str) and ref.startswith("#"):
                resolved = _resolve_internal_ref(ref, root)
                if resolved is not None:
                    # Kopija, da razrešavanje ne menja original na koji i druge reference pokazuju
                    return _resolve_refs(copy.deepcopy(resolved), root, _depth + 1)
            else:
                logger.debug("Preskačem eksterni $ref: %s", ref)
            return node

        return {k: _resolve_refs(v, root, _depth + 1) for k, v in node.items()}

    if isinstance(node, list):
        return [_resolve_refs(item, root, _depth + 1) for item in node]

    return node

# Prati $ref putanju (JSON Pointer, npr. "#/components/schemas/Book") korak
# po korak kroz spec — ulazi u rečnike po ključu i u liste po indeksu, dok ne
# pronađe traženi sadržaj; vraća None ako putanja ne postoji
def _resolve_internal_ref(ref: str, root: dict[str, Any]) -> Any | None:
    if not ref.startswith("#/"):
        return root if ref == "#" else None

    parts = ref[2:].split("/")
    current: Any = root

    for part in parts:
        # JSON Pointer escape: "~1" znači "/", a "~0" znači "~"
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
