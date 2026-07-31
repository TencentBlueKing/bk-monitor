"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from monitor_web.uptime_check.resources import UptimeCheckTaskQueryResource

BK_BIZ_ID = 2


@pytest.mark.django_db(databases="__all__")
class TestTaskQuery:
    """集成测试：UptimeCheckTaskQueryResource 走真实 ORM"""

    def test_response_structure(self, create_task):
        task = create_task(name="HTTP任务", protocol="HTTP", status="running")

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "page": 1, "page_size": 10})

        assert result["count"] == 1
        assert "has_node" in result
        item = result["results"][0]
        assert item["id"] == task.pk
        assert item["name"] == "HTTP任务"
        assert item["protocol"] == "HTTP"
        assert item["status"] == "running"
        # 指标字段不在列表接口返回
        assert "available" not in item
        assert "task_duration" not in item

    def test_has_node_false_when_no_nodes(self, create_task):
        create_task()

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID})

        assert result["has_node"] is False

    def test_has_node_true_when_node_exists(self, create_task, create_node):
        create_task()
        create_node(name="节点1", is_common=True)

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID})

        assert result["has_node"] is True

    def test_pagination(self, create_task):
        for i in range(5):
            create_task(name=f"任务{i}")

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "page": 2, "page_size": 2})

        assert result["count"] == 5
        assert len(result["results"]) == 2

    def test_page_size_limit(self):
        with pytest.raises(Exception):
            UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "page_size": 501})

    def test_filter_by_protocol(self, create_task):
        create_task(name="HTTP任务", protocol="HTTP")
        create_task(name="TCP任务", protocol="TCP")

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "protocol": "TCP"})

        assert result["count"] == 1
        assert result["results"][0]["protocol"] == "TCP"

    def test_filter_by_status(self, create_task):
        create_task(name="运行中", status="running")
        create_task(name="已停用", status="stoped")

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "status": "running"})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "运行中"

    def test_filter_by_name(self, create_task):
        create_task(name="核心服务监控")
        create_task(name="边缘服务")

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "name": "核心"})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "核心服务监控"

    def test_filter_by_group_id(self, create_task, create_group):
        task1 = create_task(name="组内任务")
        _task2 = create_task(name="组外任务")
        group = create_group(name="分组A", tasks=[task1])

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "group_id": group.pk})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "组内任务"

    def test_filter_by_node_id(self, create_task, create_node):
        from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskNodeRelation

        task1 = create_task(name="有节点")
        _task2 = create_task(name="无节点")
        node = create_node(name="节点1")
        UptimeCheckTaskNodeRelation.objects.create(task=task1, node=node)

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "node_id": node.pk})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "有节点"

    def test_target_url_type(self, create_task):
        create_task(
            protocol="HTTP",
            config={"period": 60, "url_list": ["http://a.com", "http://b.com", "http://c.com", "http://d.com"]},
        )

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID})

        target = result["results"][0]["target"]
        assert target["type"] == "url"
        assert target["total"] == 4
        assert len(target["preview"]) == 3

    def test_target_ip_type_with_port(self, create_task):
        create_task(protocol="TCP", config={"period": 60, "port": "80", "ip_list": ["127.0.0.1", "127.0.0.2"]})

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID})

        target = result["results"][0]["target"]
        assert target == {"type": "ip", "total": 2, "preview": ["[127.0.0.1]:80", "[127.0.0.2]:80"]}

    def test_with_config(self, create_task):
        config = {"period": 60, "url_list": ["http://a.com"], "headers": [{"key": "token"}]}
        create_task(config=config)

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID, "with_config": True})

        assert result["results"][0]["config"] == config

    def test_default_no_config(self, create_task):
        create_task()

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID})

        assert "config" not in result["results"][0]

    def test_groups_and_nodes_mapping(self, create_task, create_group, create_node):
        from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskNodeRelation

        task = create_task(name="关联任务")
        group = create_group(name="核心服务", tasks=[task])
        node = create_node(name="上海联通")
        UptimeCheckTaskNodeRelation.objects.create(task=task, node=node)

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID})

        item = result["results"][0]
        assert item["groups"] == [{"id": group.pk, "name": "核心服务"}]
        assert item["nodes"] == [{"id": node.pk, "name": "上海联通"}]

    def test_deleted_tasks_excluded(self, create_task):
        create_task(name="正常任务")
        create_task(name="已删除", is_deleted=True)

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": BK_BIZ_ID})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "正常任务"

    def test_biz_isolation(self, create_task):
        create_task(name="业务2任务", bk_biz_id=2)
        create_task(name="业务3任务", bk_biz_id=3)

        result = UptimeCheckTaskQueryResource().request({"bk_biz_id": 2})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "业务2任务"
