_LONG_STRING = "A" * 10_000
_SQL_INJECTION = "' OR '1'='1"
_NULL_BYTE = "test\x00injection"


CATALOG: dict[str, list] = {

    "string": [
        "",
        " ",
        _LONG_STRING,
        _SQL_INJECTION,
        _NULL_BYTE,        # null bajt može prekinuti C-bazirane parsere iza API-ja
        123,
        None,
        [],
        True,
        '{"a":{"b":{"c":{"d":{"e":"deep"}}}}}',
        "A" * 50_000,
    ],

    "integer": [
        0,
        -1,
        99_999_999,
        -99_999_999,
        2**31 - 1,         # MAX_INT — klasičan 32-bit overflow
        -(2**31),
        "abc",
        "",
        None,
        3.14,
        True,
    ],

    "boolean": [
        "true",
        "false",
        "yes",
        1,
        0,
        None,
        "",
        "random_string",
    ],

    "number": [
        0,
        -1,
        0.0,
        -0.001,
        1e308,
        -1e308,
        float("inf"),      # malo API-ja zna da serialiuze infinity u JSON
        float("nan"),
        "abc",
        None,
    ],

    "array": [
        [],
        [None],
        ["A" * 1000] * 100,
        "not_an_array",
        None,
        {},
        [1, "two", None, True],
    ],

    "object": [
        {},
        None,
        "not_an_object",
        [],
        {"__proto__": {"admin": True}},  # prototype pollution
        {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": {"l7": {"l8": "deep"}}}}}}}},
        [{"id": i, "value": "x" * 100} for i in range(500)],
    ],

    "unknown": [
        None,
        "",
        0,
        [],
    ],
}


def get_mutations(schema_type: str) -> list:
    return CATALOG.get(schema_type, CATALOG["unknown"])
