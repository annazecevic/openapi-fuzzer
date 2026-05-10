"""
fuzzer/parser/validator.py
 
Proverava da li je OpenAPI dokument strukturno ispravan
pre nego što ga parser pokuša da obradi.
 
Filozofija: fail fast sa jasnom porukom o grešci.
"""
 
 
class OpenAPIValidationError(ValueError):
    """Baca se kada spec ne prođe strukturnu validaciju."""
 
    def __init__(self, message: str, context: str = "") -> None:
        self.context = context
        full = f"OpenAPI validation error: {message}"
        if context:
            full += f"\n  Hint: {context}"
        super().__init__(full)
 
 
def validate_spec(raw: object) -> None:
    """
    Ulazna tačka — pokreće sve provjere redom.
    Baca OpenAPIValidationError na prvoj grešci.
    """
    _check_is_dict(raw)
    _check_openapi_field(raw)
    _check_info_block(raw)
    _check_paths_block(raw)
 
 
# ---------------------------------------------------------------------------
# Interne provjere
# ---------------------------------------------------------------------------
 
def _check_is_dict(raw: object) -> None:
    if not isinstance(raw, dict):
        raise OpenAPIValidationError(
            f"Root mora biti YAML/JSON objekat, dobijen: {type(raw).__name__}.",
            "Da li je ovo validan OpenAPI fajl?"
        )
 
 
def _check_openapi_field(raw: dict) -> None:
    version = raw.get("openapi")
 
    if version is None:
        if "swagger" in raw:
            sw = raw.get("swagger", "?")
            raise OpenAPIValidationError(
                f"Swagger {sw} (OpenAPI 2.x) nije podržan.",
                "Konvertuj spec na: https://converter.swagger.io"
            )
        raise OpenAPIValidationError(
            "Nedostaje obavezno polje 'openapi'.",
            "Fajl mora počinjati sa: openapi: '3.x.y'"
        )
 
    if not isinstance(version, str):
        raise OpenAPIValidationError(
            f"Polje 'openapi' mora biti string, dobijen: {type(version).__name__}."
        )
 
    if not (version.startswith("3.0") or version.startswith("3.1")):
        raise OpenAPIValidationError(
            f"Nepodržana OpenAPI verzija: '{version}'.",
            "Podržano: OpenAPI 3.0.x i 3.1.x"
        )
 
 
def _check_info_block(raw: dict) -> None:
    info = raw.get("info")
 
    if info is None:
        raise OpenAPIValidationError(
            "Nedostaje obavezni blok 'info'.",
            "Blok 'info' mora sadržati 'title' i 'version'."
        )
    if not isinstance(info, dict):
        raise OpenAPIValidationError(
            f"Polje 'info' mora biti objekat, dobijen: {type(info).__name__}."
        )
    for key in ("title", "version"):
        if key not in info:
            raise OpenAPIValidationError(
                f"Nedostaje obavezno polje 'info.{key}'."
            )
 
 
def _check_paths_block(raw: dict) -> None:
    paths = raw.get("paths")
 
    if paths is None:
        raise OpenAPIValidationError(
            "Nedostaje obavezni blok 'paths'.",
            "Spec bez paths-a nema šta da testira fuzzer."
        )
    if not isinstance(paths, dict):
        raise OpenAPIValidationError(
            f"Polje 'paths' mora biti objekat, dobijen: {type(paths).__name__}."
        )
    if len(paths) == 0:
        raise OpenAPIValidationError(
            "Blok 'paths' je prazan.",
            "Dodaj barem jedan endpoint u spec."
        )
 
    for path_key in paths:
        if not isinstance(path_key, str) or not path_key.startswith("/"):
            raise OpenAPIValidationError(
                f"Nevažeći path ključ: {path_key!r}",
                "Svi pathovi moraju biti stringovi koji počinju sa '/'."
            )