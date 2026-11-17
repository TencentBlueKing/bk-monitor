import json
from pathlib import Path
from unittest import mock

import yaml
import pytest
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema
from rest_framework.exceptions import ValidationError
from schema import SchemaError

from bkmonitor.as_code.parse_yaml import StrategyConfigParser
from bkmonitor.as_code.schema import StrategySchema
from bkmonitor.strategy.new_strategy import Strategy


def make_config():
    return yaml.safe_load(
        """
name: request ratio
version: "1.1"
query:
  data_source: prometheus
  data_type: time_series
  expression: a / b * 100
  query_configs:
  - metric: sum(rate(requests_ok_total[5m]))
    alias: a
    expression_mode: promql
    interval: 60
  - metric: sum(rate(requests_total[5m]))
    alias: b
    expression_mode: promql
    interval: 60
detect:
  algorithm:
    fatal:
    - type: Threshold
      config: ">90"
  trigger: 1/5/5
notice:
  user_groups:
  - ops.yaml
"""
    )


def make_parser():
    return StrategyConfigParser(2, {"ops.yaml": 1}, {}, {}, {}, {}, {})


def parse_without_metric_lookup(parser, config, fallback_scenario=None):
    with mock.patch("bkmonitor.as_code.parse_yaml.MetricListCache.objects.filter") as metric_filter:
        metric_filter.return_value.first.return_value = None
        return parser.parse(parser.check(config), fallback_scenario=fallback_scenario)


def test_promql_multi_expression_as_code_roundtrip():
    parser = make_parser()
    source = make_config()
    schema_path = Path(__file__).parents[1] / "json_schema/rule.json"
    with schema_path.open() as schema_file:
        validate_json_schema(source, json.load(schema_file))

    parsed = parse_without_metric_lookup(parser, source)
    exported = parser.unparse(Strategy(**parsed).to_dict())
    reparsed = parse_without_metric_lookup(parser, exported)

    assert exported["version"] == "1.1"
    for result in (parsed, reparsed):
        item = result["items"][0]
        assert item["expression"] == "a / b * 100"
        assert [(query["alias"], query["promql"], query["expression_mode"]) for query in item["query_configs"]] == [
            ("a", "sum(rate(requests_ok_total[5m]))", "promql"),
            ("b", "sum(rate(requests_total[5m]))", "promql"),
        ]


def test_single_promql_as_code_keeps_legacy_shape():
    parser = make_parser()
    source = make_config()
    source["query"].pop("expression")
    source["query"]["query_configs"] = [{"metric": "up", "interval": 60}]

    parsed = parse_without_metric_lookup(parser, source)
    exported = parser.unparse(Strategy(**parsed).to_dict())

    assert "expression_mode" not in parsed["items"][0]["query_configs"][0]
    assert "expression_mode" not in exported["query"]["query_configs"][0]
    assert "alias" not in exported["query"]["query_configs"][0]
    assert "expression" not in exported["query"]
    assert exported["version"] == "1.0"


def test_explicit_scenario_overrides_metric_and_roundtrip():
    """显式 scenario 优先，并且导出时保留。"""
    parser = make_parser()
    source = make_config()
    source["scenario"] = "os"

    parsed = parse_without_metric_lookup(parser, source)
    assert parsed["scenario"] == "os"

    exported = parser.unparse(Strategy(**parsed).to_dict())
    assert exported["scenario"] == "os"

    reparsed = parse_without_metric_lookup(parser, exported)
    assert reparsed["scenario"] == "os"


def test_whitespace_scenario_rejected():
    """纯空白 scenario 不能静默回退，应直接报错。"""
    parser = make_parser()
    source = make_config()
    source["scenario"] = "   "

    with pytest.raises(ValidationError, match="scenario 不能为空"):
        parse_without_metric_lookup(parser, source)


def test_explicit_scenario_takes_precedence_over_fallback():
    """显式 scenario 优先级高于旧策略值。"""
    parser = make_parser()
    source = make_config()
    source["scenario"] = "component"

    parsed = parse_without_metric_lookup(parser, source, fallback_scenario="os")

    assert parsed["scenario"] == "component"


def test_promql_update_uses_fallback_scenario():
    """纯 PromQL 推导不到场景时，更新已有策略使用旧值。"""
    parser = make_parser()

    parsed = parse_without_metric_lookup(parser, make_config(), fallback_scenario="os")

    assert parsed["scenario"] == "os"


def test_promql_new_rule_keeps_other_rt():
    """新建旧格式规则仍保持 other_rt，兼容现有行为。"""
    parser = make_parser()

    parsed = parse_without_metric_lookup(parser, make_config())

    assert parsed["scenario"] == "other_rt"


def test_other_rt_explicit_scenario_roundtrip():
    """原有 other_rt 场景规则导出再导入不丢场景。"""
    parser = make_parser()
    source = make_config()
    source["scenario"] = "other_rt"

    parsed = parse_without_metric_lookup(parser, source)
    exported = parser.unparse(Strategy(**parsed).to_dict())
    reparsed = parse_without_metric_lookup(parser, exported)

    assert exported["scenario"] == "other_rt"
    assert reparsed["scenario"] == "other_rt"


def test_rule_json_schema_declares_scenario():
    schema_path = Path(__file__).parents[1] / "json_schema/rule.json"
    with schema_path.open() as schema_file:
        schema = json.load(schema_file)

    assert schema["properties"]["scenario"]["maxLength"] == 32
    source = make_config()
    source["scenario"] = "os"
    validate_json_schema(source, schema)


def test_promql_expression_mode_requires_as_code_version_1_1():
    source = make_config()
    source["version"] = "1.0"
    schema_path = Path(__file__).parents[1] / "json_schema/rule.json"

    with pytest.raises(SchemaError, match="version 1.1"):
        StrategySchema.validate(source)
    with schema_path.open() as schema_file, pytest.raises(JsonSchemaValidationError):
        validate_json_schema(source, json.load(schema_file))
