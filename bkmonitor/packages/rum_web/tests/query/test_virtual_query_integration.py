"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy
import json
import re
from typing import Any
from unittest.mock import patch

from django.db.models import Q
from django.utils.tree import Node
from luqum.parser import parser
from luqum.tree import AndOperation, FieldGroup, Group, Not, OrOperation, Phrase, SearchField, Word
import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.data_source import q_to_dict
from bkmonitor.data_source.data_source import conditions_to_q, filter_dict_to_conditions
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery
from rum_web.handlers.level.factory import RumLevelHandlerFactory
from rum_web.handlers.level.span import SpanLevelHandler
from rum_web.handlers.query.base import equal_filter
from rum_web.handlers.query.span import SpanQuery


WIDTH = "attributes.browser.viewport.width"
HEIGHT = "attributes.browser.viewport.height"
NAME = "resource.user_agent.name"
VERSION = "resource.user_agent.version"


def target() -> TraceDatasourceTarget:
    return TraceDatasourceTarget.build(bk_biz_id=2, app_name="test", table_id="bk_rum.test.span")


def matches(condition: Node, row: dict[str, Any]) -> bool:
    """按存储叶子条件求值，保留 NULL 与普通不等比较的区别。"""
    results: list[bool] = []
    for child in condition.children:
        if isinstance(child, Node):
            results.append(matches(child, row))
            continue
        lookup, expected = child
        name, operation = lookup.rsplit("__", 1) if "__" in lookup else (lookup, "eq")
        value: Any = row.get(name)
        exists: bool = value is not None
        if name in {WIDTH, HEIGHT} and value == "":
            exists = False
        candidates: list[Any] = expected if isinstance(expected, list) else [expected]
        if operation == "exists":
            results.append(exists)
        elif operation == "nexists":
            results.append(not exists)
        elif operation == "eq":
            results.append(exists and value in candidates)
        else:
            assert operation == "neq"
            results.append(exists and value not in candidates)
    result: bool = any(results) if condition.connector == Q.OR else all(results)
    return not result if condition.negated else result


def query_string_matches(node: Any, row: dict[str, Any], field: str | None = None) -> bool:
    """通过 Lucene 解析树检查分组及转义，避免只比较字符串片段。"""
    if isinstance(node, AndOperation):
        return all(query_string_matches(child, row, field) for child in node.children)
    if isinstance(node, OrOperation):
        return any(query_string_matches(child, row, field) for child in node.children)
    if isinstance(node, Not):
        return not query_string_matches(node.a, row, field)
    if isinstance(node, Group | FieldGroup):
        return query_string_matches(node.expr, row, field)
    if isinstance(node, SearchField):
        return query_string_matches(node.expr, row, node.name)
    assert isinstance(node, Phrase | Word), repr(node)
    value: str = node.value[1:-1] if isinstance(node, Phrase) else node.value
    value = re.sub(r"\\(.)", r"\1", value)
    if field == "_exists_":
        return row.get(value) is not None
    if isinstance(node, Word) and value == "*":
        return row.get(field) is not None
    return row.get(field) is not None and str(row[field]) == value


@pytest.fixture
def query() -> SpanQuery:
    return SpanQuery([target()])


def test_virtual_filter_keeps_ordinary_conditions_and_input(query):
    filters = [equal_filter("virtual.browser", ["Chrome --"]), equal_filter("attributes.user.id", ["alice"])]
    original = deepcopy(filters)
    condition = query._build_filters(filters)
    assert filters == original
    assert matches(condition, {NAME: "Chrome", "attributes.user.id": "alice"})
    assert not matches(condition, {NAME: "Chrome", "attributes.user.id": "bob"})
    assert not matches(condition, {NAME: "Firefox", "attributes.user.id": "alice"})


@pytest.mark.parametrize("operator", ["exists", "not exists", "not_exists", "contains"])
def test_virtual_filter_rejects_unsupported_operations(query, operator):
    with pytest.raises(ValidationError):
        query._build_filters([{"key": "virtual.browser", "operator": operator, "value": []}])


@pytest.mark.parametrize(
    "field,values,rows",
    [
        (
            "virtual.browser",
            ["Chrome --"],
            [{NAME: "Chrome"}, {NAME: "Chrome", VERSION: ""}, {NAME: "Chrome", VERSION: "131"}, {}],
        ),
        ("virtual.viewport", ["1440 x --"], [{WIDTH: 1440}, {WIDTH: 1440, HEIGHT: 900}, {}]),
        (
            "virtual.viewport",
            ["1440 x 900", "1920 x 1080"],
            [{WIDTH: w, HEIGHT: h} for w in (1440, 1920) for h in (900, 1080)] + [{}],
        ),
    ],
)
@pytest.mark.parametrize("operator", ["equal", "not_equal"])
def test_storage_filter_serialization_preserves_virtual_semantics(query, field, values, rows, operator):
    filters = [{"key": field, "operator": operator, "value": values}]
    config = query.get_queries(filters)[0].query
    serialized = q_to_dict(config.where)
    assert "virtual." not in json.dumps(serialized)
    conditions = filter_dict_to_conditions(serialized, [])
    assert all(not item["key"].startswith("__q_to_dict") for item in conditions)
    restored = conditions_to_q(conditions)
    virtual = query.virtual_fields[field]
    for row in rows:
        row = {"app_name": "test", "bk_biz_id": 2, **row}
        actual: str | None = virtual.format(row)
        expected: bool = actual in values if operator == "equal" else actual not in values
        wire_row = {key: str(item) if item is not None else None for key, item in row.items()}
        assert matches(restored, wire_row) == expected, (operator, values, row, serialized)


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("span", {"viewport", "browser", "network"}),
        ("session", {"viewport", "browser", "network"}),
        ("view", {"browser", "network", "viewport"}),
    ],
)
def test_view_config_exposes_supported_virtual_fields(mode, expected):
    handler = RumLevelHandlerFactory.create(mode, [target()])
    with patch.object(BaseQuery, "_query_fields", return_value={}):
        config = handler.view_config(None, None)
    fields = {field["field_name"]: field for field in config["fields"]}
    expected_names = {f"virtual.{name}" for name in expected}
    assert {name for name in fields if name.startswith("virtual.")} == expected_names
    assert set(handler.query.virtual_fields) == expected_names
    assert "virtual" not in fields
    if "viewport" in expected:
        assert fields[WIDTH]["field_type"] == fields[HEIGHT]["field_type"] == "long"
    for name in expected:
        field = fields[f"virtual.{name}"]
        assert field["is_searchable"] and field["is_list"] and field["is_agg"]
        assert not field["is_real"] and field["field_type"] == "keyword"
        operations = field["supported_operations"]
        assert {operation["operator"] for operation in operations} == {"equal", "not_equal"}
        assert all(operation["label"] for operation in operations)
    assert all(
        "virtual_config" not in field
        and "composite_config" not in field
        and field.get("extra_config", {}).keys() <= {"composite"}
        for field in fields.values()
    )


def test_virtual_metadata_does_not_enable_ordinary_storage_fields(query):
    metadata = {
        "span_name": {
            "field_name": "span_name",
            "field_type": "keyword",
            "is_searchable": False,
            "is_list": False,
            "is_agg": False,
            "supported_operations": [],
        }
    }
    with patch.object(BaseQuery, "_query_fields", return_value=metadata):
        fields = query.query_fields(None, None)
    assert not fields["span_name"]["is_searchable"]
    assert not fields["span_name"]["is_list"]
    assert not fields["span_name"]["is_agg"]
    assert fields["span_name"]["supported_operations"] == []
    assert fields["virtual.viewport"]["is_searchable"]


def test_raw_query_returns_unmaterialized_records(query):
    with patch.object(BaseQuery, "_query_list", return_value=[{NAME: "Chrome", VERSION: "131"}]):
        assert query.query_list(10, 20, 3, 5) == [{NAME: "Chrome", VERSION: "131"}]


@pytest.mark.parametrize("operator", ["equal", "not_equal"])
def test_query_string_preserves_empty_placeholder_and_negation(query, operator):
    handler = SpanLevelHandler([target()])
    filters = [{"key": "virtual.browser", "operator": operator, "value": ["Chrome --"]}]
    text = handler.generate_query_string(filters)
    assert "virtual.browser" not in text
    tree = parser.parse(text)
    rows = [
        {NAME: "Chrome"},
        {NAME: "Chrome", VERSION: ""},
        {NAME: "Chrome", VERSION: "131"},
        {},
        {NAME: "", VERSION: ""},
    ]
    condition = query._build_filters(filters)
    for row in rows:
        assert query_string_matches(tree, row) == matches(condition, row), (text, row)


def test_query_string_preserves_multivalue_pairs_and_ordinary_filter(query):
    handler = SpanLevelHandler([target()])
    filters = [
        equal_filter("virtual.viewport", ["1440 x 900", "1920 x 1080"]),
        equal_filter("attributes.user.id", ["alice"]),
    ]
    text = handler.generate_query_string(filters)
    tree = parser.parse(text)
    condition = query._build_filters(filters)
    for row in [{WIDTH: 1440, HEIGHT: 900}, {WIDTH: 1920, HEIGHT: 1080}, {WIDTH: 1440, HEIGHT: 1080}, {}]:
        for user in ("alice", "bob"):
            row = {**row, "attributes.user.id": user}
            assert query_string_matches(tree, row) == matches(condition, row), (text, row)


def test_query_string_escapes_quotes_and_backslashes_in_original_values(query):
    handler = SpanLevelHandler([target()])
    row = {NAME: 'A"B\\ C', VERSION: "131"}
    value = query.virtual_fields["virtual.browser"].format(row)
    text = handler.generate_query_string([equal_filter("virtual.browser", [value])])
    assert "virtual.browser" not in text
    tree = parser.parse(text)
    assert query_string_matches(tree, row)
    assert not query_string_matches(tree, {NAME: 'A"B C', VERSION: "131"})


@pytest.mark.parametrize("name,expected", [("Chrome", True), ("Firefox", False)])
def test_virtual_and_member_filters_remain_conjunctive_through_wire_protocol(query, name, expected):
    filters = [equal_filter("virtual.browser", ["Chrome 157"]), equal_filter(NAME, [name])]
    serialized = q_to_dict(query.get_queries(filters)[0].query.where)
    conditions = filter_dict_to_conditions(serialized, [])
    assert all(not item["key"].startswith("__q_to_dict") for item in conditions)
    assert (
        matches(conditions_to_q(conditions), {NAME: "Chrome", VERSION: "157", "app_name": "test", "bk_biz_id": "2"})
        == expected
    )


@pytest.mark.parametrize("operator", ["equal", "not_equal"])
@pytest.mark.parametrize("relation", ["OR", "AND"])
def test_multivalue_browser_filter_uses_wire_conditions(query, operator, relation):
    filters = [
        {
            "key": "virtual.browser",
            "operator": operator,
            "value": ["Chrome 157", "Chrome 156"],
            "options": {"group_relation": relation},
        }
    ]
    conditions = filter_dict_to_conditions(q_to_dict(query._build_filters(filters)), [])
    assert all(not item["key"].startswith("__q_to_dict") for item in conditions)
    restored = conditions_to_q(conditions)
    for row in ({NAME: "Chrome", VERSION: "157"}, {NAME: "Chrome", VERSION: "156"}, {NAME: "Chrome"}, {}):
        expected = relation == "OR" and query.virtual_fields["virtual.browser"].format(row) in [
            "Chrome 157",
            "Chrome 156",
        ]
        assert matches(restored, row) == (expected if operator == "equal" else not expected)


def test_nonempty_virtual_value_needs_only_member_equalities(query):
    conditions = filter_dict_to_conditions(
        q_to_dict(query._build_filters([equal_filter("virtual.browser", ["Chrome 157"])])), []
    )
    assert {(item["key"], item["method"], tuple(item["value"])) for item in conditions} == {
        (NAME, "eq", ("Chrome",)),
        (VERSION, "eq", ("157",)),
    }


@pytest.mark.parametrize("operator", ["equal", "not_equal"])
@pytest.mark.parametrize("values", [["-- / 4g"], ["-- / 4g", "wifi / --"], ["-- / 4g", "wifi / 3g", "cellular / 2g"]])
def test_network_filters_preserve_pairs_and_empty_connection_on_wire(query, operator, values):
    field = "virtual.network"
    connection, quality = query.virtual_fields[field].field_names
    filters = [{"key": field, "operator": operator, "value": values}]
    builder = query.get_queries(filters)[0]
    conditions = filter_dict_to_conditions(q_to_dict(builder.query.where), [])
    assert "--" not in json.dumps(conditions)
    assert all(item["key"] in {connection, quality, "bk_biz_id", "app_name"} for item in conditions)
    restored = conditions_to_q(conditions)
    for row, display in [
        ({quality: "4g"}, "-- / 4g"),
        ({connection: "", quality: "4g"}, "-- / 4g"),
        ({connection: "wifi", quality: "3g"}, "wifi / 3g"),
        ({connection: "cellular", quality: "2g"}, "cellular / 2g"),
        ({connection: "wifi", quality: "4g"}, "wifi / 4g"),
        ({connection: "", quality: "3g"}, "-- / 3g"),
        ({connection: "wifi"}, "wifi / --"),
        ({connection: "wifi", quality: ""}, "wifi / --"),
        ({connection: "cellular"}, "cellular / --"),
        ({}, None),
    ]:
        wire_row = {"bk_biz_id": "2", "app_name": "test", **row}
        expected = display in values if operator == "equal" else display not in values
        assert matches(restored, wire_row) == expected, (display, operator, values)
