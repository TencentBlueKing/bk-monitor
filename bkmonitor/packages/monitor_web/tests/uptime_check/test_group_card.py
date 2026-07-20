"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from monitor_web.uptime_check.resources import UptimeCheckGroupCardResource


@pytest.fixture
def patch_env(mocker):
    mocker.patch("monitor_web.uptime_check.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.uptime_check.resources.count_groups", return_value=0)
    mocker.patch("monitor_web.uptime_check.resources.list_groups", return_value=[])
    mocker.patch("monitor_web.uptime_check.resources.list_group_task_stats", return_value={})
    mocks = SimpleNamespace(
        alarm_info=mocker.patch("monitor_web.uptime_check.resources._query_task_alarm_info", return_value={}),
        list_nodes=mocker.patch("monitor_web.uptime_check.resources.list_nodes", return_value=[]),
    )
    return mocks


@pytest.mark.django_db(databases="__all__")
class TestGroupCard:
    def test_card_structure_and_aggregation(self, patch_env, mocker):
        group = SimpleNamespace(id=1, name="核心服务", logo="", bk_biz_id=2)
        mocker.patch("monitor_web.uptime_check.resources.count_groups", return_value=1)
        mocker.patch("monitor_web.uptime_check.resources.list_groups", return_value=[group])
        mocker.patch(
            "monitor_web.uptime_check.resources.list_group_task_stats",
            return_value={1: [(101, "HTTP"), (102, "HTTP"), (103, "ICMP")]},
        )

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": 2})

        assert result["count"] == 1
        card = result["results"][0]
        assert card["id"] == 1
        assert card["name"] == "核心服务"
        assert card["bk_biz_id"] == 2
        assert card["task_num"] == 3
        assert card["protocol_num"] == [{"name": "HTTP", "val": 2}, {"name": "ICMP", "val": 1}]
        assert card["alarm_num"] == 0
        assert result["has_node"] is False

    def test_pagination_by_group(self, patch_env, mocker):
        groups = [SimpleNamespace(id=i, name=f"组{i}", logo="", bk_biz_id=2) for i in range(1, 4)]
        mocker.patch("monitor_web.uptime_check.resources.count_groups", return_value=3)
        mocker.patch("monitor_web.uptime_check.resources.list_groups", return_value=[groups[2]])

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": 2, "page": 2, "page_size": 1})

        assert result["count"] == 3
        assert len(result["results"]) == 1
        assert result["results"][0]["name"] == "组3"

    def test_page_size_limit(self, patch_env):
        with pytest.raises(Exception):
            UptimeCheckGroupCardResource().request({"bk_biz_id": 2, "page_size": 501})

    def test_alarm_num_mapped_to_group(self, patch_env, mocker):
        group = SimpleNamespace(id=1, name="组A", logo="", bk_biz_id=2)
        mocker.patch("monitor_web.uptime_check.resources.count_groups", return_value=1)
        mocker.patch("monitor_web.uptime_check.resources.list_groups", return_value=[group])
        mocker.patch(
            "monitor_web.uptime_check.resources.list_group_task_stats",
            return_value={1: [(101, "HTTP"), (102, "HTTP")]},
        )
        patch_env.alarm_info.return_value = {
            101: {"alarm_num": 2, "available_alarm": True, "task_duration_alarm": False},
            102: {"alarm_num": 1, "available_alarm": False, "task_duration_alarm": True},
        }

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": 2})

        assert result["results"][0]["alarm_num"] == 3

    def test_deleted_task_excluded(self, patch_env, mocker):
        group = SimpleNamespace(id=1, name="组A", logo="", bk_biz_id=2)
        mocker.patch("monitor_web.uptime_check.resources.count_groups", return_value=1)
        mocker.patch("monitor_web.uptime_check.resources.list_groups", return_value=[group])
        # list_group_task_stats 返回的成员已由 operation 层过滤 is_deleted=False
        mocker.patch(
            "monitor_web.uptime_check.resources.list_group_task_stats",
            return_value={1: [(101, "HTTP")]},
        )

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": 2})

        card = result["results"][0]
        assert card["task_num"] == 1
        assert card["protocol_num"] == [{"name": "HTTP", "val": 1}]

    def test_has_node(self, patch_env, mocker):
        group = SimpleNamespace(id=1, name="组", logo="", bk_biz_id=2)
        mocker.patch("monitor_web.uptime_check.resources.count_groups", return_value=1)
        mocker.patch("monitor_web.uptime_check.resources.list_groups", return_value=[group])
        mocker.patch("monitor_web.uptime_check.resources.list_group_task_stats", return_value={})
        patch_env.list_nodes.return_value = [SimpleNamespace(id=1, name="节点")]

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": 2})

        assert result["has_node"] is True
        assert patch_env.list_nodes.call_args.kwargs["query"] == {"include_common": True}

    def test_empty_biz(self, patch_env):
        result = UptimeCheckGroupCardResource().request({"bk_biz_id": 2})

        assert result == {"count": 0, "results": [], "has_node": False}
        # 无分组时不触发 ES 告警查询
        patch_env.alarm_info.assert_not_called()

    def test_include_global_groups(self, patch_env, mocker):
        # 注册 count_groups 和 list_groups 的 mock，验证 query 含 include_global=True
        count_mock = mocker.patch("monitor_web.uptime_check.resources.count_groups")
        list_mock = mocker.patch("monitor_web.uptime_check.resources.list_groups", return_value=[])

        UptimeCheckGroupCardResource().request({"bk_biz_id": 2})

        assert count_mock.call_args.kwargs["query"] == {"include_global": True}
        assert list_mock.call_args.kwargs["query"] == {"include_global": True}
