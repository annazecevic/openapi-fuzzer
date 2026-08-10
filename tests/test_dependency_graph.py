from fuzzer.models import EndpointModel, ParameterModel
from fuzzer.parser.dependency_graph import extract_resource_links


def _producer(response_schema: dict) -> EndpointModel:
    return EndpointModel(
        path="/books",
        method="POST",
        response_schemas={200: response_schema},
    )


def test_finds_link_for_producer_and_consumer():
    producer = _producer({
        "type": "object",
        "properties": {"id": {"type": "integer"}, "title": {"type": "string"}},
    })
    consumer = EndpointModel(
        path="/books/{bookId}",
        method="GET",
        path_params=[ParameterModel(name="bookId", location="path", required=True, schema_type="integer")],
    )

    links = extract_resource_links([producer, consumer])

    assert len(links) == 1
    link = links[0]
    assert link.producer_endpoint == "/books"
    assert link.producer_method == "POST"
    assert link.producer_field == "id"
    assert link.consumer_endpoint == "/books/{bookId}"
    assert link.consumer_param == "bookId"


def test_no_link_when_response_schema_missing_id_field():
    producer = _producer({
        "type": "object",
        "properties": {"title": {"type": "string"}},
    })
    consumer = EndpointModel(
        path="/books/{bookId}",
        method="GET",
        path_params=[ParameterModel(name="bookId", location="path", required=True, schema_type="integer")],
    )

    links = extract_resource_links([producer, consumer])

    assert links == []


def test_no_link_when_consumer_path_does_not_share_producer_prefix():
    producer = _producer({
        "type": "object",
        "properties": {"id": {"type": "integer"}},
    })
    unrelated = EndpointModel(
        path="/authors/{authorId}",
        method="GET",
        path_params=[ParameterModel(name="authorId", location="path", required=True, schema_type="integer")],
    )

    links = extract_resource_links([producer, unrelated])

    assert links == []
