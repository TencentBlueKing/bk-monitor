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
from typing import Any

import pytest
from pytest_mock import MockerFixture

from apm_web.constants import CategoryEnum, CustomServiceMatchType, CustomServiceType, DataStatus, TopoNodeKind
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import Application, ApplicationCustomService
from constants.apm import TelemetryDataType


NOW = 1_800_000_000
BK_BIZ_ID = 2
APP_NAME = "demo"


@pytest.fixture
def application(mocker: MockerFixture) -> Application:
    app = Application(
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        is_enabled_trace=True,
        is_enabled_metric=True,
        is_enabled_log=True,
        is_enabled_profiling=True,
    )
    app.no_data_period = 5
    mocker.patch("apm_web.handlers.service_handler.time.time", return_value=NOW)
    return app


@pytest.mark.parametrize(
    ("age_seconds", "expected"),
    [
        (0, DataStatus.NORMAL),
        (5 * 60, DataStatus.NORMAL),
        (15 * 60, DataStatus.NORMAL),
        (15 * 60 + 1, DataStatus.NO_DATA),
    ],
)
def test_heartbeat_fresh_tolerates_one_cycle(
    application: Application, mocker: MockerFixture, age_seconds: int, expected: str
) -> None:
    related_services = mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services",
        return_value=set(),
    )
    node = {
        "topo_key": "orders",
        "source": [],
        "heartbeat": {
            data_type.value: {"last_data_at": NOW - age_seconds, "checked_at": NOW} for data_type in TelemetryDataType
        },
    }

    assert ServiceHandler.build_service_data_status(application, [node]) == {
        "orders": {data_type.value: expected for data_type in TelemetryDataType}
    }
    if expected == DataStatus.NORMAL:
        related_services.assert_not_called()


@pytest.mark.parametrize("disabled_type", TelemetryDataType.values())
def test_build_service_data_status_disabled_first(
    application: Application, mocker: MockerFixture, disabled_type: str
) -> None:
    setattr(application, f"is_enabled_{disabled_type}", False)
    related_services = mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services",
        return_value={"orders"},
    )
    node = {
        "topo_key": "orders",
        "heartbeat": {data_type.value: {"last_data_at": NOW} for data_type in TelemetryDataType},
    }

    status = ServiceHandler.build_service_data_status(application, [node])["orders"]

    assert status == {
        data_type.value: DataStatus.DISABLED if data_type.value == disabled_type else DataStatus.NORMAL
        for data_type in TelemetryDataType
    }
    related_services.assert_not_called()


@pytest.mark.parametrize(
    "heartbeat_entry",
    [None, {}, {"checked_at": NOW}, {"last_data_at": None, "checked_at": NOW}, {"last_data_at": 0, "checked_at": NOW}],
)
def test_build_service_data_status_missing_data_time_is_no_data(
    application: Application, mocker: MockerFixture, heartbeat_entry: dict[str, Any] | None
) -> None:
    mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services", return_value=set()
    )
    nodes = [
        {
            "topo_key": "orders",
            "source": TelemetryDataType.values(),
            "heartbeat": {data_type.value: heartbeat_entry for data_type in TelemetryDataType},
        },
        {"topo_key": "http:manual"},
        {"topo_key": "empty-heartbeat", "heartbeat": None},
    ]

    assert ServiceHandler.build_service_data_status(application, nodes) == {
        node["topo_key"]: {data_type.value: DataStatus.NO_DATA for data_type in TelemetryDataType} for node in nodes
    }


def test_build_service_data_status_log_dual_source(application: Application, mocker: MockerFixture) -> None:
    related_services = mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services",
        return_value={"related"},
    )
    nodes = [
        {"topo_key": "heartbeat", "heartbeat": {"log": {"last_data_at": NOW}}},
        {"topo_key": "related", "heartbeat": {"log": {"last_data_at": NOW - 16 * 60, "checked_at": NOW}}},
        {"topo_key": "missing"},
    ]

    mapping = ServiceHandler.build_service_data_status(application, nodes)

    assert [mapping[name]["log"] for name in ("heartbeat", "related", "missing")] == [
        DataStatus.NORMAL,
        DataStatus.NORMAL,
        DataStatus.NO_DATA,
    ]
    assert all(mapping[name]["trace"] == DataStatus.NO_DATA for name in mapping)
    related_services.assert_called_once_with(application, ["related", "missing"])


def test_build_service_data_status_empty_nodes_skips_related_logs(
    application: Application, mocker: MockerFixture
) -> None:
    related_services = mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services"
    )

    assert ServiceHandler.build_service_data_status(application, []) == {}
    related_services.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("as_dict", [False, True])
def test_list_services_includes_status_without_changing_cached_topology(
    application: Application, mocker: MockerFixture, as_dict: bool
) -> None:
    nodes = [
        {
            "topo_key": "orders",
            "extra_data": {"category": CategoryEnum.HTTP, "kind": TopoNodeKind.SERVICE, "service_language": "python"},
            "heartbeat": {"trace": {"last_data_at": NOW}},
        }
    ]
    original_nodes = copy.deepcopy(nodes)
    ApplicationCustomService.objects.create(
        bk_biz_id=BK_BIZ_ID,
        app_name=APP_NAME,
        name="manual",
        type=CustomServiceType.HTTP,
        match_type=CustomServiceMatchType.MANUAL,
        rule={},
    )
    related_services = mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services", return_value=set()
    )
    topology_query = mocker.patch("apm_web.handlers.service_handler.api.apm_api.query_topo_node", return_value=nodes)
    app = (
        {
            "bk_biz_id": BK_BIZ_ID,
            "app_name": APP_NAME,
            "is_enabled_trace": True,
            "is_enabled_metric": True,
            "is_enabled_log": True,
            "is_enabled_profiling": True,
        }
        if as_dict
        else application
    )
    ServiceHandler.list_nodes.cache_clear()
    try:
        services = ServiceHandler.list_services(app, include_data_status=True)

        assert [node["topo_key"] for node in services] == ["orders", "http:manual"]
        assert services[0]["data_status"] == {
            "trace": DataStatus.NORMAL,
            "metric": DataStatus.NO_DATA,
            "log": DataStatus.NO_DATA,
            "profiling": DataStatus.NO_DATA,
        }
        assert services[1]["data_status"] == {data_type.value: DataStatus.NO_DATA for data_type in TelemetryDataType}
        assert nodes == original_nodes
        assert ServiceHandler.list_nodes(BK_BIZ_ID, APP_NAME) == original_nodes

        plain_services = ServiceHandler.list_services(app)

        assert all("data_status" not in node for node in plain_services)
        topology_query.assert_called_once_with(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
        assert related_services.call_count == 1
    finally:
        ServiceHandler.list_nodes.cache_clear()


def test_list_services_without_status_skips_state_and_related_logs(
    application: Application, mocker: MockerFixture
) -> None:
    nodes = [{"topo_key": "orders", "extra_data": {"kind": TopoNodeKind.SERVICE}}]
    mocker.patch.object(ServiceHandler, "list_nodes", return_value=nodes)
    mocker.patch.object(ApplicationCustomService.objects, "filter", return_value=[])
    build_status = mocker.patch.object(ServiceHandler, "build_service_data_status")
    related_services = mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services"
    )

    assert ServiceHandler.list_services(application) == nodes
    build_status.assert_not_called()
    related_services.assert_not_called()
