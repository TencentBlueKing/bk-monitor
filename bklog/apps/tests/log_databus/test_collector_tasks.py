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

from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.log_databus.tasks.collector import shutdown_collector_warm_storage_config


# 测试用的集群 ID
TARGET_CLUSTER_ID = 1001
OTHER_CLUSTER_ID = 2002

# Mock 的采集项数据（模拟 CollectorConfig 表中 table_id 非空的记录）
MOCK_COLLECTORS = [
    {"table_id": "1_bklog.test_index_1", "bk_biz_id": 100},
    {"table_id": "1_bklog.test_index_2", "bk_biz_id": 100},
    {"table_id": "2_bklog.test_index_3", "bk_biz_id": 200},
]

# Mock 的 cluster_infos 返回值，模拟 bulk_cluster_infos 的返回结构
MOCK_CLUSTER_INFOS = {
    "1_bklog.test_index_1": {
        "cluster_config": {"cluster_id": TARGET_CLUSTER_ID, "cluster_name": "target_cluster"},
        "storage_config": {"retention": 7},
    },
    "1_bklog.test_index_2": {
        "cluster_config": {"cluster_id": TARGET_CLUSTER_ID, "cluster_name": "target_cluster"},
        "storage_config": {"retention": 7},
    },
    "2_bklog.test_index_3": {
        "cluster_config": {"cluster_id": OTHER_CLUSTER_ID, "cluster_name": "other_cluster"},
        "storage_config": {"retention": 7},
    },
}


def _apply_exclude(data, key, value):
    """
    模拟 Django QuerySet.exclude() 的过滤行为。

    支持:
        - exclude(table_id__isnull=True): 过滤掉 table_id 为 None 的记录
        - exclude(table_id=""): 过滤掉 table_id 为空字符串的记录

    :param data: 当前数据集
    :param key: 过滤字段名（可能带 __isnull 后缀）
    :param value: 过滤值
    :return: 过滤后的新列表
    """
    if key.endswith("__isnull") and value is True:
        field_name = key[: -len("__isnull")]
        return [row for row in data if row.get(field_name) is not None]
    return [row for row in data if row.get(key) != value]


class _FakeValuesQuerySet:
    """模拟 Django QuerySet.values() 的返回值，支持 list() 迭代。"""

    def __init__(self, data):
        self._data = data

    def __iter__(self):
        return iter(self._data)

    def values(self, *fields):
        return self._data


class _FakeExcludeQuerySet:
    """模拟 Django QuerySet，支持链式 exclude() 调用。"""

    def __init__(self, data):
        self._data = data

    def exclude(self, *args, **kwargs):
        data = self._data
        for arg in args:
            for key, value in arg.items():
                data = _apply_exclude(data, key, value)
        for key, value in kwargs.items():
            data = _apply_exclude(data, key, value)
        return _FakeExcludeQuerySet(data)

    def values(self, *fields):
        return _FakeValuesQuerySet(self._data)


def _make_manager_mock(all_data):
    """
    构造一个模拟的 CollectorConfig.objects manager。

    支持代码中的链式调用:
        CollectorConfig.objects.exclude(...).exclude(...).values(...)

    利用 _FakeExcludeQuerySet 自身的链式 exclude 能力，确保每次 exclude
    调用都基于上一次的结果继续过滤。

    :param all_data: 模拟的全量采集项数据
    :return: mock_manager
    """
    mock_manager = MagicMock()
    mock_manager.exclude.side_effect = lambda *args, **kwargs: _FakeExcludeQuerySet(
        all_data
    ).exclude(*args, **kwargs)

    return mock_manager


class TestShutdownCollectorWarmStorageConfig(TestCase):
    """测试 shutdown_collector_warm_storage_config 函数的性能和功能。"""

    def setUp(self):
        """每个测试用例前的准备工作。"""
        self.modify_result_table_patcher = patch(
            "apps.log_databus.tasks.collector.TransferApi.modify_result_table"
        )
        self.mock_modify_result_table = self.modify_result_table_patcher.start()
        self.mock_modify_result_table.return_value = {"result": True}

        self.bulk_cluster_infos_patcher = patch(
            "apps.log_databus.tasks.collector.CollectorHandler.bulk_cluster_infos"
        )
        self.mock_bulk_cluster_infos = self.bulk_cluster_infos_patcher.start()
        self.mock_bulk_cluster_infos.return_value = MOCK_CLUSTER_INFOS

    def tearDown(self):
        """清理 Mock。"""
        self.modify_result_table_patcher.stop()
        self.bulk_cluster_infos_patcher.stop()

    def _patch_manager(self, all_data):
        """
        用指定的全量数据构造 manager Mock 并 patch。

        :param all_data: 模拟的全量采集项数据
        :return: patch 上下文管理器
        """
        mock_manager = _make_manager_mock(all_data)
        return patch(
            "apps.log_databus.tasks.collector.CollectorConfig.objects",
            mock_manager,
        )

    def test_optimized_code_queries_once(self):
        """
        验证修复后只执行一次数据库查询（exclude + exclude + values）。

        修复前：两次 CollectorConfig.objects.all()
        修复后：一次 CollectorConfig.objects.exclude(...).exclude(...).values(...)

        注：Django 链式调用中，第一个 exclude 在 manager 上，第二个在 QuerySet 上，
        所以 mock_manager.exclude 只被调用一次，但过滤逻辑执行了两次。
        """
        mock_manager = _make_manager_mock(MOCK_COLLECTORS)

        with patch(
            "apps.log_databus.tasks.collector.CollectorConfig.objects",
            mock_manager,
        ):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            # manager.exclude 只被调用一次（链式调用的第一次）
            self.assertEqual(mock_manager.exclude.call_count, 1)
            # 第一次 exclude 的参数是排除 NULL
            mock_manager.exclude.assert_called_once_with(table_id__isnull=True)

    def test_functional_correctness(self):
        """
        验证修复后功能正确性：只对目标集群的采集项调用 modify_result_table。
        """
        with self._patch_manager(MOCK_COLLECTORS):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            # 只有 cluster_id == TARGET_CLUSTER_ID 的采集项才应该调用 modify_result_table
            expected_calls = [
                {
                    "table_id": "1_bklog.test_index_1",
                    "default_storage": "elasticsearch",
                    "default_storage_config": {"warm_phase_days": 0},
                    "bk_biz_id": 100,
                },
                {
                    "table_id": "1_bklog.test_index_2",
                    "default_storage": "elasticsearch",
                    "default_storage_config": {"warm_phase_days": 0},
                    "bk_biz_id": 100,
                },
            ]

            self.assertEqual(self.mock_modify_result_table.call_count, len(expected_calls))
            for call in self.mock_modify_result_table.call_args_list:
                self.assertIn(call[0][0], expected_calls)

    def test_no_table_id_skipped(self):
        """
        验证 table_id 为 NULL 的采集项被正确跳过（数据库层面过滤）。

        修复前：在 Python 层遍历后通过 if not collector.table_id: continue 跳过
        修复后：在数据库层面通过 exclude(table_id__isnull=True) 过滤
        """
        all_data = [
            {"table_id": None, "bk_biz_id": 100},
            {"table_id": "1_bklog.valid_index", "bk_biz_id": 200},
        ]

        with self._patch_manager(all_data):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            # NULL 被过滤，只有 valid_index 进入后续逻辑
            # 但 valid_index 不在 MOCK_CLUSTER_INFOS 中，所以 bulk_cluster_infos 返回的
            # cluster_info 为 None，不会调用 modify_result_table
            self.mock_bulk_cluster_infos.assert_called_once_with(
                result_table_list=["1_bklog.valid_index"]
            )
            self.assertEqual(self.mock_modify_result_table.call_count, 0)

    def test_pure_null_data_skips_all(self):
        """
        验证所有 table_id 都为 NULL 时，函数提前返回。
        """
        all_data = [
            {"table_id": None, "bk_biz_id": 100},
            {"table_id": None, "bk_biz_id": 200},
        ]

        with self._patch_manager(all_data):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            # 全部被过滤，collectors 为空列表，提前返回
            self.mock_bulk_cluster_infos.assert_not_called()
            self.assertEqual(self.mock_modify_result_table.call_count, 0)

    def test_empty_string_table_id_skipped(self):
        """
        验证 table_id 为空字符串的采集项被正确跳过（数据库层面过滤）。

        修复前：在 Python 层通过 if not collector.table_id: continue 跳过空字符串
        修复后：在数据库层面通过 exclude(table_id="") 过滤
        """
        all_data = [
            {"table_id": "", "bk_biz_id": 100},
            {"table_id": "1_bklog.valid_index", "bk_biz_id": 200},
        ]

        with self._patch_manager(all_data):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            # 空字符串被过滤，只有 valid_index 进入后续逻辑
            self.mock_bulk_cluster_infos.assert_called_once_with(
                result_table_list=["1_bklog.valid_index"]
            )
            self.assertEqual(self.mock_modify_result_table.call_count, 0)

    def test_mixed_null_and_empty_string(self):
        """
        验证同时存在 NULL 和空字符串 table_id 时，两者都被过滤。
        """
        all_data = [
            {"table_id": None, "bk_biz_id": 100},
            {"table_id": "", "bk_biz_id": 200},
            {"table_id": "1_bklog.test_index_1", "bk_biz_id": 100},
        ]

        with self._patch_manager(all_data):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            # NULL 和空字符串都被过滤，只剩有效记录
            self.mock_bulk_cluster_infos.assert_called_once_with(
                result_table_list=["1_bklog.test_index_1"]
            )

    def test_empty_collectors_early_return(self):
        """
        验证当没有采集项时，函数提前返回，不调用后续逻辑。
        """
        with self._patch_manager([]):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            self.mock_bulk_cluster_infos.assert_not_called()
            self.assertEqual(self.mock_modify_result_table.call_count, 0)

    def test_cluster_id_filter(self):
        """
        验证集群 ID 过滤逻辑：只有匹配目标 cluster_id 的采集项才会修改存储配置。
        """
        all_data = [
            {"table_id": "2_bklog.test_index_3", "bk_biz_id": 200},
        ]
        other_cluster_infos = {
            "2_bklog.test_index_3": {
                "cluster_config": {"cluster_id": OTHER_CLUSTER_ID, "cluster_name": "other_cluster"},
                "storage_config": {"retention": 7},
            },
        }
        self.mock_bulk_cluster_infos.return_value = other_cluster_infos

        with self._patch_manager(all_data):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            # 没有匹配的集群，不应调用 modify_result_table
            self.assertEqual(self.mock_modify_result_table.call_count, 0)

    def test_modify_result_table_error_handled(self):
        """
        验证单个 modify_result_table 调用失败时不影响其他采集项的处理。
        """
        self.mock_modify_result_table.side_effect = [
            Exception("API error"),  # 第一个调用失败
            {"result": True},  # 第二个调用成功
        ]

        with self._patch_manager(MOCK_COLLECTORS):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            # 仍然应该尝试处理所有匹配的采集项（2个匹配）
            self.assertEqual(self.mock_modify_result_table.call_count, 2)

    def test_bulk_cluster_infos_receives_correct_tables(self):
        """
        验证 bulk_cluster_infos 接收到的 result_table_list 参数正确。
        """
        with self._patch_manager(MOCK_COLLECTORS):
            shutdown_collector_warm_storage_config(TARGET_CLUSTER_ID)

            expected_tables = ["1_bklog.test_index_1", "1_bklog.test_index_2", "2_bklog.test_index_3"]
            self.mock_bulk_cluster_infos.assert_called_once_with(result_table_list=expected_tables)
