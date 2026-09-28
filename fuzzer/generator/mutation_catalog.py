# Katalog "loših" vrednosti za fuzzing, grupisan po tipu polja (string,
# integer, boolean...). Svaka vrednost ima kategoriju koja opisuje vrstu testa:
#   boundary      — granične vrednosti (prazno, predugačko, 0, MAX_INT...)
#   type_mutation — vrednost pogrešnog tipa (npr. broj umesto stringa)
#   injection     — pokušaji ubacivanja (SQL injection, null bajt...)
#   structure     — neočekivana struktura (duboko ugnježden objekat)

from typing import Any

_LONG_STRING = "A" * 10_000
_SQL_INJECTION = "' OR '1'='1"
_NULL_BYTE = "test\x00injection"


# Tip polja → lista parova (kategorija, loša vrednost)
CATALOG: dict[str, list[tuple[str, Any]]] = {

    "string": [
        ("boundary", ""),
        ("boundary", " "),
        ("boundary", _LONG_STRING),
        ("injection", _SQL_INJECTION),          # klasičan SQL injection
        ("injection", _NULL_BYTE),              # null bajt — može da preseče string u C bibliotekama
        ("type_mutation", 123),
        ("type_mutation", None),
        ("type_mutation", []),
        ("type_mutation", True),
        ("injection", '{"a":{"b":{"c":{"d":{"e":"deep"}}}}}'),  # JSON kao string — testira da li se pogrešno parsira
        ("boundary", "A" * 50_000),
    ],

    "integer": [
        ("boundary", 0),
        ("boundary", -1),
        ("boundary", 99_999_999),
        ("boundary", -99_999_999),
        ("boundary", 2**31 - 1),         # MAX_INT — klasičan 32-bit overflow
        ("boundary", -(2**31)),         # MIN_INT
        ("type_mutation", "abc"),
        ("type_mutation", ""),
        ("type_mutation", None),
        ("type_mutation", 3.14),
        ("type_mutation", True),
    ],

    "boolean": [
        ("type_mutation", "true"),
        ("type_mutation", "false"),
        ("type_mutation", "yes"),
        ("type_mutation", 1),
        ("type_mutation", 0),
        ("type_mutation", None),
        ("type_mutation", ""),
        ("type_mutation", "random_string"),
    ],

    "number": [
        ("boundary", 0),
        ("boundary", -1),
        ("boundary", 0.0),
        ("boundary", -0.001),
        ("boundary", 1e308),
        ("boundary", -1e308),           # ekstremno veliki/mali brojevi
        # inf i nan namerno izostavljeni — nisu validan JSON, httpx ih ne može poslati
        ("type_mutation", "abc"),
        ("type_mutation", None),
    ],

    "array": [
        ("boundary", []),
        ("boundary", [None]),
        ("boundary", ["A" * 1000] * 100),
        ("type_mutation", "not_an_array"),
        ("type_mutation", None),
        ("type_mutation", {}),
        ("type_mutation", [1, "two", None, True]),
    ],

    "object": [
        ("boundary", {}),
        ("type_mutation", None),
        ("type_mutation", "not_an_object"),
        ("type_mutation", []),
        ("injection", {"__proto__": {"admin": True}}),  # prototype pollution
        ("structure", {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": "deep"}}}}}}}}),
        ("boundary", [{"id": i, "value": "x" * 100} for i in range(500)]),  # veliki niz umesto objekta
    ],

    # Rezervna lista za polja čiji tip parser nije mogao da odredi
    "unknown": [
        ("type_mutation", None),
        ("type_mutation", ""),
        ("type_mutation", 0),
        ("type_mutation", []),
    ],
}


# Vraća fiksne loše vrednosti za dati tip iz kataloga; nepoznat tip dobija listu "unknown"
def get_mutations(schema_type: str) -> list[tuple[str, Any]]:
    return CATALOG.get(schema_type, CATALOG["unknown"])


# Generiše boundary vrednosti IZRAČUNATE iz stvarno deklarisanih granica u
# OpenAPI šemi (minimum/maximum/maxLength/minLength/enum), umesto generičkih
# fiksnih vrednosti iz kataloga — za svaku granicu testira se vrednost tačno
# na granici (mora proći) i odmah preko nje (mora biti odbijena)
def boundary_values_from_schema(raw_schema: dict) -> list[tuple[str, Any]]:
    values: list[tuple[str, Any]] = []
    if not raw_schema:
        return values

    if "maximum" in raw_schema:
        m = raw_schema["maximum"]
        values.append(("boundary", m))
        values.append(("boundary", m + 1))
    if "minimum" in raw_schema:
        m = raw_schema["minimum"]
        values.append(("boundary", m))
        values.append(("boundary", m - 1))
    if "maxLength" in raw_schema:
        n = raw_schema["maxLength"]
        values.append(("boundary", "A" * n))
        values.append(("boundary", "A" * (n + 1)))
    if "minLength" in raw_schema:
        n = raw_schema["minLength"]
        if n > 0:  # string kraći od minimuma postoji samo ako je minLength > 0
            values.append(("boundary", "A" * (n - 1)))
        values.append(("boundary", "A" * n))
    if "enum" in raw_schema and raw_schema["enum"]:
        values.append(("boundary", "NIJE_U_ENUM_LISTI"))  # vrednost van dozvoljene liste

    return values
