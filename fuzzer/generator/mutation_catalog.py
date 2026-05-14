"""
fuzzer/generator/mutation_catalog.py
 
Katalog mutacija: za svaki OpenAPI tip podatka definiše
listu namerno loših vrednosti koje fuzzer šalje API-ju.
 
Kako se čita:
    CATALOG["string"] → lista loših string vrednosti
    CATALOG["integer"] → lista loših integer vrednosti
    itd.
"""
 
# Velika vrednost za testiranje buffer overflow / performansi
_LONG_STRING = "A" * 10_000
 
# SQL injection — čest bezbednosni propust
_SQL_INJECTION = "' OR '1'='1"
 
# Null bajt — može pokvariti C-bazirane sisteme iza API-ja
_NULL_BYTE = "test\x00injection"
 
 
CATALOG: dict[str, list] = {
 
    "string": [
        "",                  # prazan string — čest edge case
        " ",                 # samo razmak
        _LONG_STRING,        # ekstremno dugačak string (performanse, buffer)
        _SQL_INJECTION,      # SQL injection pokušaj
        _NULL_BYTE,          # null bajt
        123,                 # integer umjesto stringa (type mutation)
        None,                # null — šta se desi ako pošaljemo ništa?
        [],                  # lista umjesto stringa
        True,                # boolean umjesto stringa
    ],
 
    "integer": [
        0,                   # nula — boundary
        -1,                  # negativan broj — čest edge case
        99_999_999,          # veoma veliki broj
        -99_999_999,         # veoma mali broj
        2**31 - 1,           # MAX_INT (32-bit) — klasičan overflow
        -(2**31),            # MIN_INT (32-bit)
        "abc",               # string umjesto integera (type mutation)
        "",                  # prazan string
        None,                # null
        3.14,                # decimalni broj umjesto celog
        True,                # boolean (u Pythonu je bool podklasa int — API možda prihvati)
    ],
 
    "boolean": [
        "true",              # string "true" — API možda ne parsira ispravno
        "false",             # string "false"
        "yes",               # neformalni boolean
        1,                   # integer 1 (često se koristi kao true)
        0,                   # integer 0 (često se koristi kao false)
        None,                # null
        "",                  # prazan string
        "random_string",     # potpuno nevalidan
    ],
 
    "number": [
        0,                   # nula
        -1,                  # negativan
        0.0,                 # nula kao float
        -0.001,              # mali negativan float
        1e308,               # veoma veliki float (blizu Python max)
        -1e308,              # veoma mali float
        float("inf"),        # beskonačnost — malo API-ja ovo handleuje
        float("nan"),        # Not a Number — čest uzrok crash-a
        "abc",               # string umjesto broja
        None,                # null
    ],
 
    "array": [
        [],                  # prazna lista — boundary
        [None],              # lista sa null elementom
        ["A" * 1000] * 100,  # lista sa 100 dugih stringova (performanse)
        "not_an_array",      # string umjesto liste (type mutation)
        None,                # null umjesto liste
        {},                  # objekat umjesto liste
        [1, "two", None, True],  # mješoviti tipovi unutar liste
    ],
 
    "object": [
        {},                  # prazan objekat
        None,                # null
        "not_an_object",     # string umjesto objekta
        [],                  # lista umjesto objekta
        {"__proto__": {"admin": True}},  # prototype pollution pokušaj
    ],
 
    # Fallback za tipove koje ne prepoznajemo
    "unknown": [
        None,
        "",
        0,
        [],
    ],
}
 
 
def get_mutations(schema_type: str) -> list:
    """
    Vrati listu mutacija za dati OpenAPI tip.
 
    Args:
        schema_type: tip iz OpenAPI spec-a ("string", "integer", itd.)
 
    Returns:
        Lista loših vrednosti za taj tip.
        Ako tip nije poznat, vraća fallback listu.
 
    Primer:
        get_mutations("string") → ["", " ", "AAAA...", ...]
        get_mutations("integer") → [0, -1, 99999, "abc", ...]
    """
    return CATALOG.get(schema_type, CATALOG["unknown"])