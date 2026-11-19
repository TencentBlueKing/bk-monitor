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
from typing import Any
from unittest.mock import patch

import pytest

from bkmonitor.data_source.format import flatten_dict_data
from bkmonitor.data_source.utils.apm import LevelTarget, TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery
from rum_web.handlers.level.factory import RumLevelHandlerFactory
from rum_web.query.resources import RumViewConfigResource


def handler_for(mode: str, precomputed: bool = False):
    target = TraceDatasourceTarget.build(
        bk_biz_id=2,
        app_name="test",
        table_id="bk_rum.test.span",
        retention=3,
        levels=[LevelTarget(mode, [f"bk_rum.test.{mode}"])] if precomputed else [],
    )
    return RumLevelHandlerFactory.create(mode, [target])


def view_config(mode: str, precomputed: bool = False) -> dict[str, Any]:
    handler = handler_for(mode, precomputed)
    with (
        patch.object(BaseQuery, "_query_fields", return_value={}),
        patch("rum_web.query.resources._get_application"),
        patch("rum_web.query.resources._build_data_sources", return_value=handler.query.data_sources),
    ):
        return RumViewConfigResource().request({"bk_biz_id": 2, "app_name": "test", "mode": mode})


@pytest.mark.parametrize(
    "mode, precomputed", [("span", False), ("view", False), ("view", True), ("session", False), ("session", True)]
)
def test_column_layouts_reference_available_fields_and_preserve_query_capabilities(mode, precomputed):
    config = view_config(mode, precomputed)
    fields: dict[str, dict[str, Any]] = {field["field_name"]: field for field in config["fields"]}
    composites = {name: field for name, field in fields.items() if field.get("extra_config", {}).get("composite")}
    expected = {"virtual.browser"}
    if mode in ("span", "view"):
        expected.add("attributes.view.url_template")
    if mode == "session":
        expected.add("attributes.session.id")
    if mode == "span":
        expected.update({"span_name", "attributes.error.source", "attributes.resource.size"})
    assert "display.action.target" not in fields
    assert set(composites) == expected
    for name, field in composites.items():
        assert field["is_list"]
        assert field["is_real"] == (name != "virtual.browser")
        assert field["is_searchable"] and field["is_agg"] and field["supported_operations"]
        assert field["extra_config"]["composite"]["primary"] == name
        layout = field["extra_config"]["composite"]
        members = {
            item["field_name"]
            for section in layout["sections"]
            for item in [*section.get("items", []), *section.get("badges", [])]
        }
        assert layout.keys() == {"primary", "sections"}
        assert all(section.keys() <= {"items", "badges", "separator"} for section in layout["sections"])
        assert all(
            item.keys() <= {"field_name", "show_if"}
            for section in layout["sections"]
            for item in [*section.get("items", []), *section.get("badges", [])]
        )
        assert layout["primary"] in members
        assert members <= fields.keys(), name
        if name == "span_name":
            assert "attributes.action.target.tag" in members
            assert "attributes.action.target.name" not in members
        assert fields[layout["primary"]]["is_searchable"]
    assert set(config["display_fields"]) <= fields.keys()
    assert "virtual.browser" in config["display_fields"]
    assert "resource.user_agent.name" in fields
    assert "resource.user_agent.name" not in config["display_fields"]
    assert all(not name.startswith("display.") for group in config["groups"] for name in group["field_names"])
    for defaults in config.get("span_type_display_fields", {}).values():
        assert set(defaults) <= fields.keys()
        assert len(defaults) == len(set(defaults))
        assert defaults[-1] == "end_time"
    if mode == "span":
        assert config["display_fields"] == [
            "span_name",
            "attributes.span_type",
            "elapsed_time",
            "virtual.browser",
            "attributes.user.id",
            "end_time",
        ]
        assert config["span_type_display_fields"]["error"][1] == "attributes.error.source"
        assert "events.attributes.long_task.script.source_url" in config["span_type_display_fields"]["long_task"]
        assert config["span_type_display_fields"]["resource"] == [
            "span_name",
            "elapsed_time",
            "attributes.resource.size",
            "attributes.view.url_template",
            "virtual.browser",
            "attributes.user.id",
            "end_time",
        ]
    if mode == "view":
        assert config["display_fields"] == [
            "attributes.view.url_template",
            "duration",
            "web_vitals.lcp",
            "web_vitals.inp",
            "web_vitals.cls",
            "web_vitals.fcp",
            "web_vitals.ttfb",
            "virtual.browser",
            "attributes.user.id",
            "start_time",
        ]
    if mode == "session":
        assert config["display_fields"] == [
            "attributes.session.id",
            "duration",
            "virtual.browser",
            "attributes.user.id",
            "start_time",
            "view_count",
            "action_count",
            "error_count",
        ]
        assert composites["attributes.session.id"]["extra_config"]["composite"]["sections"] == [
            {"items": [{"field_name": "attributes.session.id"}]},
            {"items": [{"field_name": "enter_url_template"}], "badges": [{"field_name": "virtual.viewport"}]},
        ]
        assert fields["enter_url_template"]["is_searchable"] == precomputed
        assert bool(fields["enter_url_template"]["supported_operations"]) == precomputed


def test_page_column_has_identical_members_in_span_and_view():
    fields = {mode: {field["field_name"]: field for field in view_config(mode)["fields"]} for mode in ("span", "view")}
    page = fields["span"]["attributes.view.url_template"]["extra_config"]["composite"]
    assert page == fields["view"]["attributes.view.url_template"]["extra_config"]["composite"]
    assert page["primary"] == "attributes.view.url_template"
    assert page["sections"][1]["items"][0]["field_name"] == "attributes.view.url"
    assert page["sections"][0]["badges"] == [
        {"field_name": "virtual.viewport"},
        {"field_name": "attributes.view.loading_type"},
    ]


@pytest.mark.parametrize("mode", ["view", "session"])
def test_fallback_keeps_viewport_from_snapshot_for_composite_columns(mode):
    handler = handler_for(mode)
    records = [{handler.query.group_field: "view-1", "attributes.view.url_template": "/orders"}]
    summary = {
        "view-1": {
            "snapshot": {
                "attributes.browser.viewport.width": 1440,
                "attributes.browser.viewport.height": 900,
                "attributes.view.url": "https://example.com/orders?page=2",
            }
        }
    }
    rows = handler.query.fill_records(records, summary)
    with patch.object(handler.query, "query_list", return_value=rows):
        result = flatten_dict_data(handler.list_records(1, 2)[0])
    assert handler.query.virtual_fields["virtual.viewport"].format(result) == "1440 x 900"
    if mode == "view":
        assert result["attributes.view.url"] == "https://example.com/orders?page=2"
        assert result["attributes.view.url_template"] == "/orders"


@pytest.mark.parametrize("mode", ["span", "view", "session"])
def test_list_response_returns_raw_values_and_virtual_strings(mocker, mode):
    from rum_web.query.resources import RumRecordsResource

    handler = handler_for(mode)
    row = {
        "span_name": "POST /api/orders",
        "virtual": {"browser": "stale"},
        "virtual.network": "stale",
        "resource": {"user_agent": {"name": "Chrome", "version": "131", "os": {"name": "macOS"}}},
        "attributes": {
            "span_type": "resource",
            "resource": {"type": "xhr", "size": 1024, "delivery_type": "cache", "transfer_size": 0},
            "http": {"request": {"method": "POST"}, "response": {"status_code": 200}},
            "browser": {"viewport": {"width": 1440, "height": 900}},
            "network": {"connection": {"type": "wifi"}, "effective_type": "4g"},
        },
    }
    original = deepcopy(row)
    mocker.patch("rum_web.query.resources._get_application")
    mocker.patch("rum_web.query.resources._build_data_sources", return_value=[])
    mocker.patch("rum_web.query.resources.RumLevelHandlerFactory.create", return_value=handler)
    mocker.patch.object(handler.query, "query_list", return_value=[row])
    result = RumRecordsResource().request(
        {
            "bk_biz_id": 2,
            "app_name": "test",
            "mode": mode,
            "start_time": 1,
            "end_time": 2,
        }
    )["list"][0]
    assert row == original
    assert result["span_name"] == "POST /api/orders"
    assert result["attributes.resource.size"] == 1024
    assert result["attributes.resource.delivery_type"] == "cache"
    assert result["resource.user_agent.name"] == "Chrome"
    assert result["virtual.browser"] == "Chrome 131"
    assert result["virtual.network"] == "wifi / 4g"
    assert "attributes.error.source" not in result
    assert "composite_cells" not in result
    assert all(not isinstance(value, dict) for value in result.values())
    assert result["virtual.viewport"] == "1440 x 900"


def test_view_config_includes_frontend_selection_rules():
    fields = {field["field_name"]: field for field in view_config("span")["fields"]}
    layout = fields["span_name"]["extra_config"]["composite"]
    badges = {item["field_name"]: item for item in layout["sections"][0]["badges"]}
    assert badges["attributes.http.request.method"]["show_if"] == {
        "attributes.span_type": ["resource"],
        "attributes.resource.type": ["xhr", "fetch"],
    }
    subtitle = layout["sections"][1]
    assert {item["field_name"]: item["show_if"] for item in subtitle["items"]} == {
        "attributes.action.target.tag": {"attributes.span_type": ["action"]},
        "attributes.view.url": {"attributes.span_type": ["view"]},
        "attributes.url.full": {"attributes.span_type": ["resource"]},
    }
