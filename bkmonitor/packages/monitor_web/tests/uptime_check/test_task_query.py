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
from bk_monitor_base.uptime_check import UptimeCheckTask

from monitor_web.uptime_check.resources import UptimeCheckTaskQueryResource


def make_task(**kwargs) -> UptimeCheckTask:
    data = {
        "bk_tenant_id": "tenant",
        "id": 10001,
        "bk_biz_id": 2,
        "name": "任务1",
        "protocol": "HTTP",
        "status": "running",
        "config": {"period": 60, "url_list": ["http://a.com"]},
        "node_ids": [],
        "group_ids": [],
    }
    data.update(kwargs)
    return UptimeCheckTask(**data)


@pytest.fixture
def patch_env(mocker):
    mocker.patch("monitor_web.uptime_check.resources.get_request_tenant_id", return_value="tenant")
    mocks = SimpleNamespace(
        list_tasks=mocker.patch("monitor_web.uptime_check.resources.list_tasks", return_value=[]),
        count_tasks=mocker.patch("monitor_web.uptime_check.resources.count_tasks", return_value=0),
        list_groups=mocker.patch("monitor_web.uptime_check.resources.list_groups", return_value=[]),
        list_nodes=mocker.patch("monitor_web.uptime_check.resources.list_nodes", return_value=[]),
    )
    return mocks


@pytest.mark.django_db(databases="__all__")
class TestTaskQuery:
    def test_response_structure(self, patch_env):
        patch_env.list_tasks.return_value = [make_task()]
        patch_env.count_tasks.return_value = 42

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2, "page": 1, "page_size": 10})

        assert result["count"] == 42
        assert len(result["results"]) == 1
        item = result["results"][0]
        assert item["id"] == 10001
        assert item["protocol"] == "HTTP"
        assert item["status"] == "running"
        # 指标字段不在列表接口返回
        assert "available" not in item
        assert "task_duration" not in item

    def test_pagination_passthrough(self, patch_env):
        UptimeCheckTaskQueryResource().request({"bk_biz_id": 2, "page": 3, "page_size": 20})

        call_kwargs = patch_env.list_tasks.call_args.kwargs
        assert call_kwargs["page"] == 3
        assert call_kwargs["page_size"] == 20
        assert call_kwargs["order_by"] == "-id"

    def test_page_size_limit(self, patch_env):
        with pytest.raises(Exception):
            UptimeCheckTaskQueryResource().request({"bk_biz_id": 2, "page_size": 501})

    def test_filters_passthrough(self, patch_env):
        UptimeCheckTaskQueryResource().request(
            {"bk_biz_id": 2, "group_id": 5, "name": "abc", "protocol": "TCP", "status": "running"}
        )

        query = patch_env.list_tasks.call_args.kwargs["query"]
        assert query == {"group_ids": [5], "name": "abc", "protocol": "TCP", "status": "running"}
        # count 与 list 使用同一份 query，保证分页总数口径一致
        assert patch_env.count_tasks.call_args.kwargs["query"] == query

    def test_target_url_type(self, patch_env):
        patch_env.list_tasks.return_value = [
            make_task(
                config={"period": 60, "url_list": ["http://a.com", "http://b.com", "http://c.com", "http://d.com"]}
            )
        ]

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2})

        target = result["results"][0]["target"]
        assert target == {
            "type": "url",
            "total": 4,
            "preview": ["http://a.com", "http://b.com", "http://c.com"],
        }

    def test_target_ip_type_with_port(self, patch_env):
        patch_env.list_tasks.return_value = [
            make_task(protocol="TCP", config={"period": 60, "port": "80", "ip_list": ["127.0.0.1", "127.0.0.2"]})
        ]

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2})

        target = result["results"][0]["target"]
        assert target == {"type": "ip", "total": 2, "preview": ["[127.0.0.1]:80", "[127.0.0.2]:80"]}

    def test_target_icmp_no_port(self, patch_env):
        patch_env.list_tasks.return_value = [
            make_task(protocol="ICMP", config={"period": 60, "ip_list": ["127.0.0.1"]})
        ]

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2})

        assert result["results"][0]["target"]["preview"] == ["127.0.0.1"]

    def test_target_topo_not_expanded(self, patch_env):
        # 拓扑类任务：total 为节点数，不调 CMDB 展开主机
        patch_env.list_tasks.return_value = [
            make_task(
                protocol="TCP",
                config={
                    "period": 60,
                    "port": "80",
                    "node_list": [{"bk_obj_id": "SET", "bk_inst_id": 1}, {"bk_obj_id": "MODULE", "bk_inst_id": 2}],
                },
            )
        ]

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2})

        target = result["results"][0]["target"]
        assert target == {"type": "topo", "total": 2, "preview": []}

    def test_with_config_returns_config(self, patch_env):
        config = {"period": 60, "url_list": ["http://a.com"], "headers": [{"key": "token"}]}
        patch_env.list_tasks.return_value = [make_task(config=config)]

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2, "with_config": True})

        assert result["results"][0]["config"] == config
        assert "config" in patch_env.list_tasks.call_args.kwargs["fields"]

    def test_default_no_config(self, patch_env):
        patch_env.list_tasks.return_value = [make_task()]

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2})

        assert "config" not in result["results"][0]

    def test_no_target_no_config_skips_config_column(self, patch_env):
        # with_target=false 且 with_config=false 时，config 列不加载
        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2, "with_target": False, "with_config": False})

        assert "config" not in patch_env.list_tasks.call_args.kwargs["fields"]
        assert result["results"] == []

    def test_groups_nodes_light_mapping(self, patch_env):
        patch_env.list_tasks.return_value = [make_task(node_ids=[3], group_ids=[1])]
        patch_env.list_groups.return_value = [SimpleNamespace(id=1, name="核心服务")]
        patch_env.list_nodes.return_value = [SimpleNamespace(id=3, name="上海联通")]

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2})

        item = result["results"][0]
        assert item["groups"] == [{"id": 1, "name": "核心服务"}]
        assert item["nodes"] == [{"id": 3, "name": "上海联通"}]
