"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import Mock, patch

import pytest

from bk_monitor_base.uptime_check import UptimeCheckNodeModel
from monitor_web.uptime_check.resources import UptimeCheckBeatResource


class MockUptimeCheckNode:
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)


BIZ_NODES = [
    MockUptimeCheckNode(
        pk=1,
        id=1,
        bk_biz_id=2,
        is_common=False,
        name="北京联通",
        ip="192.168.10.11",
        plat_id=0,
        location={"country": "中国", "city": "北京"},
        carrieroperator="联通",
        bk_host_id=1,
    )
]

COMMON_NODES = [
    MockUptimeCheckNode(
        pk=2,
        id=2,
        bk_biz_id=3,
        is_common=True,
        name="广东电信",
        ip="192.168.10.10",
        plat_id=0,
        location={"country": "中国", "city": "广东"},
        carrieroperator="电信",
        bk_host_id=2,
    )
]

UPTIME_CHECK_BEAT_DATA = [
    {
        "gse_status": "0",
        "status": "0",
        "uptime": 746400,
        "ip": "192.168.10.10",
        "bk_host_id": 1,
        "bk_cloud_id": 0,
        "version": "1.8.0",
        "time": 1584337545000,
    },
    {
        "gse_status": "0",
        "status": "0",
        "uptime": 746400,
        "ip": "192.168.10.11",
        "bk_host_id": 2,
        "bk_cloud_id": 0,
        "version": "1.8.0",
        "time": 1584337545000,
    },
]

DATA_BIZ = [
    [
        {
            "status": "0",
            "uptime": 746400,
            "ip": "192.168.10.11",
            "bk_host_id": 2,
            "bk_cloud_id": "0",
            "version": "1.8.0",
            "time": 1584337545000,
        },
        {
            "status": "0",
            "uptime": 746460,
            "bk_host_id": 2,
            "ip": "192.168.10.11",
            "bk_cloud_id": "0",
            "version": "1.8.0",
            "time": 1584337605000,
        },
        {
            "status": "0",
            "uptime": 746520,
            "bk_host_id": 2,
            "ip": "192.168.10.11",
            "bk_cloud_id": "0",
            "version": "1.8.0",
            "time": 1584337665000,
        },
    ],
    [],
]

DATA_COMMON = [
    [],
    [
        {
            "status": "0",
            "uptime": 746400,
            "ip": "192.168.10.10",
            "bk_host_id": 1,
            "bk_cloud_id": "0",
            "version": "1.8.0",
            "time": 1584337545000,
        },
        {
            "status": "0",
            "uptime": 746460,
            "ip": "192.168.10.10",
            "bk_host_id": 1,
            "bk_cloud_id": "0",
            "version": "1.8.0",
            "time": 1584337605000,
        },
        {
            "status": "0",
            "uptime": 746520,
            "ip": "192.168.10.10",
            "bk_host_id": 1,
            "bk_cloud_id": "0",
            "version": "1.8.0",
            "time": 1584337665000,
        },
    ],
]


class MockRequest:
    def __init__(self, method, params=None):
        params = params or {}
        if method.upper() == "GET":
            self.query_params = params
            self.GET = params

        if method.upper() == "POST":
            self.data = params


class MockSerializer:
    def __init__(self, queryset, *arg, **kwargs):
        self.data = []
        for i in queryset:
            self.data.append(i.__dict__)


def get_serializer_side_effect(queryset, *args, **kwargs):
    return MockSerializer(queryset)


def mock_count_side_effect(id):
    mock_node_task = Mock()
    mock_node_task.task = Mock()
    mock_task_all = Mock()
    mock_node_task.tasks.all = Mock()
    mock_node_task.tasks.all.return_value = mock_task_all
    mock_task_all.count = Mock()
    mock_task_all.count.return_value = 3 if id == 1 else 4
    return mock_node_task


def node_filter_side_effect(**kwargs):
    if kwargs.get("bk_biz_id"):
        return set(BIZ_NODES)

    if kwargs.get("is_common"):
        return set(COMMON_NODES)


def mock_node_task_count():
    UptimeCheckNodeModel.objects.get = Mock()
    UptimeCheckNodeModel.objects.get.side_effect = mock_count_side_effect


@pytest.mark.django_db(databases="__all__")
class TestNodeList:
    # def test_list(self, mocker):
    #     from monitor_web.uptime_check.views import UptimeCheckNodeViewSet
    #
    #     params = {"bk_biz_id": 2}
    #     request = MockRequest("GET", params)
    #     view_set = UptimeCheckNodeViewSet()
    #     view_set.request = request
    #     # mock查询公共节点
    #     mock_get_queryset = mocker.patch("monitor_web.models.uptime_check.UptimeCheckNode.objects")
    #     mock_get_queryset.filter.return_value = set(COMMON_NODES)
    #
    #     # mock查询业务节点
    #     view_set.filter_queryset = Mock()
    #     view_set.filter_queryset.return_value = set(BIZ_NODES)
    #     # mock get_serializer
    #     view_set.get_serializer = Mock()
    #     view_set.get_serializer.side_effect = get_serializer_side_effect
    #     # mock心跳查询
    #     mocker.patch(
    #         "monitor_web.uptime_check.resources.UptimeCheckBeatResource.request", return_value=UPTIME_CHECK_BEAT_DATA
    #     )
    #
    #     mocker.patch("monitor_web.cc.resources.get_app_by_id", return_value=MockUptimeCheckNode(name=""))
    #
    #     mock_node_task_count()
    #     result = view_set.list(request)
    #
    #     expected_data = []
    #     for node in BIZ_NODES + COMMON_NODES:
    #         expected_data.append(
    #             {
    #                 "id": node.id,
    #                 "bk_biz_id": node.bk_biz_id,
    #                 "bk_biz_name": "",
    #                 "name": node.name,
    #                 "ip": node.ip,
    #                 "plat_id": node.plat_id,
    #                 "country": node.location.get("country"),
    #                 "province": node.location.get("city"),
    #                 "carrieroperator": node.carrieroperator,
    #                 "task_num": 3 if node.id == 1 else 4,
    #                 "is_common": node.is_common,
    #                 "gse_status": "0",
    #                 "status": "0",
    #                 "version": "1.8.0",
    #             }
    #         )
    #
    #     for data in expected_data:
    #         assert data in result.data

    def test_uptime_check_beat(self, mocker):
        params = {"bk_biz_id": 2}
        patcher = patch(
            "bk_monitor_base.uptime_check.UptimeCheckNodeModel.objects.filter",
            side_effect=node_filter_side_effect,
        )
        patcher.start()
        mocker.patch(
            "monitor_web.uptime_check.resources.GetBeatDataResource.bulk_request",
            return_value=[DATA_BIZ[0], DATA_COMMON[1]],
        )
        mocker.patch(
            "monitor_web.cc.resources.cmdb.agent_status", side_effect=[{"192.168.10.10|0": 0}, {"192.168.10.11|0": 0}]
        )
        result = UptimeCheckBeatResource().request(params)
        assert {
            "gse_status": "0",
            "status": "0",
            "ip": "192.168.10.11",
            "bk_cloud_id": 0,
            "version": "1.8.0",
        } in result
        assert {
            "gse_status": "0",
            "status": "0",
            "ip": "192.168.10.10",
            "bk_cloud_id": 0,
            "version": "1.8.0",
        } in result

        patcher.stop()

    def test_uptime_check_beat_only_biz(self, mocker):
        params = {"bk_biz_id": 2}
        patcher = patch(
            "bk_monitor_base.uptime_check.UptimeCheckNodeModel.objects.filter",
            side_effect=node_filter_side_effect,
        )
        patcher.start()
        mocker.patch("monitor_web.uptime_check.resources.GetBeatDataResource.bulk_request", return_value=DATA_BIZ)
        mocker.patch(
            "monitor_web.cc.resources.cmdb.agent_status", side_effect=[{"192.168.10.10|0": 0}, {"192.168.10.11|0": 0}]
        )
        result = UptimeCheckBeatResource().request(params)
        assert {
            "gse_status": "0",
            "status": "0",
            "ip": "192.168.10.11",
            "bk_cloud_id": 0,
            "version": "1.8.0",
        } in result
        assert {
            "gse_status": "0",
            "status": "-1",
            "ip": "192.168.10.10",
            "bk_cloud_id": 0,
            "version": "",
        } in result

        patcher.stop()

    def test_uptime_check_beat_only_common(self, mocker):
        params = {"bk_biz_id": 2}
        patcher = patch(
            "bk_monitor_base.uptime_check.UptimeCheckNodeModel.objects.filter",
            side_effect=node_filter_side_effect,
        )
        patcher.start()
        mocker.patch("monitor_web.uptime_check.resources.GetBeatDataResource.bulk_request", return_value=DATA_COMMON)
        mocker.patch(
            "monitor_web.cc.resources.cmdb.agent_status", side_effect=[{"192.168.10.10|0": 0}, {"192.168.10.11|0": 0}]
        )
        result = UptimeCheckBeatResource().request(params)
        assert {
            "gse_status": "0",
            "status": "-1",
            "ip": "192.168.10.11",
            "bk_cloud_id": 0,
            "version": "",
        } in result
        assert {
            "gse_status": "0",
            "status": "0",
            "ip": "192.168.10.10",
            "bk_cloud_id": 0,
            "version": "1.8.0",
        } in result

        patcher.stop()
