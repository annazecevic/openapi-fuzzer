"""
Ovaj fajl validira da li spec fajl zadovoljava osnovna pravila OpenAPI 3.x standarda,
pre nego što parser počne da izvlači podatke iz njega.
"""

# Prilagođen tip greške za OpenAPI validaciju
class OpenAPIValidationError(ValueError):
    def __init__(self, message: str, context: str = "") -> None:
        self.context = context
        full = f"OpenAPI validation error: {message}"
        if context:
            full += f"\n  Hint: {context}"
        super().__init__(full) # prosleđuje kompletnu poruku roditeljskoj klasi ValueError


# Glavna funkcija validacije — redom poziva sve provere, staje čim neka ne prođe
def validate_spec(raw: object) -> None:
    _check_is_dict(raw)
    _check_openapi_field(raw)
    _check_info_block(raw)
    _check_paths_block(raw)

# Proverava da li je ceo spec, na najvišem nivou, rečnik (dict)
def _check_is_dict(raw: object) -> None:
    if not isinstance(raw, dict):
        raise OpenAPIValidationError(
            f"Root mora biti YAML/JSON objekat, dobijen: {type(raw).__name__}.",
            "Da li je ovo validan OpenAPI fajl?"
        )

# Proverava polje "openapi" — prepoznaje zastareli Swagger format, proverava tip i podržanu verziju
def _check_openapi_field(raw: dict) -> None:
    version = raw.get("openapi")
# Polje ne postoji — proveri da li je u pitanju zastareo Swagger 2.x format
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
    # Polje mora biti string
    if not isinstance(version, str):
        raise OpenAPIValidationError(
            f"Polje 'openapi' mora biti string, dobijen: {type(version).__name__}."
        )
    # Podržane su samo verzije 3.0.x i 3.1.x
    if not (version.startswith("3.0") or version.startswith("3.1")):
        raise OpenAPIValidationError(
            f"Nepodržana OpenAPI verzija: '{version}'.",
            "Podržano: OpenAPI 3.0.x i 3.1.x"
        )

# Proverava da "info" blok postoji, jeste rečnik, i sadrži obavezna polja title i version
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

# Proverava da "paths" blok postoji, jeste rečnik, nije prazan, i da svaki ključ počinje sa "/"
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
# Svaki ključ (naziv putanje) mora biti string koji počinje kosom crtom
    for path_key in paths:
        if not isinstance(path_key, str) or not path_key.startswith("/"):
            raise OpenAPIValidationError(
                f"Nevažeći path ključ: {path_key!r}",
                "Svi pathovi moraju biti stringovi koji počinju sa '/'."
            )
