"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from apm_web.constants import CustomServiceMatchType, CustomServiceType, DataStatus
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
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services",
        side_effect=lambda _app, service_names: {"logs"} & set(service_names),
    )
    topo_query = mocker.patch("apm_web.handlers.service_handler.api.apm_api.query_topo_node", return_value=nodes)
    mocker.patch.object(ServiceHandler, "get_service_metric_range_mapping", side_effect=AssertionError("指标状态查询"))
    mocker.patch("apm_web.handlers.service_handler.ServiceFlowCount", side_effect=AssertionError("Flow 状态查询"))
    mocker.patch(
        "apm_web.handlers.service_handler.api.apm_api.query_profile_services_detail",
        side_effect=AssertionError("Profiling 查询"),
    )
    mocker.patch("apm_web.handlers.service_handler.api.log_search.es_query_dsl", side_effect=AssertionError("ES 聚合"))
    ServiceHandler.list_nodes.cache_clear()
    yield app, topo_query
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


def async_request(app: Application, column: str, service_names: list[str], **overrides: Any) -> dict[str, Any]:
    resource = ServiceListAsyncResource()
    serializer = resource.RequestSerializer(
        data={
            "bk_biz_id": app.bk_biz_id,
            "app_name": app.app_name,
            "start_time": 1,
            "end_time": 2,
            "column": column,
            "service_names": service_names,
            **overrides,
        }
    )
    serializer.is_valid(raise_exception=True)
    return resource.perform_request(serializer.validated_data)


@pytest.mark.parametrize("column", ["data_status", *[f"{kind}_data_status" for kind in TelemetryDataType.values()]])
def test_async_status_columns_use_heartbeat_and_full_service_filters(
    service_status_context: tuple[Application, mock.Mock], mocker: MockerFixture, column: str
) -> None:
    app, topo_query = service_status_context
    list_services = mocker.spy(ServiceHandler, "list_services")
    result = async_request(app, column, ["orders", "http:manual"], filter_keys=["have_data", "apply_module"])

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


@pytest.mark.parametrize("missing_service", ["unknown", "profile-only"])
@pytest.mark.parametrize("column", ["data_status", *[f"{kind}_data_status" for kind in TelemetryDataType.values()]])
def test_async_missing_first_service_keeps_status_fields_and_full_counts(
    service_status_context: tuple[Application, mock.Mock],
    mocker: MockerFixture,
    missing_service: str,
    column: str,
) -> None:
    app, _ = service_status_context
    list_services = mocker.spy(ServiceHandler, "list_services")

    result = async_request(app, column, [missing_service, "orders"], filter_keys=["have_data", "apply_module"])

    assert [row["service_name"] for row in result["data"]] == [missing_service, "orders"]
    kinds = TelemetryDataType.values() if column == "data_status" else [column.removesuffix("_data_status")]
    expected_fields = {"service_name", *[f"{kind}_data_status" for kind in kinds]}
    assert all(set(row) == expected_fields for row in result["data"])
    for kind in kinds:
        missing_status = DataStatus.DISABLED if kind == "profiling" else DataStatus.NO_DATA
        assert result["data"][0][f"{kind}_data_status"] == {"icon": missing_status}
        assert result["data"][1][f"{kind}_data_status"] == {
            "icon": DataStatus.NORMAL if kind == "trace" else missing_status
        }
    filters = {field["id"]: {item["id"]: item["count"] for item in field["data"]} for field in result["filter"]}
    assert filters["have_data"] == {"true": 3, "false": 2}
    assert filters["apply_module"] == {"metric": 5, "log": 5, "trace": 5, "profiling": 0}
    list_services.assert_called_once()


def test_async_empty_service_set_returns_defaults_and_zero_counts(
    service_status_context: tuple[Application, mock.Mock],
) -> None:
    app, topo_query = service_status_context
    topo_query.return_value = []
    ApplicationCustomService.objects.filter(bk_biz_id=app.bk_biz_id, app_name=app.app_name).delete()

    result = async_request(app, "data_status", ["unknown"], filter_keys=["have_data", "apply_module"])

    assert result["data"] == [
        {
            "service_name": "unknown",
            **{
                f"{kind}_data_status": {"icon": DataStatus.DISABLED if kind == "profiling" else DataStatus.NO_DATA}
                for kind in TelemetryDataType.values()
            },
        }
    ]
    filters = {field["id"]: {item["id"]: item["count"] for item in field["data"]} for field in result["filter"]}
    assert filters["have_data"] == {"true": 0, "false": 0}
    assert filters["apply_module"] == {kind: 0 for kind in TelemetryDataType.values()}


def test_async_service_deleted_after_sync_keeps_default_status_and_current_counts(
    service_status_context: tuple[Application, mock.Mock],
) -> None:
    app, _ = service_status_context
    sync_result = sync_request(app)
    service_names = [row["service_name"]["value"] for row in sync_result["data"]]
    assert service_names[0] == "http:manual"
    ApplicationCustomService.objects.filter(bk_biz_id=app.bk_biz_id, app_name=app.app_name, name="manual").delete()

    result = async_request(app, "data_status", service_names, filter_keys=["have_data", "apply_module"])

    assert [row["service_name"] for row in result["data"]] == service_names
    assert result["data"][0] == {
        "service_name": "http:manual",
        **{
            f"{kind}_data_status": {"icon": DataStatus.DISABLED if kind == "profiling" else DataStatus.NO_DATA}
            for kind in TelemetryDataType.values()
        },
    }
    orders = next(row for row in result["data"] if row["service_name"] == "orders")
    assert orders["trace_data_status"] == {"icon": DataStatus.NORMAL}
    filters = {field["id"]: {item["id"]: item["count"] for item in field["data"]} for field in result["filter"]}
    assert filters["have_data"] == {"true": 3, "false": 1}
    assert filters["apply_module"] == {"metric": 4, "log": 4, "trace": 4, "profiling": 0}


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("trace_data_status", DataStatus.NORMAL),
        ("metric_data_status", DataStatus.NO_DATA),
        ("profiling_data_status", DataStatus.DISABLED),
    ],
)
def test_async_single_non_log_status_ignores_related_log_failure(
    service_status_context: tuple[Application, mock.Mock], mocker: MockerFixture, column: str, expected: str
) -> None:
    app, _ = service_status_context
    related_logs = mocker.patch.object(
        ServiceLogHandler, "list_available_related_services", side_effect=RuntimeError("日志关联不可用")
    )

    result = async_request(app, column, ["unknown", "orders"])

    assert result == {
        "data": [
            {
                "service_name": "unknown",
                column: {"icon": DataStatus.DISABLED if column == "profiling_data_status" else DataStatus.NO_DATA},
            },
            {"service_name": "orders", column: {"icon": expected}},
        ]
    }
    related_logs.assert_not_called()


@pytest.mark.parametrize("column", ["data_status", "log_data_status"])
@pytest.mark.parametrize("service_names", [["unknown", "orders"], ["unknown"]])
def test_async_status_without_filters_skips_unrequested_log_lookup(
    service_status_context: tuple[Application, mock.Mock],
    mocker: MockerFixture,
    column: str,
    service_names: list[str],
) -> None:
    app, topo_query = service_status_context
    topo_query.return_value[0]["heartbeat"]["log"] = {"last_data_at": 2_000_000_000}
    related_logs = mocker.patch.object(
        ServiceLogHandler, "list_available_related_services", side_effect=RuntimeError("无关服务的日志关联不可用")
    )

    result = async_request(app, column, service_names)

    kinds = TelemetryDataType.values() if column == "data_status" else ["log"]
    default_status = {
        kind: DataStatus.DISABLED if kind == "profiling" else DataStatus.NO_DATA for kind in TelemetryDataType.values()
    }
    expected_statuses = {
        "unknown": default_status,
        "orders": {**default_status, "trace": DataStatus.NORMAL, "log": DataStatus.NORMAL},
    }
    assert result == {
        "data": [
            {
                "service_name": name,
                **{f"{kind}_data_status": {"icon": expected_statuses[name][kind]} for kind in kinds},
            }
            for name in service_names
        ]
    }
    related_logs.assert_not_called()


def test_async_single_log_status_keeps_related_index_availability(
    service_status_context: tuple[Application, mock.Mock], mocker: MockerFixture
) -> None:
    app, _ = service_status_context
    related_logs = mocker.patch.object(ServiceLogHandler, "list_available_related_services", return_value={"logs"})

    result = async_request(app, "log_data_status", ["logs"])

    assert result == {"data": [{"service_name": "logs", "log_data_status": {"icon": DataStatus.NORMAL}}]}
    related_logs.assert_called_once_with(app, ["logs"])


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
