"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from itertools import product
from typing import Any

from django.db.models import Q
import pytest

from rum_web.virtual_fields import VirtualField, get_virtual_fields, normalize_filter
from semconv.rum.field import FieldSpec
from semconv.rum.session import SessionSpec
from semconv.rum.trace import SpanSpec
from semconv.rum.view import ViewSpec


def make_field(template: str, **types: str) -> VirtualField:
    return VirtualField(
        {"fields": {name: name for name in types}, "template": template},
        {name: FieldSpec(name, field_type=kind) for name, kind in types.items()},
    )


def matches(condition: Q, row: dict[str, Any], field: VirtualField) -> bool:
    """按查询条件语义检查结果集，独立于模板的拼接实现。"""
    results: list[bool] = []
    by_path: dict[str, FieldSpec] = {path: field.field_specs[name] for name, path in field.fields.items()}
    for child in condition.children:
        if isinstance(child, Q):
            results.append(matches(child, row, field))
            continue
        lookup, expected = child
        name, operation = lookup.rsplit("__", 1)
        actual: Any = row.get(name)
        exists: bool = actual is not None
        if by_path[name].field_type in field.INTEGER_TYPES | field.FLOAT_TYPES | {"boolean"}:
            exists = exists and actual != ""
        if operation == "exists":
            results.append(exists)
        elif operation == "nexists":
            results.append(not exists)
        elif operation == "eq":
            results.append(exists and actual == expected)
        else:
            assert operation == "neq"
            results.append(exists and actual != expected)
    result: bool = any(results) if condition.connector == Q.OR else all(results)
    return not result if condition.negated else result


@pytest.fixture
def span_fields() -> dict[str, VirtualField]:
    return get_virtual_fields(SpanSpec)


@pytest.mark.parametrize(
    "name,row,expected",
    [
        (
            "virtual.span_kind",
            {"attributes.span_type": "resource", "attributes.resource.type": "xhr"},
            "resource（xhr）",
        ),
        ("virtual.span_kind", {"attributes.span_type": "action"}, "action"),
        (
            "virtual.viewport",
            {"attributes.browser.viewport.width": 1440, "attributes.browser.viewport.height": 900},
            "1440 x 900",
        ),
        ("virtual.viewport", {"attributes.browser.viewport.width": 1440}, "1440 x --"),
        (
            "virtual.browser",
            {"resource.user_agent.name": "Chrome", "resource.user_agent.version": "131"},
            "Chrome 131",
        ),
        (
            "virtual.network",
            {"attributes.network.connection.type": "wifi", "attributes.network.effective_type": "4g"},
            "wifi / 4g",
        ),
    ],
)
def test_registered_fields_format_and_filter(span_fields, name, row, expected):
    field = span_fields[name]
    assert field.format(row) == expected
    assert matches(field.build_filter(expected), row, field)


def test_default_collision_matches_empty_and_literal():
    field = make_field("{name|--} {version|--}", name="keyword", version="keyword")
    condition = field.build_filter("Chrome --")
    for version in (None, "", "--"):
        row = {"name": "Chrome", "version": version}
        assert field.format(row) == "Chrome --"
        assert matches(condition, row, field)
    assert not matches(condition, {"name": "Chrome", "version": "131"}, field)
    assert not matches(condition, {}, field)


def test_hidden_optional_block_requires_its_missing_condition():
    field = make_field("{kind}[（{resource}）]", kind="keyword", resource="keyword")
    condition = field.build_filter("action")
    assert matches(condition, {"kind": "action"}, field)
    assert matches(condition, {"kind": "action", "resource": ""}, field)
    assert not matches(condition, {"kind": "action", "resource": "xhr"}, field)


def test_partly_missing_optional_block_hides_all_of_it():
    field = make_field("{head}[ / {a}-{b}]", head="keyword", a="keyword", b="keyword")
    condition = field.build_filter("x")
    for row in ({"head": "x", "a": "A"}, {"head": "x", "b": "B"}):
        assert field.format(row) == "x"
        assert matches(condition, row, field)
    assert not matches(condition, {"head": "x", "a": "A", "b": "B"}, field)


def test_all_empty_overrides_defaults():
    field = make_field("{a|--}/{b|--}", a="keyword", b="keyword")
    for row in ({}, {"a": None, "b": ""}):
        assert field.format(row) is None
        assert not matches(field.exists_filter(), row, field)
        assert not matches(field.build_filter("--/--"), row, field)
    assert matches(field.build_filter("--/--"), {"a": "--"}, field)


def test_numeric_types_and_default_canonical_value():
    field = make_field("{kind}:{size|01}", kind="keyword", size="long")
    condition = field.build_filter("x:01")
    assert field.format({"kind": "x", "size": 1}) == "x:1"
    assert matches(condition, {"kind": "x"}, field)
    assert not matches(condition, {"kind": "x", "size": 1}, field)
    assert not matches(field.build_filter("x:--"), {"kind": "x"}, field)
    assert matches(field.build_filter("x:0"), {"kind": "x", "size": 0}, field)


def test_zero_false_and_space_are_not_empty():
    field = make_field("{size|--}/{enabled|--}/{name|--}", size="long", enabled="boolean", name="keyword")
    row = {"size": 0, "enabled": False, "name": " "}
    assert field.format(row) == "0/false/ "
    assert matches(field.build_filter("0/false/ "), row, field)
    assert matches(field.exists_filter(), row, field)


@pytest.mark.parametrize("name,version", [("Mobile Safari", "131"), (r"A\B", "131"), ("a/b", "--")])
def test_browser_splits_once_from_right_without_escaping(name, version):
    field = make_field("{name} {version}", name="keyword", version="keyword")
    row = {"name": name, "version": version}
    value = field.format(row)
    assert value == f"{name} {version}"
    assert matches(field.build_filter(value), row, field)
    if name == "Mobile Safari":
        assert not matches(field.build_filter(value), {"name": "Mobile", "version": "Safari 131"}, field)


def test_default_text_is_returned_without_encoding():
    field = make_field("{head}/{value|unknown}", head="keyword", value="keyword")
    value = field.format({"head": "x"})
    assert value == "x/unknown"
    condition = field.build_filter(value)
    assert matches(condition, {"head": "x"}, field)
    assert matches(condition, {"head": "x", "value": "unknown"}, field)


def test_literal_brackets_and_repeated_fields():
    field = make_field("{{{a}}} [[{a}]]", a="keyword")
    assert field.format({"a": "x"}) == "{x} [x]"
    assert matches(field.build_filter("{x} [x]"), {"a": "x"}, field)
    assert not matches(field.build_filter("{x} [y]"), {"a": "x"}, field)
    assert field.field_names == ["a"]


def test_member_order_comes_from_template():
    field = make_field("{a}/{b}/{a}", b="keyword", a="keyword")
    assert field.field_names == ["a", "b"]


def test_filters_equal_the_template_value_for_all_fixture_records():
    field = make_field("{kind|--}[ / {a} : {b|--}]", kind="keyword", a="keyword", b="keyword")
    rows = [dict(zip(("kind", "a", "b"), values)) for values in product((None, "", "x", "--", "a/b", "a b"), repeat=3)]
    values = {field.format(row) for row in rows} - {None}
    for value in values:
        condition = field.build_filter(value)
        normalized = normalize_filter(condition)
        excluded = normalize_filter(~condition)
        for row in rows:
            expected = field.format(row) == value
            assert matches(condition, row, field) == expected, (value, row)
            assert matches(normalized, row, field) == expected, (value, row)
            assert matches(excluded, row, field) == (not expected), (value, row)


@pytest.mark.parametrize("template", ["{a}{b}", "{a}[{b}]", "{a", "[{a}[{b}]]", "{a}[ / {b}"])
def test_invalid_template_fails_when_compiled(template):
    with pytest.raises(ValueError):
        make_field(template, a="keyword", b="keyword")


def test_registry_exposes_only_supported_virtual_dimensions(span_fields):
    assert set(span_fields) == {"virtual.span_kind", "virtual.viewport", "virtual.browser", "virtual.network"}
    assert set(get_virtual_fields(SessionSpec)) == {"virtual.browser", "virtual.network"}
    assert set(get_virtual_fields(ViewSpec)) == {"virtual.browser", "virtual.network", "virtual.viewport"}
    assert "virtual" not in {field.get_full_field_name() for field in SpanSpec.fields()}
    assert SpanSpec.from_field("attributes.browser.viewport.width").field_type == "long"
    assert SpanSpec.from_field("attributes.browser.viewport.height").field_type == "long"
