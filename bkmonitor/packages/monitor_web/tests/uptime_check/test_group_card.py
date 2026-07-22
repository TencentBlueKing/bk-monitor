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

from monitor_web.uptime_check.resources import UptimeCheckGroupCardResource

BK_BIZ_ID = 2


@pytest.mark.django_db(databases="__all__")
class TestGroupCard:
    """集成测试：UptimeCheckGroupCardResource 走真实 ORM（纯 DB 查询）"""

    def test_empty_biz(self):
        result = UptimeCheckGroupCardResource().request({"bk_biz_id": BK_BIZ_ID})

        assert result == {"count": 0, "results": []}

    def test_card_structure(self, create_task, create_group):
        task1 = create_task(name="HTTP任务1", protocol="HTTP")
        task2 = create_task(name="HTTP任务2", protocol="HTTP")
        task3 = create_task(name="ICMP任务", protocol="ICMP")
        group = create_group(name="核心服务", tasks=[task1, task2, task3])

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": BK_BIZ_ID})

        assert result["count"] == 1
        card = result["results"][0]
        assert card["id"] == group.pk
        assert card["name"] == "核心服务"
        assert card["bk_biz_id"] == BK_BIZ_ID
        assert card["task_num"] == 3
        assert card["protocol_num"] == [{"name": "HTTP", "val": 2}, {"name": "ICMP", "val": 1}]
        # alarm_num 已移到 top_tasks 接口，card 不再返回
        assert "alarm_num" not in card

    def test_pagination(self, create_group):
        for i in range(5):
            create_group(name=f"分组{i}")

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": BK_BIZ_ID, "page": 2, "page_size": 2})

        assert result["count"] == 5
        assert len(result["results"]) == 2

    def test_page_size_limit(self):
        with pytest.raises(Exception):
            UptimeCheckGroupCardResource().request({"bk_biz_id": BK_BIZ_ID, "page_size": 501})

    def test_name_filter(self, create_group):
        create_group(name="核心服务监控")
        create_group(name="边缘服务")

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": BK_BIZ_ID, "name": "核心"})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "核心服务监控"

    def test_deleted_group_excluded(self, create_group):
        create_group(name="正常分组")
        create_group(name="已删除分组", is_deleted=True)

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": BK_BIZ_ID})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "正常分组"

    def test_deleted_task_excluded_from_count(self, create_task, create_group):
        task1 = create_task(name="正常任务")
        task2 = create_task(name="已删除任务", is_deleted=True)
        _group = create_group(name="分组", tasks=[task1, task2])

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": BK_BIZ_ID})

        # 已删除任务不计入 task_num
        assert result["results"][0]["task_num"] == 1

    def test_global_group_included(self, create_group):
        """全局分组 (bk_biz_id=0) 应该被包含在结果中"""
        create_group(name="业务分组", bk_biz_id=BK_BIZ_ID)
        create_group(name="全局分组", bk_biz_id=0)

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": BK_BIZ_ID})

        names = [card["name"] for card in result["results"]]
        assert "业务分组" in names
        assert "全局分组" in names
        assert result["count"] == 2

    def test_biz_isolation(self, create_group):
        create_group(name="业务2分组", bk_biz_id=2)
        create_group(name="业务3分组", bk_biz_id=3)

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": 2})

        assert result["count"] == 1
        assert result["results"][0]["name"] == "业务2分组"

    def test_task_biz_isolation(self, create_task, create_group):
        """分组关联的任务必须属于当前业务才计入 task_num"""
        task_biz2 = create_task(name="业务2任务", bk_biz_id=2)
        task_biz3 = create_task(name="业务3任务", bk_biz_id=3)
        _group = create_group(name="分组", bk_biz_id=2, tasks=[task_biz2, task_biz3])

        result = UptimeCheckGroupCardResource().request({"bk_biz_id": 2})

        # 只有业务2的任务被计入（list_tasks 受 bk_biz_id 限制）
        assert result["results"][0]["task_num"] == 1
