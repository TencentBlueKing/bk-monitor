"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from apm_web.constants import (
    ApmCacheKey,
    CategoryEnum,
    CustomServiceMatchType,
    CustomServiceType,
    DataStatus,
    TopoNodeKind,
)
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import Application, ApplicationCustomService
from constants.apm import TelemetryDataType

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
APP_NAME = "demo"


@pytest.fixture
def topology(mocker: MockerFixture) -> Iterator[tuple[list[dict[str, Any]], mock.Mock, mock.Mock]]:
    nodes = [
        {
            "topo_key": name,
            "extra_data": {
                "category": category,
                "kind": kind,
                "predicate_value": "",
                "service_language": "",
            },
            "source": [data_type],
            "heartbeat": {data_type: {"last_data_at": 100, "checked_at": 110}},
        }
        for name, category, kind, data_type in (
            ("orders", CategoryEnum.HTTP, TopoNodeKind.SERVICE, TelemetryDataType.TRACE.value),
            ("logs", CategoryEnum.OTHER, TopoNodeKind.SERVICE, TelemetryDataType.LOG.value),
            ("worker", CategoryEnum.OTHER, TopoNodeKind.SERVICE, TelemetryDataType.PROFILING.value),
            ("orders-mysql", CategoryEnum.DB, TopoNodeKind.COMPONENT, TelemetryDataType.METRIC.value),
            ("http:existing", CategoryEnum.HTTP, TopoNodeKind.REMOTE_SERVICE, TelemetryDataType.TRACE.value),
        )
    ]
    ServiceHandler.list_nodes.cache_clear()
    topo_query = mocker.patch("apm_web.handlers.service_handler.api.apm_api.query_topo_node", return_value=nodes)
    profile_query = mocker.patch(
        "apm_web.handlers.service_handler.api.apm_api.query_profile_services_detail", return_value=[{"name": "worker"}]
    )
    yield nodes, topo_query, profile_query
    ServiceHandler.list_nodes.cache_clear()


@pytest.mark.parametrize("as_dict", [False, True])
@pytest.mark.parametrize("profiling_enabled", [False, True])
def test_list_services_uses_topology_and_scoped_manual_services(
    topology: tuple[list[dict[str, Any]], mock.Mock, mock.Mock], as_dict: bool, profiling_enabled: bool
) -> None:
    nodes, topo_query, profile_query = topology
    expected_nodes = copy.deepcopy(nodes)
    if not profiling_enabled:
        expected_nodes.pop(2)
    ApplicationCustomService.objects.bulk_create(
        [
            ApplicationCustomService(
                bk_biz_id=biz_id,
                app_name=app_name,
                name=name,
                type=CustomServiceType.HTTP,
                match_type=match_type,
                rule={},
            )
            for biz_id, app_name, name, match_type in (
                (BK_BIZ_ID, APP_NAME, "existing", CustomServiceMatchType.MANUAL),
                (BK_BIZ_ID, APP_NAME, "manual", CustomServiceMatchType.MANUAL),
                (BK_BIZ_ID, APP_NAME, "automatic", CustomServiceMatchType.AUTO),
                (BK_BIZ_ID + 1, APP_NAME, "other-biz", CustomServiceMatchType.MANUAL),
                (BK_BIZ_ID, "other-app", "other-app", CustomServiceMatchType.MANUAL),
            )
        ]
    )
    app_data = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "is_enabled_profiling": profiling_enabled}
    application = app_data if as_dict else Application(**app_data)

    services = ServiceHandler.list_services(application)

    assert services[: len(expected_nodes)] == expected_nodes
    assert [service["topo_key"] for service in services] == [
        "orders",
        "logs",
        *(["worker"] if profiling_enabled else []),
        "orders-mysql",
        "http:existing",
        "http:manual",
    ]
    assert services[-1]["extra_data"]["kind"] == TopoNodeKind.REMOTE_SERVICE
    topo_query.assert_called_once_with(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
    profile_query.assert_not_called()


@pytest.mark.parametrize("as_dict", [False, True])
def test_list_services_excludes_profiling_only_when_disabled(
    topology: tuple[list[dict[str, Any]], mock.Mock, mock.Mock], as_dict: bool
) -> None:
    nodes, topo_query, profile_query = topology
    nodes[0]["source"] = [TelemetryDataType.PROFILING.value, TelemetryDataType.TRACE.value]
    nodes[1]["source"] = [TelemetryDataType.LOG.value, TelemetryDataType.PROFILING.value]
    nodes[3]["source"] = []
    nodes[4].pop("source")
    expected_nodes = copy.deepcopy(nodes)
    app_data = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "is_enabled_profiling": True}
    application = app_data if as_dict else Application(**app_data)

    assert ServiceHandler.list_services(application) == expected_nodes

    if as_dict:
        application.pop("is_enabled_profiling")
    else:
        application.is_enabled_profiling = False

    assert [service["topo_key"] for service in ServiceHandler.list_services(application)] == [
        "orders",
        "logs",
        "orders-mysql",
        "http:existing",
    ]

    if as_dict:
        application["is_enabled_profiling"] = True
    else:
        application.is_enabled_profiling = True

    assert ServiceHandler.list_services(application) == expected_nodes
    assert nodes == expected_nodes
    topo_query.assert_called_once_with(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
    profile_query.assert_not_called()


@pytest.mark.parametrize("with_manual_service", [False, True])
def test_list_services_with_empty_topology(
    topology: tuple[list[dict[str, Any]], mock.Mock, mock.Mock], with_manual_service: bool
) -> None:
    nodes, _, profile_query = topology
    nodes.clear()
    if with_manual_service:
        ApplicationCustomService.objects.create(
            bk_biz_id=BK_BIZ_ID,
            app_name=APP_NAME,
            name="manual",
            type=CustomServiceType.HTTP,
            match_type=CustomServiceMatchType.MANUAL,
            rule={},
        )

    services = ServiceHandler.list_services({"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME})

    assert [service["topo_key"] for service in services] == (["http:manual"] if with_manual_service else [])
    profile_query.assert_not_called()


def test_manual_services_do_not_change_cached_topology(
    topology: tuple[list[dict[str, Any]], mock.Mock, mock.Mock],
) -> None:
    nodes, topo_query, _ = topology
    expected_nodes = copy.deepcopy(nodes)
    app_data = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "is_enabled_profiling": True}
    custom_service = ApplicationCustomService.objects.create(
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        name="manual",
        type=CustomServiceType.HTTP,
        match_type=CustomServiceMatchType.MANUAL,
        rule={},
    )
    services = ServiceHandler.list_services(app_data)

    assert services[-1]["topo_key"] == "http:manual"
    assert nodes == expected_nodes

    ApplicationCustomService.objects.filter(pk=custom_service.pk).delete()
    assert ServiceHandler.list_services(app_data) == expected_nodes
    topo_query.assert_called_once_with(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)


@pytest.mark.parametrize("profiling_enabled", [False, True])
def test_service_count_refresh_keeps_existing_status_cache(
    topology: tuple[list[dict[str, Any]], mock.Mock, mock.Mock], mocker: MockerFixture, profiling_enabled: bool
) -> None:
    nodes, topo_query, profile_query = topology
    expected_names = {node["topo_key"] for node in nodes}
    if not profiling_enabled:
        expected_names.remove("worker")
    application = Application.objects.create(
        application_id=1,
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        is_enabled_trace=False,
        is_enabled_metric=False,
        is_enabled_log=False,
        is_enabled_profiling=profiling_enabled,
    )
    cache_set = mocker.patch("apm_web.models.application.cache.set")

    application.set_service_count_and_data_status()

    application.refresh_from_db()
    assert application.service_count == len(expected_names)
    topo_query.assert_called_once_with(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
    if profiling_enabled:
        profile_query.assert_called_once()
        assert "last_check_time__gt" in profile_query.call_args.kwargs
    else:
        profile_query.assert_not_called()
    cache_set.assert_called_once()
    cache_key, cached_status = cache_set.call_args.args
    assert cache_key == ApmCacheKey.APP_SERVICE_STATUS_KEY.format(application_id=application.application_id)
    status_mapping = json.loads(cached_status)
    assert set(status_mapping) == expected_names
    if profiling_enabled:
        assert status_mapping["worker"][TelemetryDataType.PROFILING.value] == DataStatus.NORMAL
        assert status_mapping["orders"][TelemetryDataType.PROFILING.value] == DataStatus.NO_DATA
        assert status_mapping["worker"][TelemetryDataType.TRACE.value] == DataStatus.DISABLED
    else:
        assert all(
            status[TelemetryDataType.PROFILING.value] == DataStatus.DISABLED for status in status_mapping.values()
        )
