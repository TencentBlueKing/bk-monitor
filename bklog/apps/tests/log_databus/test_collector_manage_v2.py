"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from unittest.mock import patch

from django.test import TestCase

from bkm_space.define import Space, SpaceTypeEnum
from apps.log_databus.constants import CollectorSourceEnum
from apps.log_databus.handlers.collector_handler.log import LogCollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.log_databus.serializers import LogCollectorSerializer
from apps.utils.local import set_local_param

# 当前空间为 bkcc 业务空间（"大"的一方）
CURRENT_SPACE_UID = "bkcc__2"
CURRENT_BK_BIZ_ID = 2
CURRENT_SPACE_NAME = "蓝鲸业务"

# 关联空间为 bkci 空间（"小"的一方，bkcc 业务可以单向关联 bkci）
RELATED_SPACE_UID = "bkci__1001"
RELATED_SPACE_ID = 1001
RELATED_BK_BIZ_ID = -RELATED_SPACE_ID
RELATED_SPACE_NAME = "蓝盾流水线"

PAGE = 1
PAGESIZE = 10


def _make_space(space_uid, space_name, bk_biz_id, space_id, space_type_id):
    """构造一个 bkm_space.define.Space 对象，用于 mock 空间查询接口。"""
    return Space(
        id=space_id if space_type_id == SpaceTypeEnum.BKCC.value else -bk_biz_id,
        space_type_id=space_type_id,
        space_id=str(space_id),
        space_name=space_name,
        status="normal",
        space_code=str(space_id),
        space_uid=space_uid,
        type_name="",
        bk_biz_id=bk_biz_id,
        extend={},
    )


class TestLogCollectorHandlerRelatedSpaces(TestCase):
    """
    测试 LogCollectorHandler 中 include_related_spaces / collector_source 相关的新行为。

    当前空间（bkcc 业务）可以单向关联 bkci 空间（bkci 不能反向关联 bkcc）。
    所有对外部接口的调用均在此处 mock，以便在没有真实接口的 CI 环境下运行。
    """

    def setUp(self):
        super().setUp()
        set_local_param("time_zone", "Asia/Shanghai")

        # 构造当前空间（bkcc）与关联空间（bkci）各自的采集项
        self.current_collector = CollectorConfig.objects.create(
            collector_config_id=1,
            collector_config_name="current_collector",
            collector_scenario_id="row",
            bk_biz_id=CURRENT_BK_BIZ_ID,
            category_id="os",
            target_object_type="HOST",
            target_node_type="TOPO",
            target_nodes=[{"bk_inst_id": 52, "bk_obj_id": "module"}],
            target_subscription_diff={},
            description="current",
            is_active=True,
            bk_data_id=1500586,
            table_id="2_bklog.current_collector",
            subscription_id=2103,
            task_id_list=["1331697"],
        )
        self.related_collector = CollectorConfig.objects.create(
            collector_config_id=2,
            collector_config_name="related_collector",
            collector_scenario_id="row",
            bk_biz_id=RELATED_BK_BIZ_ID,
            category_id="os",
            target_object_type="HOST",
            target_node_type="TOPO",
            target_nodes=[{"bk_inst_id": 53, "bk_obj_id": "module"}],
            target_subscription_diff={},
            description="related",
            is_active=True,
            bk_data_id=1500587,
            table_id="1001_bklog.related_collector",
            subscription_id=2104,
            task_id_list=["1331698"],
        )

        # mock 关联空间列表查询（IndexSetHandler.get_all_related_space_uids）
        self.mock_get_all_related = self._start_patch(
            "apps.log_databus.handlers.collector_handler.log.IndexSetHandler.get_all_related_space_uids"
        )
        # mock 空间详情查询（space_uid_to_bk_biz_id 内部使用 bkm_space.api.SpaceApi.get_space_detail）
        self.mock_get_space_detail = self._start_patch("bkm_space.api.SpaceApi.get_space_detail")
        # mock 批量空间详情查询（bk_biz_id_to_space_detail_map 使用）
        self.mock_batch_get_space_detail = self._start_patch(
            "apps.log_databus.handlers.collector_handler.log.SpaceApi.batch_get_space_detail"
        )
        # mock 采集项信息补充接口（集群信息、标签信息、索引集列表后置处理）
        self._start_patch(
            "apps.log_databus.handlers.collector_handler.log.CollectorHandler.add_cluster_info",
            lambda data: data,
        )
        self._start_patch(
            "apps.log_databus.handlers.collector_handler.log.CollectorHandler.add_tags_info",
            lambda data: data,
        )
        self._start_patch(
            "apps.log_databus.handlers.collector_handler.log.IndexSetHandler.post_list",
            lambda data: data,
        )

    def _start_patch(self, target, new=None):
        patcher = patch(target, new=new) if new is not None else patch(target)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _setup_related_space_mocks(self):
        """为 include_related_spaces=True 的场景准备空间查询相关的 mock 数据。"""
        self.mock_get_all_related.return_value = [CURRENT_SPACE_UID, RELATED_SPACE_UID]
        self.mock_get_space_detail.return_value = _make_space(
            RELATED_SPACE_UID, RELATED_SPACE_NAME, RELATED_BK_BIZ_ID, RELATED_SPACE_ID, SpaceTypeEnum.BKCI.value
        )
        self.mock_batch_get_space_detail.return_value = {
            CURRENT_SPACE_UID: _make_space(
                CURRENT_SPACE_UID, CURRENT_SPACE_NAME, CURRENT_BK_BIZ_ID, CURRENT_BK_BIZ_ID, SpaceTypeEnum.BKCC.value
            ),
            RELATED_SPACE_UID: _make_space(
                RELATED_SPACE_UID, RELATED_SPACE_NAME, RELATED_BK_BIZ_ID, RELATED_SPACE_ID, SpaceTypeEnum.BKCI.value
            ),
        }

    def _run_get_log_collectors(self, include_related_spaces=False, collector_source=None):
        """构造请求参数并调用 get_log_collectors。"""
        conditions = []
        if collector_source:
            conditions.append({"key": "collector_source", "value": collector_source})
        handler = LogCollectorHandler(CURRENT_SPACE_UID)
        data = {
            "space_uid": CURRENT_SPACE_UID,
            "page": PAGE,
            "pagesize": PAGESIZE,
            "conditions": conditions,
            "include_related_spaces": include_related_spaces,
        }
        return handler.get_log_collectors(data)

    @staticmethod
    def _collectors_from_result(result):
        """从返回结果中筛选出采集项（collector_config_id 非空）的记录。"""
        return [item for item in result["list"] if item.get("collector_config_id")]

    def test_default_include_both_current_and_related_space(self):
        """默认（include_related_spaces=True 且不传 collector_source）应返回当前空间和关联空间的采集项。"""
        self._setup_related_space_mocks()

        result = self._run_get_log_collectors(include_related_spaces=True)

        collectors = self._collectors_from_result(result)
        self.assertEqual(len(collectors), 2)
        collector_ids = {item["collector_config_id"] for item in collectors}
        self.assertEqual(collector_ids, {self.current_collector.collector_config_id, self.related_collector.collector_config_id})

    def test_returned_item_has_related_space_fields(self):
        """返回项应包含 bk_biz_id / space_uid / space_name / is_related_space 字段，且值正确。"""
        self._setup_related_space_mocks()

        result = self._run_get_log_collectors(include_related_spaces=True)
        collectors = {item["collector_config_id"]: item for item in self._collectors_from_result(result)}

        current = collectors[self.current_collector.collector_config_id]
        self.assertEqual(current["bk_biz_id"], CURRENT_BK_BIZ_ID)
        self.assertEqual(current["space_uid"], CURRENT_SPACE_UID)
        self.assertEqual(current["space_name"], CURRENT_SPACE_NAME)
        self.assertFalse(current["is_related_space"])

        related = collectors[self.related_collector.collector_config_id]
        self.assertEqual(related["bk_biz_id"], RELATED_BK_BIZ_ID)
        self.assertEqual(related["space_uid"], RELATED_SPACE_UID)
        self.assertEqual(related["space_name"], RELATED_SPACE_NAME)
        self.assertTrue(related["is_related_space"])

    def test_collector_source_current_space_only(self):
        """collector_source=[current_space] 时只返回当前空间的采集项。"""
        self._setup_related_space_mocks()

        result = self._run_get_log_collectors(
            include_related_spaces=True, collector_source=[CollectorSourceEnum.CURRENT_SPACE.value]
        )

        collectors = self._collectors_from_result(result)
        self.assertEqual(len(collectors), 1)
        self.assertEqual(collectors[0]["collector_config_id"], self.current_collector.collector_config_id)
        self.assertFalse(collectors[0]["is_related_space"])

    def test_collector_source_related_space_only(self):
        """collector_source=[related_space] 时只返回关联空间的采集项。"""
        self._setup_related_space_mocks()

        result = self._run_get_log_collectors(
            include_related_spaces=True, collector_source=[CollectorSourceEnum.RELATED_SPACE.value]
        )

        collectors = self._collectors_from_result(result)
        self.assertEqual(len(collectors), 1)
        self.assertEqual(collectors[0]["collector_config_id"], self.related_collector.collector_config_id)
        self.assertTrue(collectors[0]["is_related_space"])

    def test_collector_source_both_current_and_related(self):
        """collector_source 同时包含 current_space 与 related_space 时返回两个空间的采集项。"""
        self._setup_related_space_mocks()

        result = self._run_get_log_collectors(
            include_related_spaces=True,
            collector_source=[CollectorSourceEnum.CURRENT_SPACE.value, CollectorSourceEnum.RELATED_SPACE.value],
        )

        collectors = self._collectors_from_result(result)
        self.assertEqual(len(collectors), 2)

    def test_include_related_spaces_false_ignores_collector_source(self):
        """
        组合边界：当 include_related_spaces=False 时，collector_source 应被忽略，
        仅返回当前空间的采集项，且返回项中不包含关联空间相关字段。
        """
        # 即便数据上包含关联空间，因 include_related_spaces=False，不会查询关联空间
        self.mock_get_all_related.return_value = [CURRENT_SPACE_UID, RELATED_SPACE_UID]

        result = self._run_get_log_collectors(
            include_related_spaces=False, collector_source=[CollectorSourceEnum.RELATED_SPACE.value]
        )

        collectors = self._collectors_from_result(result)
        self.assertEqual(len(collectors), 1)
        self.assertEqual(collectors[0]["collector_config_id"], self.current_collector.collector_config_id)
        # 未开启 include_related_spaces，返回项不应包含关联空间字段
        self.assertNotIn("is_related_space", collectors[0])
        self.assertNotIn("space_uid", collectors[0])

    def test_invalid_collector_source_value_returns_empty(self):
        """
        collector_source 传入非法来源值时，即使 include_related_spaces=True，
        也不会匹配任何来源，因此不返回任何采集项。
        """
        self._setup_related_space_mocks()

        result = self._run_get_log_collectors(include_related_spaces=True, collector_source=["invalid_source"])

        collectors = self._collectors_from_result(result)
        self.assertEqual(len(collectors), 0)

    def test_serializer_rejects_invalid_collector_source(self):
        """采集项来源(collector_source)非法时，序列化校验应失败。"""
        valid_serializer = LogCollectorSerializer(
            data={
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "conditions": [{"key": "collector_source", "value": [CollectorSourceEnum.CURRENT_SPACE.value]}],
            }
        )
        self.assertTrue(valid_serializer.is_valid())

        invalid_serializer = LogCollectorSerializer(
            data={
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "conditions": [{"key": "collector_source", "value": ["invalid_source"]}],
            }
        )
        self.assertFalse(invalid_serializer.is_valid())

    def test_get_query_ids_by_collector_source_logic(self):
        """直接验证 get_query_ids_by_collector_source 的查询 id 组合逻辑。"""
        self.mock_get_all_related.return_value = [CURRENT_SPACE_UID, RELATED_SPACE_UID]
        self.mock_get_space_detail.return_value = _make_space(
            RELATED_SPACE_UID, RELATED_SPACE_NAME, RELATED_BK_BIZ_ID, RELATED_SPACE_ID, SpaceTypeEnum.BKCI.value
        )

        handler = LogCollectorHandler(CURRENT_SPACE_UID)

        # 不传 collector_source -> 返回当前空间 + 关联空间的全部 bk_biz_id
        self.assertEqual(
            set(handler.get_query_ids_by_collector_source([], is_bk_biz_id=True)),
            {CURRENT_BK_BIZ_ID, RELATED_BK_BIZ_ID},
        )

        # 仅当前空间
        self.assertEqual(
            handler.get_query_ids_by_collector_source([CollectorSourceEnum.CURRENT_SPACE.value], is_bk_biz_id=True),
            [CURRENT_BK_BIZ_ID],
        )

        # 仅关联空间
        self.assertEqual(
            handler.get_query_ids_by_collector_source([CollectorSourceEnum.RELATED_SPACE.value], is_bk_biz_id=True),
            [RELATED_BK_BIZ_ID],
        )

        # 非法来源值 -> 空集
        self.assertEqual(handler.get_query_ids_by_collector_source(["invalid_source"], is_bk_biz_id=True), [])

        # space_uid 维度同样适用
        self.assertEqual(
            handler.get_query_ids_by_collector_source([CollectorSourceEnum.CURRENT_SPACE.value]),
            [CURRENT_SPACE_UID],
        )
        self.assertEqual(
            handler.get_query_ids_by_collector_source([CollectorSourceEnum.RELATED_SPACE.value]),
            [RELATED_SPACE_UID],
        )
