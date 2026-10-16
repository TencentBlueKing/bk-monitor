"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.core.cache import cache
from pytest_mock import MockerFixture

from apm_web.constants import ApmCacheKey, CustomServiceMatchType, CustomServiceType, DataStatus
from apm_web.handlers.log_handler import ServiceLogHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric.resources import ServiceListAsyncResource, ServiceListResource
from apm_web.models import Application, ApplicationCustomService
from constants.apm import TelemetryDataType

pytestmark = pytest.mark.django_db


@pytest.fixture
def service_status_context(mocker: MockerFixture) -> Iterator[tuple[Application, mock.Mock]]:
    app = Application.objects.create(
        application_id=1,
        bk_biz_id=2,
        app_name="demo",
        trace_result_table_id="trace.demo",
        metric_result_table_id="metric.demo",
        is_enabled_trace=True,
        is_enabled_metric=True,
        is_enabled_log=True,
        is_enabled_profiling=False,
    )
    nodes = [
        {
            "topo_key": name,
            "extra_data": {"category": "http", "kind": "service", "service_language": "python"},
            "source": [data_type],
            "heartbeat": {data_type: {"last_data_at": timestamp, "checked_at": 2_000_000_000}},
        }
        for name, data_type, timestamp in (
            ("orders", "trace", 2_000_000_000),
            ("metrics", "metric", 2_000_000_000),
            ("logs", "log", 1),
            ("stale", "trace", 1),
            ("profile-only", "profiling", 2_000_000_000),
        )
    ]
    ApplicationCustomService.objects.create(
        bk_biz_id=app.bk_biz_id,
        app_name=app.app_name,
        name="manual",
        type=CustomServiceType.HTTP,
        match_type=CustomServiceMatchType.MANUAL,
        rule={},
    )
    mocker.patch("apm_web.handlers.service_handler.time.time", return_value=2_000_000_000)
    mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services", return_value={"logs"}
    )
    topo_query = mocker.patch("apm_web.handlers.service_handler.api.apm_api.query_topo_node", return_value=nodes)
    mocker.patch.object(ServiceHandler, "get_service_data_status_mapping", side_effect=AssertionError("旧状态重算"))
    mocker.patch.object(ServiceHandler, "get_service_metric_range_mapping", side_effect=AssertionError("指标状态查询"))
    mocker.patch("apm_web.handlers.service_handler.ServiceFlowCount", side_effect=AssertionError("Flow 状态查询"))
    mocker.patch(
        "apm_web.handlers.service_handler.api.apm_api.query_profile_services_detail",
        side_effect=AssertionError("Profiling 查询"),
    )
    mocker.patch("apm_web.handlers.service_handler.api.log_search.es_query_dsl", side_effect=AssertionError("ES 聚合"))
    cache_key = ApmCacheKey.APP_SERVICE_STATUS_KEY.format(application_id=app.application_id)
    old_status = json.dumps({"orders": {data_type: DataStatus.DISABLED for data_type in TelemetryDataType.values()}})
    cache_get = mocker.patch.object(
        cache, "get", side_effect=lambda key, *args, **kwargs: old_status if key == cache_key else None
    )
    cache_set = mocker.patch.object(cache, "set")
    ServiceHandler.list_nodes.cache_clear()
    yield app, topo_query
    assert all(call.args[0] != cache_key for call in [*cache_get.call_args_list, *cache_set.call_args_list])
    ServiceHandler.list_nodes.cache_clear()


def sync_request(app: Application, **overrides: Any) -> dict[str, Any]:
    params = {
        "bk_biz_id": app.bk_biz_id,
        "app_name": app.app_name,
        "start_time": 1,
        "end_time": 2,
        "include_data_status": True,
        "sort": "service_name",
        **overrides,
    }
    resource = ServiceListResource()
    serializer = resource.RequestSerializer(data=params)
    serializer.is_valid(raise_exception=True)
    return resource.perform_request(serializer.validated_data)


@pytest.mark.parametrize("column", ["data_status", *[f"{kind}_data_status" for kind in TelemetryDataType.values()]])
def test_async_status_columns_use_heartbeat_and_full_service_filters(
    service_status_context: tuple[Application, mock.Mock], mocker: MockerFixture, column: str
) -> None:
    app, topo_query = service_status_context
    list_services = mocker.spy(ServiceHandler, "list_services")
    result = ServiceListAsyncResource().perform_request(
        {
            "bk_biz_id": app.bk_biz_id,
            "app_name": app.app_name,
            "start_time": 1,
            "end_time": 2,
            "column": column,
            "service_names": ["orders", "http:manual"],
            "filter_keys": ["have_data", "apply_module"],
        }
    )

    assert [row["service_name"] for row in result["data"]] == ["orders", "http:manual"]
    expected = {
        "metric": DataStatus.NO_DATA,
        "log": DataStatus.NO_DATA,
        "trace": DataStatus.NORMAL,
        "profiling": DataStatus.DISABLED,
    }
    types = TelemetryDataType.values() if column == "data_status" else [column.removesuffix("_data_status")]
    for kind in types:
        assert result["data"][0][f"{kind}_data_status"] == {"icon": expected[kind]}
        assert result["data"][1][f"{kind}_data_status"] == {
            "icon": DataStatus.DISABLED if kind == "profiling" else DataStatus.NO_DATA
        }
    filters = {field["id"]: {item["id"]: item["count"] for item in field["data"]} for field in result["filter"]}
    assert filters["have_data"] == {"true": 3, "false": 2}
    assert filters["apply_module"] == {"metric": 5, "log": 5, "trace": 5, "profiling": 0}
    list_services.assert_called_once()
    topo_query.assert_called_once_with(bk_biz_id=app.bk_biz_id, app_name=app.app_name)


def test_sync_status_columns_reuse_nodes_and_keep_total_count(
    service_status_context: tuple[Application, mock.Mock], mocker: MockerFixture
) -> None:
    app, topo_query = service_status_context
    list_services = mocker.spy(ServiceHandler, "list_services")
    result = sync_request(app, page=1, page_size=1)

    assert result["total"] == 5
    assert len(result["data"]) == 1
    assert result["data"][0]["service_name"]["value"] == "http:manual"
    for kind in TelemetryDataType.values():
        assert result["data"][0][f"{kind}_data_status"] == {
            "icon": DataStatus.DISABLED if kind == "profiling" else DataStatus.NO_DATA
        }
    app.refresh_from_db()
    assert app.service_count == 5
    list_services.assert_called_once()
    topo_query.assert_called_once()


def test_sync_without_status_skips_related_log_lookup(
    service_status_context: tuple[Application, mock.Mock], mocker: MockerFixture
) -> None:
    app, _ = service_status_context
    related_logs = mocker.patch.object(ServiceLogHandler, "list_available_related_services")

    result = sync_request(app, include_data_status=False)

    assert result["total"] == 5
    related_logs.assert_not_called()


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        ([{"key": "have_data", "value": ["true"]}], {"orders", "metrics", "logs"}),
        ([{"key": "have_data", "value": ["false"]}], {"stale", "http:manual"}),
        ([{"key": "apply_module", "value": ["profiling"]}], set()),
        ([{"key": "apply_module", "value": ["metric"]}], {"orders", "metrics", "logs", "stale", "http:manual"}),
        (
            [{"key": "have_data", "value": ["false"]}, {"key": "apply_module", "value": ["log"]}],
            {"orders", "metrics", "logs", "stale", "http:manual"},
        ),
    ],
)
def test_sync_status_filters_keep_existing_rules(
    service_status_context: tuple[Application, mock.Mock], conditions: list[dict[str, Any]], expected: set[str]
) -> None:
    app, _ = service_status_context
    result = sync_request(app, include_data_status=False, field_conditions=conditions)

    assert {row["service_name"]["value"] for row in result["data"]} == expected
    assert result["total"] == len(expected)
    app.refresh_from_db()
    assert app.service_count == 5
