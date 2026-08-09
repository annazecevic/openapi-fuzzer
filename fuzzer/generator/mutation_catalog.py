#rečnik loših vrednosti po tipu (string, integer, boolean...)

from typing import Any

_LONG_STRING = "A" * 10_000
_SQL_INJECTION = "' OR '1'='1"
_NULL_BYTE = "test\x00injection"


CATALOG: dict[str, list[tuple[str, Any]]] = {

    "string": [
        ("boundary", ""),
        ("boundary", " "),
        ("boundary", _LONG_STRING),
        ("injection", _SQL_INJECTION),
        ("injection", _NULL_BYTE),
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
        ("boundary", -(2**31)),
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
        ("boundary", float("inf")),     # beskonačnost
        ("boundary", float("nan")),     # "Not a Number"
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
        ("boundary", [{"id": i, "value": "x" * 100} for i in range(500)]),
    ],

    "unknown": [
        ("type_mutation", None),
        ("type_mutation", ""),
        ("type_mutation", 0),
        ("type_mutation", []),
    ],
}


def get_mutations(schema_type: str) -> list[tuple[str, Any]]:
    return CATALOG.get(schema_type, CATALOG["unknown"])
