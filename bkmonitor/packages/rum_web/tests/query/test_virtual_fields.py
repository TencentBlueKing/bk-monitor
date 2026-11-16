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

from rum_web.virtual_fields import VirtualField, get_virtual_fields
from semconv.rum.field import FieldSpec
from semconv.rum.session import SessionSpec
from semconv.rum.trace import SpanSpec
from semconv.rum.view import ViewSpec


def make_field(template: str, pattern: str, **types: str) -> VirtualField:
    return VirtualField(
        {"fields": {name: name for name in types}, "template": template, "parse_pattern": pattern},
        {name: FieldSpec(name, field_type=kind) for name, kind in types.items()},
    )


def matches(condition: Q, row: dict[str, Any], field: VirtualField) -> bool:
    """按查询条件语义检查结果集，独立于模板的拼接实现。"""
    results: list[bool] = []
    for child in condition.children:
        if isinstance(child, Q):
            results.append(matches(child, row, field))
            continue
        lookup, expected = child
        name, operation = lookup.rsplit("__", 1)
        actual: Any = row.get(name)
        candidates: list[Any] = expected if isinstance(expected, list) else [expected]
        exists: bool = actual is not None
        if field.types[name] is int:
            exists = exists and actual != ""
        if operation == "exists":
            results.append(exists)
        elif operation == "nexists":
            results.append(not exists)
        elif operation == "eq":
            results.append(exists and actual in candidates)
        else:
            assert operation == "neq"
            results.append(exists and actual not in candidates)
    result: bool = any(results) if condition.connector == Q.OR else all(results)
    return not result if condition.negated else result


@pytest.fixture
def span_fields() -> dict[str, VirtualField]:
    return get_virtual_fields(SpanSpec.fields())


@pytest.mark.parametrize(
    "name,row,expected",
    [
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


def test_default_placeholder_matches_empty_only():
    field = make_field("{name|--} {version|--}", r"(?P<name>.+) (?P<version>[^ ]+)", name="keyword", version="keyword")
    condition = field.build_filter("Chrome --")
    for version in (None, ""):
        row = {"name": "Chrome", "version": version}
        assert field.format(row) == "Chrome --"
        assert matches(condition, row, field)
    assert not matches(condition, {"name": "Chrome", "version": "131"}, field)
    assert not matches(condition, {}, field)


def test_all_empty_overrides_defaults():
    field = make_field("{a|--}/{b|--}", r"(?P<a>.*)/(?P<b>.*)", a="keyword", b="keyword")
    for row in ({}, {"a": None, "b": ""}):
        assert field.format(row) is None
        assert not matches(field.build_filter("--/--"), row, field)


def test_viewport_filter_preserves_zero_and_canonical_numbers(span_fields):
    field = span_fields["virtual.viewport"]
    row = dict(zip(field.field_names, (0, 900)))
    assert field.format(row) == "0 x 900"
    assert matches(field.build_filter("0 x 900"), row, field)
    for invalid in ("", "0 x", "00 x 900", "wide x 900"):
        assert not matches(field.build_filter(invalid), row, field)


@pytest.mark.parametrize("name,version", [("Mobile Safari", "131"), (r"A\B", "131"), ("a/b", None)])
def test_browser_splits_once_from_right_without_escaping(name, version):
    field = make_field("{name|--} {version|--}", r"(?P<name>.+) (?P<version>[^ ]+)", name="keyword", version="keyword")
    row = {"name": name, "version": version}
    value = field.format(row)
    assert value == f"{name} {version or '--'}"
    assert matches(field.build_filter(value), row, field)
    if name == "Mobile Safari":
        assert not matches(field.build_filter(value), {"name": "Mobile", "version": "Safari 131"}, field)


def test_member_order_comes_from_template():
    field = make_field("{a|--}/{b|--}", r"(?P<a>.*)/(?P<b>.*)", b="keyword", a="keyword")
    assert field.field_names == ["a", "b"]


def test_filters_equal_the_template_value_for_all_fixture_records():
    field = make_field("{a|--} / {b|--}", r"(?P<a>.*) / (?P<b>.*)", a="keyword", b="keyword")
    rows = [dict(zip(("a", "b"), values)) for values in product((None, "", "x", "a/b", "a b"), repeat=2)]
    values = {field.format(row) for row in rows} - {None}
    for value in values:
        condition = field.build_filter(value)
        excluded = field.build_filter(value, exclude=True)
        for row in rows:
            expected = field.format(row) == value
            assert matches(condition, row, field) == expected, (value, row)
            assert matches(excluded, row, field) == (not expected), (value, row)


@pytest.mark.parametrize(
    "template,pattern,row,display,other",
    [
        ("type({x|--})", r"type\((?P<x>.*)\)", {"x": "http(v2)"}, "type(http(v2))", {"x": "http"}),
        ("a{x|--}b{y|--}", r"a(?P<x>.*?)b(?P<y>.*)", {"x": "1", "y": "2b3"}, "a1b2b3", {"x": "1b2", "y": "3"}),
        ("a{x|--}b{y|--}", r"a(?P<x>.*)b(?P<y>.*)", {"x": "1b2", "y": "3"}, "a1b2b3", {"x": "1", "y": "2b3"}),
    ],
)
def test_configured_pattern_decides_member_boundaries(template, pattern, row, display, other):
    field = make_field(template, pattern, **dict.fromkeys(row, "keyword"))
    assert field.format(row) == display
    for exclude in (False, True):
        condition = field.build_filter(display, exclude=exclude)
        assert matches(condition, row, field) == (not exclude)
        assert matches(condition, other, field) == exclude


@pytest.mark.parametrize(
    "template,pattern",
    [("{a|--}/{other|--}", r"(?P<a>.*)/(?P<b>.*)"), ("{a|--}/{b|--}", r"(?P<a>.*)/(?P<other>.*)")],
)
def test_template_and_pattern_must_bind_the_same_members(template, pattern):
    with pytest.raises(ValueError):
        make_field(template, pattern, a="keyword", b="keyword")


def test_registry_exposes_only_supported_virtual_dimensions(span_fields):
    assert set(span_fields) == {"virtual.viewport", "virtual.browser", "virtual.network"}
    assert set(get_virtual_fields(SessionSpec.fields())) == {"virtual.browser", "virtual.network"}
    assert set(get_virtual_fields(ViewSpec.fields())) == {"virtual.browser", "virtual.network", "virtual.viewport"}
    assert "virtual" not in {field.get_full_field_name() for field in SpanSpec.fields()}
    assert SpanSpec.from_field("attributes.browser.viewport.width").field_type == "long"
    assert SpanSpec.from_field("attributes.browser.viewport.height").field_type == "long"
