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

import pytest
from django.test import override_settings
from pytest_mock import MockerFixture

from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import Application
from apm_web.service.resources import ServiceInfoResource

pytestmark = pytest.mark.django_db

NOW = 1_800_000_000
SERVICE_NAME = "service-a"


@pytest.fixture
def service_context(mocker: MockerFixture) -> Iterator[Application]:
    application = Application.objects.create(application_id=1, bk_biz_id=2, app_name="demo", is_enabled_profiling=True)
    mocker.patch("apm_web.handlers.service_handler.time.time", return_value=NOW)
    for method, result in (
        ("get_app_relation_info", {}),
        ("get_log_relation_infos", []),
        ("get_cmdb_relation_info", {}),
        ("get_uri_relation_infos", []),
        ("get_apdex_relation_info", {}),
        ("get_labels", []),
    ):
        mocker.patch.object(ServiceInfoResource, method, return_value=result)
    mocker.patch("apm_web.service.resources.EventServiceRelation.get_relations", return_value=[])
    mocker.patch("apm_web.service.resources.RelationMetricHandler.list_instances", return_value=[])
    mocker.patch(
        "apm_web.handlers.service_handler.ServiceLogHandler.list_available_related_services",
        side_effect=AssertionError("Profiling 状态不应查询关联日志"),
    )
    ServiceHandler.list_nodes.cache_clear()
    yield application
    ServiceHandler.list_nodes.cache_clear()


@pytest.mark.parametrize(
    ("heartbeat", "enabled", "expected"),
    [
        ({"profiling": {"last_data_at": NOW}}, True, True),
        ({"profiling": {"last_data_at": NOW - 3600}}, True, True),
        ({"profiling": {"last_data_at": NOW - 3601, "checked_at": NOW}}, True, False),
        ({"profiling": {"checked_at": NOW}}, True, False),
        ({"profiling": {"last_data_at": None, "checked_at": NOW}}, True, False),
        ({"profiling": {"last_data_at": 0}}, True, False),
        ({"trace": {"last_data_at": NOW}}, True, False),
        ({}, True, False),
        (None, True, False),
        ({"profiling": {"last_data_at": NOW}}, False, False),
    ],
)
@override_settings(APM_SERVICE_DATA_STATUS_LOOKBACK_SECONDS=3600)
def test_service_info_uses_profiling_heartbeat(
    service_context: Application,
    mocker: MockerFixture,
    heartbeat: dict[str, Any] | None,
    enabled: bool,
    expected: bool,
) -> None:
    service_context.is_enabled_profiling = enabled
    service_context.save(update_fields=["is_enabled_profiling"])
    nodes = [{"topo_key": "another", "heartbeat": {"profiling": {"last_data_at": NOW}}}]
    if heartbeat is not None:
        nodes.append({"topo_key": SERVICE_NAME, "extra_data": {}, "heartbeat": heartbeat})
    topo_query = mocker.patch("apm_web.handlers.service_handler.api.apm_api.query_topo_node", return_value=nodes)
    count_query = mocker.patch(
        "apm_web.profile.doris.querier.QueryTemplate.get_service_count", return_value=int(not expected)
    )

    response = ServiceInfoResource().request(
        {
            "bk_biz_id": service_context.bk_biz_id,
            "app_name": service_context.app_name,
            "service_name": SERVICE_NAME,
            "start_time": 1,
            "end_time": 2,
        }
    )

    assert response["application_id"] == service_context.application_id
    assert response["is_enabled_profiling"] is enabled
    assert response["is_profiling_data_normal"] is expected
    assert response["topo_key"] == SERVICE_NAME
    assert response["instance_count"] == 0
    topo_query.assert_called_once_with(
        bk_biz_id=service_context.bk_biz_id, app_name=service_context.app_name, topo_key=SERVICE_NAME
    )
    count_query.assert_not_called()
