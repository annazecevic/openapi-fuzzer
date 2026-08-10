# Statička analiza spec-a (bez izvršavanja zahteva) koja pronalazi zavisnosti
# između endpointa — koji endpoint proizvodi resurs (npr. POST vraća "id")
# i koji ga koristi kao path parametar (npr. GET/PUT/DELETE po tom id-ju).

from fuzzer.models import EndpointModel, ResourceLink

# Provera da li POST endpoint dokumentuje "id" polje u properties bilo kog
# 2xx response schema-e — takav endpoint se smatra proizvođačem resursa
def _is_producer(endpoint: EndpointModel) -> bool:
    if endpoint.method != "POST":
        return False
    for status_code, schema in endpoint.response_schemas.items():
        if 200 <= status_code < 300 and isinstance(schema, dict):
            if "id" in schema.get("properties", {}):
                return True
    return False

# Pronalazi sve zavisnosti između endpointa: za svaki POST proizvođač
# resursa (ima "id" u response šemi), povezuje ga sa svakim drugim
# endpointom čiji path počinje istim prefiksom (npr. "/books" → "/books/{bookId}")
def extract_resource_links(endpoints: list[EndpointModel]) -> list[ResourceLink]:
    links: list[ResourceLink] = []

    producers = [ep for ep in endpoints if _is_producer(ep)]

    for producer in producers:
        prefix = producer.path + "/"
        for endpoint in endpoints:
            if endpoint.method not in ("GET", "PUT", "DELETE"):
                continue
            if not endpoint.path_params:
                continue
            if not endpoint.path.startswith(prefix):
                continue

            consumer_param = endpoint.path_params[0].name
            links.append(ResourceLink(
                producer_endpoint=producer.path,
                producer_method=producer.method,
                producer_field="id",
                consumer_endpoint=endpoint.path,
                consumer_param=consumer_param,
            ))

    return links
