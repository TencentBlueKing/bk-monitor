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
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery
from rum_web.handlers.builder.span.resource_timing import resource_delivery
from rum_web.handlers.level.factory import RumLevelHandlerFactory


def handler_for(mode: str):
    target = TraceDatasourceTarget.build(bk_biz_id=2, app_name="test", table_id="bk_rum.test.span", retention=3)
    return RumLevelHandlerFactory.create(mode, [target])


def view_config(mode: str) -> dict[str, Any]:
    with patch.object(BaseQuery, "_query_fields", return_value={}):
        return handler_for(mode).view_config(None, None)


@pytest.mark.parametrize("mode", ["span", "view", "session"])
def test_composites_reference_available_members_without_becoming_query_dimensions(mode):
    config = view_config(mode)
    fields: dict[str, dict[str, Any]] = {field["field_name"]: field for field in config["fields"]}
    composites = {name: field for name, field in fields.items() if field.get("composite_config")}
    assert composites
    for name, field in composites.items():
        assert not field["is_real"] and not field["is_agg"] and not field["is_searchable"]
        assert field["is_list"] and field["supported_operations"] == []
        layout = field["composite_config"]
        members = {
            item["field_name"]
            for section in layout["sections"]
            for item in [*section.get("items", []), *section.get("badges", [])]
        }
        assert layout["primary"] in members
        assert members <= fields.keys(), name
        assert fields[layout["primary"]]["is_searchable"]
    assert set(config["display_fields"]) <= fields.keys()
    assert "display.environment" in config["display_fields"]
    assert "resource.user_agent.name" in fields
    assert "resource.user_agent.name" not in config["display_fields"]
    assert all(not name.startswith("display.") for group in config["groups"] for name in group["field_names"])
    for defaults in config.get("span_type_display_fields", {}).values():
        assert set(defaults) <= fields.keys()
        assert len(defaults) == len(set(defaults))
        assert defaults[-1] == "end_time"
    if mode == "span":
        assert config["display_fields"] == [
            "display.span_name",
            "elapsed_time",
            "display.environment",
            "attributes.user.id",
            "end_time",
        ]
        assert config["span_type_display_fields"]["resource"] == [
            "display.span_name",
            "elapsed_time",
            "display.resource_size",
            "display.page",
            "display.environment",
            "attributes.user.id",
            "end_time",
        ]
    if mode == "view":
        assert config["display_fields"][0] == "display.page"


def test_page_column_has_identical_members_in_span_and_view():
    fields = {mode: {field["field_name"]: field for field in view_config(mode)["fields"]} for mode in ("span", "view")}
    page = fields["span"]["display.page"]["composite_config"]
    assert page == fields["view"]["display.page"]["composite_config"]
    assert page["primary"] == "attributes.view.url_template"
    assert page["sections"][1]["items"][0]["field_name"] == "attributes.view.url"
    assert page["sections"][0]["badges"] == [
        {"field_name": "virtual.viewport", "icon": "icon-monitor icon-mc-tv"},
        {"field_name": "attributes.view.loading_type"},
    ]


def test_view_fallback_keeps_viewport_from_snapshot_for_shared_page_column():
    handler = handler_for("view")
    records = [{"attributes.view.id": "view-1", "attributes.view.url_template": "/orders"}]
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
    assert result["virtual.viewport"] == "1440 x 900"
    assert result["attributes.view.url"] == "https://example.com/orders?page=2"
    assert result["attributes.view.url_template"] == "/orders"


@pytest.mark.parametrize(
    "values,expected",
    [
        ({"attributes.resource.timing.worker_start": 10}, "Service Worker"),
        ({"attributes.resource.transfer_size": 0, "attributes.resource.decoded_body_size": 30}, "Cache"),
        ({"attributes.resource.delivery_type": "cache", "attributes.resource.transfer_size": 0}, "Cache"),
        ({"attributes.resource.decoded_body_size": 30}, None),
        ({"attributes.resource.transfer_size": 0, "attributes.resource.decoded_body_size": 0}, None),
        ({"attributes.resource.timing.connect_start": 10, "attributes.resource.timing.connect_end": 20}, None),
        ({}, None),
    ],
)
def test_delivery_caption_uses_resource_timing_and_does_not_guess_memory_cache(values, expected):
    assert resource_delivery({"attributes.span_type": "resource", **values}) == expected
    assert resource_delivery({"attributes.span_type": "view", **values}) is None


def test_delivery_is_materialized_only_for_list_and_has_no_query_actions():
    handler = handler_for("span")
    records = [{"attributes": {"span_type": "resource", "resource": {"transfer_size": 0, "decoded_body_size": 30}}}]
    original = deepcopy(records)
    with patch.object(handler.query, "query_list", return_value=records):
        result = handler.list_records(1, 2)
    assert records == original
    assert flatten_dict_data(result[0])["display.resource.delivery"] == "Cache"
    fields = {field["field_name"]: field for field in view_config("span")["fields"]}
    delivery = fields["display.resource.delivery"]
    assert not delivery["is_searchable"] and not delivery["is_agg"] and not delivery["is_list"]
    assert delivery["supported_operations"] == []
