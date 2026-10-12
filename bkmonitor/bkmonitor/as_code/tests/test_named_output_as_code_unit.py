import json
from pathlib import Path
from unittest import mock

import pytest
import yaml
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema
from schema import SchemaError

from bkmonitor.as_code.parse_yaml import StrategyConfigParser
from bkmonitor.as_code.schema import StrategySchema
from bkmonitor.strategy.new_strategy import Strategy

AS_CODE_PATH = Path(__file__).parents[1]
DATA_PATH = AS_CODE_PATH / "tests/data/rule"


def load_rule_config(filename: str) -> dict:
    with (DATA_PATH / filename).open() as f:
        return yaml.safe_load(f.read())


def make_parser():
    return StrategyConfigParser(2, {"ops.yaml": 1}, {}, {}, {}, {}, {})


def parse_without_metric_lookup(parser: StrategyConfigParser, config: dict) -> dict:
    with mock.patch("bkmonitor.as_code.parse_yaml.MetricListCache.objects.filter") as metric_filter:
        metric_filter.return_value.first.return_value = None
        return parser.parse(parser.check(config))


def test_strategy_schema_preserves_named_output_config_for_version_1_1():
    config = load_rule_config("named_outputs.yaml")

    validated = StrategySchema.validate(config)

    assert validated["query"]["query_output_config"] == config["query"]["query_output_config"]


def test_strategy_schema_rejects_named_output_config_before_version_1_1():
    config = load_rule_config("named_outputs.yaml")
    config["version"] = "1.0"

    with pytest.raises(SchemaError, match="1.1"):
        StrategySchema.validate(config)


@pytest.mark.parametrize("version", ["1.01", "1.05", "1.10"])
def test_strategy_schema_rejects_unknown_version(version):
    config = load_rule_config("cpu_simple.yaml")
    config["version"] = version

    with pytest.raises(SchemaError):
        StrategySchema.validate(config)


def test_strategy_schema_keeps_numeric_legacy_version_compatible():
    config = load_rule_config("cpu_simple.yaml")
    config["version"] = 1.0

    validated = StrategySchema.validate(config)

    assert validated["version"] == "1.0"


def test_strategy_schema_keeps_legacy_rule_without_named_output_config():
    validated = StrategySchema.validate(load_rule_config("cpu_simple.yaml"))

    assert validated["version"] == "1.0"
    assert "query_output_config" not in validated["query"]


def test_strategy_parser_maps_named_output_config_to_item():
    parser = make_parser()
    config = load_rule_config("named_outputs.yaml")

    parsed = parse_without_metric_lookup(parser, config)

    assert parsed["items"][0]["query_output_config"] == config["query"]["query_output_config"]


def test_strategy_parser_preserves_omitted_and_explicit_null_lifecycle():
    parser = make_parser()
    omitted = load_rule_config("cpu_simple.yaml")
    deleting = load_rule_config("named_outputs.yaml")
    deleting["query"]["query_output_config"] = None

    parsed_omitted = parse_without_metric_lookup(parser, omitted)
    parsed_deleting = parse_without_metric_lookup(parser, deleting)

    assert "query_output_config" not in parsed_omitted["items"][0]
    assert parsed_deleting["items"][0]["query_output_config"] is None


def test_strategy_unparse_named_output_config_uses_version_1_1_and_roundtrips():
    parser = make_parser()
    source = load_rule_config("named_outputs.yaml")
    parsed = parse_without_metric_lookup(parser, source)

    unparsed = parser.unparse(Strategy(**parsed).to_dict())

    assert unparsed["version"] == "1.1"
    assert unparsed["query"]["query_output_config"] == source["query"]["query_output_config"]


def test_strategy_unparse_without_named_output_config_keeps_version_1_0():
    parser = make_parser()
    source = load_rule_config("cpu_simple.yaml")
    parsed = parse_without_metric_lookup(parser, source)

    unparsed = parser.unparse(Strategy(**parsed).to_dict())

    assert unparsed["version"] == "1.0"
    assert "query_output_config" not in unparsed["query"]


def test_rule_json_schema_declares_named_output_config_and_version_1_1():
    with (AS_CODE_PATH / "json_schema/rule.json").open() as f:
        schema = json.load(f)

    output_schema = schema["properties"]["query"]["properties"]["query_output_config"]
    assert output_schema["anyOf"][0]["type"] == "null"
    assert output_schema["anyOf"][1]["properties"]["response_contract"]["const"] == "named_outputs/v1"
    assert "1.1" in schema["properties"]["version"]["enum"]


def test_rule_json_schema_requires_version_1_1_for_named_output_config():
    with (AS_CODE_PATH / "json_schema/rule.json").open() as f:
        schema = json.load(f)
    config = load_rule_config("named_outputs.yaml")

    validate_json_schema(config, schema)
    config["version"] = "1.0"
    with pytest.raises(JsonSchemaValidationError):
        validate_json_schema(config, schema)
