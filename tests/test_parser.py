import pytest

from fuzzer.parser import OpenAPIValidationError, parse_file


def test_json_and_yaml_specs_parse_to_identical_result():
    json_spec = parse_file("examples/bookstore.json")
    yaml_spec = parse_file("examples/bookstore.yaml")

    assert len(json_spec.endpoints) == len(yaml_spec.endpoints)
    assert json_spec.title == yaml_spec.title
    assert json_spec.version == yaml_spec.version


def test_malformed_json_raises_validation_error(tmp_path):
    broken_json = tmp_path / "broken.json"
    broken_json.write_text('{"openapi": "3.0.3", "info": {"title": "Broken"', encoding="utf-8")

    with pytest.raises(OpenAPIValidationError):
        parse_file(str(broken_json))
