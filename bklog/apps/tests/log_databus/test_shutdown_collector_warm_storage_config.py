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

from django.db import connection
from django.test import TestCase

from apps.log_databus.models import CollectorConfig
from apps.log_databus.tasks.collector import shutdown_collector_warm_storage_config


# 测试用的集群 ID
TARGET_CLUSTER_ID = 1001
OTHER_CLUSTER_ID = 2002


class TestShutdownCollectorWarmStorageConfig(TestCase):
    """
    使用真实数据库测试 shutdown_collector_warm_storage_config 函数。

    只 Mock 外部 API（TransferApi.modify_result_table、CollectorHandler.bulk_cluster_infos），
    使用真实 CollectorConfig 记录验证 SQL 优化效果和业务逻辑。

    验证点：
    1. 只执行 1 次数据库查询（assertNumQueries(1)）
    2. SQL 只 SELECT table_id, bk_biz_id 两列（字段裁剪）
    3. SQL WHERE 条件包含 is_deleted=False（软删除过滤）
    4. 集群 ID 过滤逻辑
    5. 错误处理（单个失败不影响其他）
    """

    def setUp(self):
        """每个测试用例前 Mock 外部 API。"""
        self.bulk_cluster_infos_patcher = patch(
            "apps.log_databus.tasks.collector.CollectorHandler.bulk_cluster_infos"
        )
        self.mock_bulk_cluster_infos = self.bulk_cluster_infos_patcher.start()
        self.mock_bulk_cluster_infos.return_value = {}

        self.modify_result_table_patcher = patch(
            "apps.log_databus.tasks.collector.TransferApi.modify_result_table"
        )
        self.mock_modify_result_table = self.modify_result_table_patcher.start()
        self.mock_modify_result_table.return_value = {"result": True}

    def tearDown(self):
        """清理 Mock。"""
        self.bulk_cluster_infos_patcher.stop()
        self.modify_result_table_patcher.stop()

    def _create_collector(self, table_id, bk_biz_id=100):
        """
        创建测试采集项。

        :param table_id: 结果表 ID，可为 None 或空字符串
        :param bk_biz_id: 业务 ID
        :return: CollectorConfig 实例
        """
        return CollectorConfig.objects.create(
            collector_config_name=f"test_collector_{table_id or 'none'}_{bk_biz_id}",
            collector_scenario_id="host",
            category_id="host",
            bk_biz_id=bk_biz_id,
            table_id=table_id,
        )

    def _execute_and_get_sql(self, cluster_id):
        """
        执行函数并返回其产生的 SQL 语句。

        通过记录执行前的查询数量，精确定位目标查询，避免取到 setUp 或
        _create_collector 产生的无关 SQL。

        :param cluster_id: 集群 ID
        :return: 函数执行产生的 SQL 语句
        """
        query_count_before = len(connection.queries)
        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(cluster_id)
        return connection.queries[query_count_before]["sql"]

    # ==================== SQL 优化验证测试 ====================

    def test_sql_single_query_with_field_projection(self):
        """
        验证只执行 1 次查询，且 SQL 只 SELECT table_id, bk_biz_id。

        核心验收标准：
        - 查询次数从 2 降为 1
        - 只 SELECT 必要的 2 列，避免查询 params、yaml_config 等大字段
        """
        self._create_collector(table_id="1_bklog.test_index", bk_biz_id=100)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.test_index": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        sql = self._execute_and_get_sql(TARGET_CLUSTER_ID)

        self.assertIn("table_id", sql)
        self.assertIn("bk_biz_id", sql)
        self.assertNotIn("params", sql)
        self.assertNotIn("description", sql)
        self.assertNotIn("yaml_config", sql)

    def test_sql_soft_delete_filter_applied(self):
        """
        验证 SQL WHERE 条件包含 is_deleted=False（软删除过滤）。

        CollectorConfig 继承链：CollectorConfig -> CollectorBase -> SoftDeleteModel，
        查询时应自动添加 is_deleted=False 条件。
        """
        self._create_collector(table_id="1_bklog.test_index", bk_biz_id=100)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.test_index": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        sql = self._execute_and_get_sql(TARGET_CLUSTER_ID)

        self.assertIn("is_deleted", sql)

    # ==================== 数据库过滤逻辑测试 ====================

    def test_exclude_null_table_id(self):
        """
        验证 NULL 值的 table_id 被数据库层过滤。
        """
        self._create_collector(table_id=None, bk_biz_id=100)
        self._create_collector(table_id="1_bklog.valid_index", bk_biz_id=200)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.valid_index": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        self.mock_bulk_cluster_infos.assert_called_once_with(
            result_table_list=["1_bklog.valid_index"]
        )

    def test_exclude_empty_string_table_id(self):
        """
        验证空字符串的 table_id 被数据库层过滤。
        """
        self._create_collector(table_id="", bk_biz_id=100)
        self._create_collector(table_id="1_bklog.valid_index", bk_biz_id=200)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.valid_index": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        self.mock_bulk_cluster_infos.assert_called_once_with(
            result_table_list=["1_bklog.valid_index"]
        )

    def test_exclude_mixed_null_empty_and_valid(self):
        """
        验证同时存在 NULL、空字符串和有效 table_id 时的过滤行为。
        """
        self._create_collector(table_id=None, bk_biz_id=100)
        self._create_collector(table_id="", bk_biz_id=200)
        self._create_collector(table_id="1_bklog.valid_1", bk_biz_id=300)
        self._create_collector(table_id="2_bklog.valid_2", bk_biz_id=400)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.valid_1": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
            "2_bklog.valid_2": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        expected_tables = sorted(["1_bklog.valid_1", "2_bklog.valid_2"])
        actual_call = self.mock_bulk_cluster_infos.call_args
        actual_tables = sorted(actual_call.kwargs["result_table_list"])
        self.assertEqual(actual_tables, expected_tables)

    def test_empty_collectors_early_return(self):
        """
        验证当没有有效采集项时，函数提前返回，只执行 1 次查询。
        """
        self._create_collector(table_id=None, bk_biz_id=100)
        self._create_collector(table_id="", bk_biz_id=200)

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        self.mock_bulk_cluster_infos.assert_not_called()
        self.mock_modify_result_table.assert_not_called()

    # ==================== 业务逻辑测试 ====================

    def test_cluster_id_filter(self):
        """
        验证集群 ID 过滤逻辑：只有匹配目标 cluster_id 的采集项才会调用 modify_result_table。
        """
        self._create_collector(table_id="1_bklog.target_index", bk_biz_id=100)
        self._create_collector(table_id="2_bklog.other_index", bk_biz_id=200)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.target_index": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
            "2_bklog.other_index": {
                "cluster_config": {"cluster_id": OTHER_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        self.assertEqual(self.mock_modify_result_table.call_count, 1)
        self.mock_modify_result_table.assert_called_once_with(
            {
                "table_id": "1_bklog.target_index",
                "default_storage": "elasticsearch",
                "default_storage_config": {"warm_phase_days": 0},
                "bk_biz_id": 100,
            }
        )

    def test_no_matching_cluster_no_modify(self):
        """
        验证当没有匹配目标集群的采集项时，不调用 modify_result_table。
        """
        self._create_collector(table_id="1_bklog.other_cluster_index", bk_biz_id=100)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.other_cluster_index": {
                "cluster_config": {"cluster_id": OTHER_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        self.mock_modify_result_table.assert_not_called()

    def test_cluster_info_not_found(self):
        """
        验证当 cluster_info 不存在时，跳过该采集项。
        """
        self._create_collector(table_id="1_bklog.no_cluster_index", bk_biz_id=100)

        # bulk_cluster_infos 返回空字典，模拟找不到 cluster_info 的情况
        self.mock_bulk_cluster_infos.return_value = {}

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        self.mock_modify_result_table.assert_not_called()

    def test_modify_result_table_error_handled(self):
        """
        验证单个 modify_result_table 调用失败时不影响其他采集项的处理。
        """
        self._create_collector(table_id="1_bklog.index_1", bk_biz_id=100)
        self._create_collector(table_id="2_bklog.index_2", bk_biz_id=200)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.index_1": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
            "2_bklog.index_2": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        # 设置 modify_result_table 第一个调用失败，第二个成功
        self.mock_modify_result_table.side_effect = [
            Exception("API error"),
            {"result": True},
        ]

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        # 验证仍然尝试处理所有匹配的采集项
        self.assertEqual(self.mock_modify_result_table.call_count, 2)

    def test_multiple_biz_ids(self):
        """
        验证不同业务 ID 的采集项都能正确处理。
        """
        self._create_collector(table_id="1_bklog.biz1_index", bk_biz_id=100)
        self._create_collector(table_id="2_bklog.biz2_index", bk_biz_id=200)
        self._create_collector(table_id="3_bklog.biz3_index", bk_biz_id=300)

        self.mock_bulk_cluster_infos.return_value = {
            "1_bklog.biz1_index": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
            "2_bklog.biz2_index": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
            "3_bklog.biz3_index": {
                "cluster_config": {"cluster_id": TARGET_CLUSTER_ID},
                "storage_config": {"retention": 7},
            },
        }

        with self.assertNumQueries(1):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

        self.assertEqual(self.mock_modify_result_table.call_count, 3)
        calls_biz_ids = [call[0][0]["bk_biz_id"] for call in self.mock_modify_result_table.call_args_list]
        self.assertIn(100, calls_biz_ids)
        self.assertIn(200, calls_biz_ids)
        self.assertIn(300, calls_biz_ids)
