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

import arrow
from django.test import TestCase

from bkm_space.define import Space, SpaceTypeEnum
from apps.exceptions import ValidationError
from apps.log_databus.constants import CollectorSourceEnum
from apps.log_databus.handlers.collector_handler.log import LogCollectorHandler
from apps.log_databus.models import CollectorConfig
from apps.log_databus.serializers import LogCollectorSerializer
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import LogIndexSet, LogIndexSetData, Scenario
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
        self.assertEqual(
            collector_ids, {self.current_collector.collector_config_id, self.related_collector.collector_config_id}
        )

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
        # 项目自定义 ValidationError 会直接抛出（由统一异常处理器转换为错误响应）
        with self.assertRaises(ValidationError) as ctx:
            invalid_serializer.is_valid()
        self.assertIn("collector_source", str(ctx.exception))

    def test_serializer_validates_bk_data_id_condition(self):
        valid_serializer = LogCollectorSerializer(
            data={
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "conditions": [{"key": "bk_data_id", "value": [str(self.current_collector.bk_data_id)]}],
            }
        )
        self.assertTrue(valid_serializer.is_valid())
        self.assertEqual(valid_serializer.validated_data["conditions"][0]["value"], [self.current_collector.bk_data_id])

        invalid_serializer = LogCollectorSerializer(
            data={
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "conditions": [{"key": "bk_data_id", "value": ["invalid"]}],
            }
        )
        with self.assertRaises(ValidationError) as ctx:
            invalid_serializer.is_valid()
        self.assertIn("bk_data_id", str(ctx.exception))

    def test_serializer_accepts_multiple_query_values(self):
        serializer = LogCollectorSerializer(
            data={
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "conditions": [{"key": "query", "value": ["nginx", "1500", "default-es"]}],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["conditions"][0],
            {"key": "query", "value": ["nginx", "1500", "default-es"]},
        )

    def test_serializer_validates_log_collector_ordering(self):
        serializer = LogCollectorSerializer(data={"space_uid": CURRENT_SPACE_UID, "page": PAGE, "pagesize": PAGESIZE})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["ordering"], "-updated_at")

        for ordering in (
            "name",
            "-name",
            "retention",
            "-retention",
            "updated_at",
            "-updated_at",
            "created_at",
            "-created_at",
            "daily_usage",
            "-daily_usage",
            "total_usage",
            "-total_usage",
        ):
            serializer = LogCollectorSerializer(
                data={
                    "space_uid": CURRENT_SPACE_UID,
                    "page": PAGE,
                    "pagesize": PAGESIZE,
                    "ordering": ordering,
                }
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)

        serializer = LogCollectorSerializer(
            data={
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "ordering": "invalid",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("ordering", serializer.errors)

    def test_sort_log_collectors_by_name(self):
        data = [
            {"name": name, "collector_config_id": index}
            for index, name in enumerate(["a", "Z", "0", "A", "z", "9", "_", ""], start=1)
        ]

        ascending = LogCollectorHandler.sort_log_collectors(data, "name")
        descending = LogCollectorHandler.sort_log_collectors(data, "-name")

        self.assertEqual([item["name"] for item in ascending], ["A", "Z", "0", "9", "a", "z", "_", ""])
        self.assertEqual([item["name"] for item in descending], ["Z", "A", "9", "0", "z", "a", "_", ""])

    def test_collector_identity_sort_key_variants(self):
        cases = [
            ({"collector_config_id": 12}, (0, (0, 12))),
            ({"collector_config_id": "12", "index_set_id": 99}, (0, (0, 12))),
            ({"index_set_id": 34}, (1, (0, 34))),
            ({"collector_config_id": "collector-x"}, (0, (1, "collector-x"))),
            ({"index_set_id": "index-x"}, (1, (1, "index-x"))),
            ({}, (1, (1, ""))),
        ]

        for item, expected_key in cases:
            with self.subTest(item=item):
                self.assertEqual(LogCollectorHandler._collector_identity_sort_key(item), expected_key)

    def test_name_character_sort_key_variants(self):
        cases = [
            ("A", (0, 0), (0, 0)),
            ("Z", (0, 25), (0, -25)),
            ("0", (1, 0), (1, 0)),
            ("9", (1, 9), (1, -9)),
            ("a", (2, 0), (2, 0)),
            ("z", (2, 25), (2, -25)),
            ("_", (3, ord("_")), (3, -ord("_"))),
            ("中", (3, ord("中")), (3, -ord("中"))),
        ]

        for character, ascending_key, descending_key in cases:
            with self.subTest(character=character):
                self.assertEqual(
                    LogCollectorHandler._name_character_sort_key(character, descending=False), ascending_key
                )
                self.assertEqual(
                    LogCollectorHandler._name_character_sort_key(character, descending=True), descending_key
                )

    def test_name_sort_key_structure(self):
        item = {"name": "A1a_", "collector_config_id": "12"}

        ascending_key = LogCollectorHandler._name_sort_key(item, descending=False)
        descending_key = LogCollectorHandler._name_sort_key(item, descending=True)

        self.assertEqual(
            ascending_key,
            (
                False,
                ((0, 0), (1, 1), (2, 0), (3, ord("_")), (-1, 0)),
                (0, (0, 12)),
            ),
        )
        self.assertEqual(
            descending_key,
            (
                False,
                ((0, 0), (1, -1), (2, 0), (3, -ord("_")), (4, 0)),
                (0, (0, 12)),
            ),
        )
        self.assertEqual(
            LogCollectorHandler._name_sort_key({"name": "", "index_set_id": 3}, descending=False),
            (True, ((-1, 0),), (1, (0, 3))),
        )

    def test_sort_log_collectors_by_name_prefix_and_stable_identity(self):
        data = [
            {"name": "A", "collector_config_id": 2},
            {"name": "Aa", "collector_config_id": 6},
            {"name": "A0", "collector_config_id": 5},
            {"name": "AA", "collector_config_id": 4},
            {"name": "A", "index_set_id": 1},
            {"name": "A", "collector_config_id": 1},
            {"name": "", "index_set_id": 7},
        ]

        ascending = LogCollectorHandler.sort_log_collectors(data, "name")
        descending = LogCollectorHandler.sort_log_collectors(data, "-name")

        self.assertEqual([item["name"] for item in ascending], ["A", "A", "A", "AA", "A0", "Aa", ""])
        self.assertEqual(
            [item.get("collector_config_id") or item.get("index_set_id") for item in ascending[:3]],
            [1, 2, 1],
        )
        self.assertEqual([item["name"] for item in descending], ["AA", "A0", "Aa", "A", "A", "A", ""])

    def test_field_sort_key_variants(self):
        retention_item = {"retention": "14", "collector_config_id": 2}
        identity_key = (0, (0, 2))

        self.assertEqual(
            LogCollectorHandler._field_sort_key(retention_item, "retention", descending=False),
            (False, 14, identity_key),
        )
        self.assertEqual(
            LogCollectorHandler._field_sort_key(retention_item, "retention", descending=True),
            (False, -14, identity_key),
        )
        self.assertEqual(
            LogCollectorHandler._field_sort_key({"retention": "", "index_set_id": 3}, "retention", descending=True),
            (True, 0, (1, (0, 3))),
        )
        self.assertEqual(
            LogCollectorHandler._field_sort_key(
                {"retention": "forever", "collector_config_id": 4}, "retention", descending=False
            ),
            (True, 0, (0, (0, 4))),
        )

        time_value = "2025-02-01 12:30:45+0800"
        timestamp = arrow.get(time_value[:19], "YYYY-MM-DD HH:mm:ss").int_timestamp
        self.assertEqual(
            LogCollectorHandler._field_sort_key(
                {"updated_at": time_value, "index_set_id": 5}, "updated_at", descending=False
            ),
            (False, timestamp, (1, (0, 5))),
        )
        self.assertEqual(
            LogCollectorHandler._field_sort_key(
                {"updated_at": time_value, "index_set_id": 5}, "updated_at", descending=True
            ),
            (False, -timestamp, (1, (0, 5))),
        )
        self.assertEqual(
            LogCollectorHandler._field_sort_key(
                {"updated_at": "not-a-time", "index_set_id": 6}, "updated_at", descending=False
            ),
            (True, 0, (1, (0, 6))),
        )

        self.assertEqual(
            LogCollectorHandler._field_sort_key(
                {"storage_usage": {"daily_usage": "2048"}, "index_set_id": 7},
                "daily_usage",
                descending=False,
            ),
            (False, 2048, (1, (0, 7))),
        )
        self.assertEqual(
            LogCollectorHandler._field_sort_key(
                {"storage_usage": {"total_usage": 4096}, "index_set_id": 8},
                "total_usage",
                descending=True,
            ),
            (False, -4096, (1, (0, 8))),
        )

    def test_sort_log_collectors_by_retention_with_empty_values_last(self):
        data = [
            {"retention": 30, "collector_config_id": 1},
            {"retention": "", "index_set_id": 2},
            {"retention": 7, "collector_config_id": 3},
            {"retention": 14, "collector_config_id": 4},
        ]

        ascending = LogCollectorHandler.sort_log_collectors(data, "retention")
        descending = LogCollectorHandler.sort_log_collectors(data, "-retention")

        self.assertEqual([item["retention"] for item in ascending], [7, 14, 30, ""])
        self.assertEqual([item["retention"] for item in descending], [30, 14, 7, ""])

    def test_sort_log_collectors_by_created_and_updated_at(self):
        data = [
            {
                "collector_config_id": 1,
                "updated_at": "2025-01-01 00:00:00+0800",
                "created_at": "2025-02-01 00:00:00",
            },
            {
                "collector_config_id": 2,
                "updated_at": "2025-02-01 00:00:00",
                "created_at": "2025-01-01 00:00:00+0800",
            },
            {"index_set_id": 3, "updated_at": "", "created_at": ""},
        ]

        for ordering, expected_ids in (
            ("updated_at", [1, 2, 3]),
            ("-updated_at", [2, 1, 3]),
            ("created_at", [2, 1, 3]),
            ("-created_at", [1, 2, 3]),
        ):
            result = LogCollectorHandler.sort_log_collectors(data, ordering)
            result_ids = [item.get("collector_config_id") or item.get("index_set_id") for item in result]
            self.assertEqual(result_ids, expected_ids)

    def test_sort_log_collectors_by_storage_usage_with_empty_values_last(self):
        data = [
            {"index_set_id": 1, "storage_usage": {"daily_usage": 1024, "total_usage": 10240}},
            {"index_set_id": 2, "storage_usage": {"daily_usage": None, "total_usage": None}},
            {"index_set_id": 3, "storage_usage": {"daily_usage": 0, "total_usage": 0}},
            {
                "collector_config_id": 4,
                "index_set_id": 4,
                "storage_usage": {"daily_usage": "4096", "total_usage": "40960"},
            },
        ]

        for ordering, expected_ids in (
            ("daily_usage", [3, 1, 4, 2]),
            ("-daily_usage", [4, 1, 3, 2]),
            ("total_usage", [3, 1, 4, 2]),
            ("-total_usage", [4, 1, 3, 2]),
        ):
            result = LogCollectorHandler.sort_log_collectors(data, ordering)
            result_ids = [item.get("collector_config_id") or item.get("index_set_id") for item in result]
            self.assertEqual(result_ids, expected_ids)

    def test_fill_storage_usage_info_groups_index_sets_by_space(self):
        current_index_set = LogIndexSet.objects.create(
            index_set_name="current_usage_index_set",
            space_uid=CURRENT_SPACE_UID,
            scenario_id=Scenario.BKDATA,
        )
        related_index_set = LogIndexSet.objects.create(
            index_set_name="related_usage_index_set",
            space_uid=RELATED_SPACE_UID,
            scenario_id=Scenario.BKDATA,
        )
        data = [
            {"collector_config_id": 1, "index_set_id": current_index_set.index_set_id},
            {"index_set_id": related_index_set.index_set_id},
            {"collector_config_id": 3, "index_set_id": ""},
        ]

        def get_storage_usage_info(bk_biz_id, index_set_ids):
            multiplier = 1 if bk_biz_id == CURRENT_BK_BIZ_ID else 2
            return [
                {
                    "index_set_id": str(index_set_id),
                    "daily_count": 10 * multiplier,
                    "total_count": 100 * multiplier,
                    "daily_usage": 1024 * multiplier,
                    "total_usage": 10240 * multiplier,
                }
                for index_set_id in index_set_ids
            ]

        handler = LogCollectorHandler(CURRENT_SPACE_UID)
        with (
            patch(
                "apps.log_databus.handlers.collector_handler.log.space_uid_to_bk_biz_id",
                return_value=RELATED_BK_BIZ_ID,
            ) as mock_space_uid_to_bk_biz_id,
            patch.object(
                IndexSetHandler,
                "get_storage_usage_info",
                side_effect=get_storage_usage_info,
            ) as mock_get_storage_usage_info,
        ):
            result = handler.fill_storage_usage_info(data)

        self.assertEqual(result[0]["storage_usage"]["daily_usage"], 1024)
        self.assertEqual(result[0]["storage_usage"]["total_usage"], 10240)
        self.assertEqual(result[1]["storage_usage"]["daily_usage"], 2048)
        self.assertEqual(result[1]["storage_usage"]["total_usage"], 20480)
        self.assertIsNone(result[2]["storage_usage"]["daily_usage"])
        self.assertIsNone(result[2]["storage_usage"]["total_usage"])
        mock_space_uid_to_bk_biz_id.assert_called_once_with(RELATED_SPACE_UID)
        self.assertEqual(
            {(call.args[0], tuple(call.args[1])) for call in mock_get_storage_usage_info.call_args_list},
            {
                (CURRENT_BK_BIZ_ID, (current_index_set.index_set_id,)),
                (RELATED_BK_BIZ_ID, (related_index_set.index_set_id,)),
            },
        )

    def test_get_log_collectors_fills_usage_before_sorting_and_pagination(self):
        self._setup_related_space_mocks()

        def fill_storage_usage_info(data):
            usage_by_collector_id = {
                self.current_collector.collector_config_id: 1024,
                self.related_collector.collector_config_id: 4096,
            }
            for item in data:
                total_usage = usage_by_collector_id[item["collector_config_id"]]
                item["storage_usage"] = {
                    "daily_count": 1,
                    "total_count": 10,
                    "daily_usage": total_usage // 10,
                    "total_usage": total_usage,
                }
            return data

        with patch.object(
            LogCollectorHandler,
            "fill_storage_usage_info",
            side_effect=fill_storage_usage_info,
        ) as mock_fill_storage_usage_info:
            result = LogCollectorHandler(CURRENT_SPACE_UID).get_log_collectors(
                {
                    "space_uid": CURRENT_SPACE_UID,
                    "page": 1,
                    "pagesize": 1,
                    "conditions": [],
                    "include_related_spaces": True,
                    "ordering": "-total_usage",
                }
            )

        mock_fill_storage_usage_info.assert_called_once()
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["list"][0]["collector_config_id"], self.related_collector.collector_config_id)
        self.assertEqual(result["list"][0]["storage_usage"]["total_usage"], 4096)

    def test_get_log_collectors_does_not_fill_usage_for_other_ordering(self):
        self._setup_related_space_mocks()

        with patch.object(LogCollectorHandler, "fill_storage_usage_info") as mock_fill_storage_usage_info:
            result = LogCollectorHandler(CURRENT_SPACE_UID).get_log_collectors(
                {
                    "space_uid": CURRENT_SPACE_UID,
                    "page": 1,
                    "pagesize": PAGESIZE,
                    "conditions": [],
                    "include_related_spaces": True,
                    "ordering": "-updated_at",
                }
            )

        mock_fill_storage_usage_info.assert_not_called()
        self.assertTrue(result["list"])
        self.assertTrue(all("storage_usage" not in item for item in result["list"]))

    def test_get_log_collectors_sorts_before_pagination(self):
        self._setup_related_space_mocks()
        result = LogCollectorHandler(CURRENT_SPACE_UID).get_log_collectors(
            {
                "space_uid": CURRENT_SPACE_UID,
                "page": 1,
                "pagesize": 1,
                "conditions": [],
                "include_related_spaces": True,
                "ordering": "-name",
            }
        )

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["list"][0]["name"], "related_collector")

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

    @patch.object(LogCollectorHandler, "get_bkdata_cluster_names", return_value={"bkdata_cluster"})
    @patch.object(LogCollectorHandler, "get_metadata_cluster_names", return_value={"metadata_cluster"})
    def test_get_collector_field_enums_uses_collector_list_field_values(
        self, _mock_get_metadata_cluster_names, _mock_get_bkdata_cluster_names
    ):
        index_set = LogIndexSet.objects.create(
            index_set_name="bkdata_index_set",
            space_uid=CURRENT_SPACE_UID,
            scenario_id=Scenario.BKDATA,
        )
        LogIndexSetData.objects.create(index_set_id=index_set.index_set_id, result_table_id="2_bkbase.first")
        LogIndexSetData.objects.create(index_set_id=index_set.index_set_id, result_table_id="2_bkbase.second")

        result = LogCollectorHandler(CURRENT_SPACE_UID).get_collector_field_enums(include_related_spaces=False)

        self.assertEqual(
            result["name"],
            [
                {"key": "bkdata_index_set", "value": "bkdata_index_set"},
                {"key": "current_collector", "value": "current_collector"},
            ],
        )
        self.assertEqual(result["table_id"], [{"key": "current_collector", "value": "current_collector"}])
        self.assertEqual(result["bk_data_id"], [{"key": 1500586, "value": 1500586}])
        self.assertEqual(
            result["bk_data_name"],
            [
                {"key": "2_bkbase.second,2_bkbase.first", "value": "2_bkbase.second,2_bkbase.first"},
                {"key": "2_bklog_current_collector", "value": "2_bklog_current_collector"},
            ],
        )
        self.assertEqual(
            result["storage_display_name"],
            [
                {"key": "bkdata_cluster", "value": "bkdata_cluster"},
                {"key": "metadata_cluster", "value": "metadata_cluster"},
            ],
        )

    def test_get_log_collectors_filters_by_table_id_bk_data_id_and_bk_data_name(self):
        handler = LogCollectorHandler(CURRENT_SPACE_UID)
        base_data = {
            "space_uid": CURRENT_SPACE_UID,
            "page": PAGE,
            "pagesize": PAGESIZE,
        }

        for key, value in [
            ("table_id", "current_collector"),
            ("bk_data_id", self.current_collector.bk_data_id),
            ("bk_data_name", "2_BKLOG_CURRENT_COLLECTOR"),
            ("bk_data_name", "CURRENT_COLLECTOR"),
        ]:
            result = handler.get_log_collectors(
                {
                    **base_data,
                    "conditions": [{"key": key, "value": [value]}],
                }
            )
            collectors = self._collectors_from_result(result)
            self.assertEqual([item["collector_config_id"] for item in collectors], [self.current_collector.pk])

        for key, value in [
            ("table_id", "2_bklog_current_collector"),
            ("bk_data_name", "missing_collector"),
        ]:
            result = handler.get_log_collectors(
                {
                    **base_data,
                    "conditions": [{"key": key, "value": [value]}],
                }
            )
            self.assertEqual(self._collectors_from_result(result), [])

    def test_get_log_collectors_filters_storage_display_name_by_partial_value(self):
        def add_cluster_info(data):
            for item in data:
                item["storage_display_name"] = (
                    "Related ES Cluster"
                    if item["collector_config_id"] == self.related_collector.collector_config_id
                    else "Current ES Cluster"
                )
            return data

        self._setup_related_space_mocks()
        with patch(
            "apps.log_databus.handlers.collector_handler.log.CollectorHandler.add_cluster_info",
            side_effect=add_cluster_info,
        ):
            result = LogCollectorHandler(CURRENT_SPACE_UID).get_log_collectors(
                {
                    "space_uid": CURRENT_SPACE_UID,
                    "page": PAGE,
                    "pagesize": PAGESIZE,
                    "conditions": [{"key": "storage_display_name", "value": ["RELATED es"]}],
                    "include_related_spaces": True,
                }
            )

        collectors = self._collectors_from_result(result)
        self.assertEqual([item["collector_config_id"] for item in collectors], [self.related_collector.pk])

    def test_get_log_collectors_filters_index_set_by_exposed_bk_data_name(self):
        index_set = LogIndexSet.objects.create(
            index_set_name="bkdata_index_set",
            space_uid=CURRENT_SPACE_UID,
            scenario_id=Scenario.BKDATA,
        )
        LogIndexSetData.objects.create(index_set_id=index_set.index_set_id, result_table_id="2_bkbase.first")
        LogIndexSetData.objects.create(index_set_id=index_set.index_set_id, result_table_id="2_bkbase.second")
        other_index_set = LogIndexSet.objects.create(
            index_set_name="other_bkdata_index_set",
            space_uid=CURRENT_SPACE_UID,
            scenario_id=Scenario.BKDATA,
        )
        LogIndexSetData.objects.create(
            index_set_id=other_index_set.index_set_id,
            result_table_id="2_bkbase.other",
        )

        result = LogCollectorHandler(CURRENT_SPACE_UID).get_log_collectors(
            {
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "conditions": [
                    {"key": "bk_data_name", "value": ["2_bkbase.second,2_bkbase.first"]},
                ],
            }
        )

        matched_item = next(item for item in result["list"] if item["index_set_id"] == index_set.index_set_id)
        self.assertEqual(matched_item["bk_data_name"], "2_bkbase.second,2_bkbase.first")
        self.assertNotIn(other_index_set.index_set_id, [item["index_set_id"] for item in result["list"]])

    def test_filter_by_queries_matches_all_searchable_fields_and_multiple_queries(self):
        data = [
            {
                "collector_config_id": 1,
                "name": "Nginx Access",
                "bk_data_id": 1500586,
                "table_id": "nginx_access",
                "bk_data_name": "2_bklog_nginx_access",
                "storage_display_name": "Default ES",
            },
            {
                "index_set_id": 2,
                "name": "BKBase Index",
                "bk_data_id": "",
                "table_id": "",
                "bk_data_name": "2_bkbase.pipeline_log",
                "storage_display_name": "BKData Cluster",
            },
        ]

        cases = (
            (["nginx"], [1]),
            (["0058"], [1]),
            (["ACCESS"], [1]),
            (["bklog_nginx"], [1]),
            (["default es"], [1]),
            (["nginx", "0058", "default es"], [1]),
            (["bkbase", "cluster"], [2]),
            (["pipeline", "nginx"], []),
            (["missing"], []),
            (["", "  "], [1, 2]),
        )
        for queries, expected_ids in cases:
            with self.subTest(queries=queries):
                result = LogCollectorHandler.filter_by_queries(data, queries)
                result_ids = [item.get("collector_config_id") or item.get("index_set_id") for item in result]
                self.assertEqual(result_ids, expected_ids)

    def test_get_log_collectors_searches_collector_with_query_condition(self):
        result = LogCollectorHandler(CURRENT_SPACE_UID).get_log_collectors(
            {
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "conditions": [{"key": "query", "value": ["CURRENT_COLLECTOR"]}],
            }
        )

        collectors = self._collectors_from_result(result)
        self.assertEqual([item["collector_config_id"] for item in collectors], [self.current_collector.pk])

    def test_get_log_collectors_searches_storage_display_name_with_query_condition(self):
        def add_cluster_info(data):
            for item in data:
                item["storage_display_name"] = (
                    "Related ES Cluster"
                    if item["collector_config_id"] == self.related_collector.collector_config_id
                    else "Current ES Cluster"
                )
            return data

        self._setup_related_space_mocks()
        with patch(
            "apps.log_databus.handlers.collector_handler.log.CollectorHandler.add_cluster_info",
            side_effect=add_cluster_info,
        ):
            result = LogCollectorHandler(CURRENT_SPACE_UID).get_log_collectors(
                {
                    "space_uid": CURRENT_SPACE_UID,
                    "page": PAGE,
                    "pagesize": PAGESIZE,
                    "conditions": [{"key": "query", "value": ["related es"]}],
                    "include_related_spaces": True,
                }
            )

        collectors = self._collectors_from_result(result)
        self.assertEqual([item["collector_config_id"] for item in collectors], [self.related_collector.pk])

    def test_get_log_collectors_searches_index_set_with_multiple_query_conditions(self):
        index_set = LogIndexSet.objects.create(
            index_set_name="bkdata_index_set",
            space_uid=CURRENT_SPACE_UID,
            scenario_id=Scenario.BKDATA,
        )
        LogIndexSetData.objects.create(index_set_id=index_set.index_set_id, result_table_id="2_bkbase.first")
        LogIndexSetData.objects.create(index_set_id=index_set.index_set_id, result_table_id="2_bkbase.second")

        result = LogCollectorHandler(CURRENT_SPACE_UID).get_log_collectors(
            {
                "space_uid": CURRENT_SPACE_UID,
                "page": PAGE,
                "pagesize": PAGESIZE,
                "conditions": [{"key": "query", "value": ["SECOND", "2_BKBASE.FI"]}],
            }
        )

        matched_item = next(item for item in result["list"] if item["index_set_id"] == index_set.index_set_id)
        self.assertEqual(matched_item["bk_data_name"], "2_bkbase.second,2_bkbase.first")
