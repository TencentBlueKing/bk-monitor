"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from alarm_backends.core.cache.result_table import ResultTableCacheManager


def test_refresh_by_strategy_records_with_relations():
    """
    测试基于策略记录刷新结果表缓存 - 存在表业务关系的情况
    """
    with mock.patch.multiple(
        "alarm_backends.core.cache.result_table.ResultTableCacheManager",
        refresh_metadata=mock.DEFAULT,
        refresh_bkdata=mock.DEFAULT,
        refresh_bklog=mock.DEFAULT,
        logger=mock.DEFAULT,
    ):
        with mock.patch(
            "alarm_backends.core.cache.result_table.StrategyCacheManager.get_table_biz_relations"
        ) as mock_get_relations:
            with mock.patch("alarm_backends.core.cache.result_table.ThreadPool") as mock_thread_pool_class:
                # 设置模拟返回值 (包含完整的数据源信息)
                mock_get_relations.return_value = {
                    ("table1", "2", "bk_monitor", "time_series"),
                    ("table2", "2", "bk_data", "time_series"),
                    ("table1", "3", "bk_log_search", "log"),
                }

                # 模拟线程池
                mock_thread_pool = mock.Mock()
                mock_thread_pool_class.return_value = mock_thread_pool

                # 调用被测试的方法
                ResultTableCacheManager.refresh_by_strategy_records()

                # 验证调用
                mock_get_relations.assert_called_once()

                # 验证线程池的使用
                mock_thread_pool_class.assert_called_once_with(ResultTableCacheManager.THREAD_POOL_SIZE)
                assert mock_thread_pool.apply_async.call_count == 3  # 3个不同的业务和数据源类型

                # 验证refresh方法被正确调用
                expected_calls = [
                    mock.call(ResultTableCacheManager.refresh_metadata, args=(["2"], ["table1"])),
                    mock.call(ResultTableCacheManager.refresh_bkdata, args=(["2"], ["table2"])),
                    mock.call(ResultTableCacheManager.refresh_bklog, args=(["3"], ["table1"])),
                ]

                mock_thread_pool.apply_async.assert_has_calls(expected_calls, any_order=True)

                # 验证线程池关闭方法被调用
                mock_thread_pool.close.assert_called_once()
                mock_thread_pool.join.assert_called_once()


def test_refresh_by_strategy_records_empty_relations():
    """
    测试基于策略记录刷新结果表缓存 - 无表业务关系的情况
    """
    with mock.patch.multiple(
        "alarm_backends.core.cache.result_table.ResultTableCacheManager", refresh=mock.DEFAULT, logger=mock.DEFAULT
    ) as mocks:
        with mock.patch(
            "alarm_backends.core.cache.result_table.StrategyCacheManager.get_table_biz_relations"
        ) as mock_get_relations:
            # 设置模拟返回值为空
            mock_get_relations.return_value = set()

            # 调用被测试的方法
            ResultTableCacheManager.refresh_by_strategy_records()

            # 验证调用
            mock_get_relations.assert_called_once()
            mocks["logger"].info.assert_called_once_with(
                "[result_table_cache] No table-biz relations found, fallback to full refresh"
            )
            mocks["refresh"].assert_called_once()


def test_refresh_by_strategy_records_chunking():
    """
    测试基于策略记录刷新结果表缓存 - 表ID分块处理的情况
    """
    with mock.patch.multiple(
        "alarm_backends.core.cache.result_table.ResultTableCacheManager",
        refresh_metadata=mock.DEFAULT,
        refresh_bkdata=mock.DEFAULT,
        refresh_bklog=mock.DEFAULT,
        logger=mock.DEFAULT,
    ):
        with mock.patch(
            "alarm_backends.core.cache.result_table.StrategyCacheManager.get_table_biz_relations"
        ) as mock_get_relations:
            with mock.patch("alarm_backends.core.cache.result_table.ThreadPool") as mock_thread_pool_class:
                # 创建超过分块大小的表ID
                table_ids = [f"table{i}" for i in range(15)]  # 15个表ID，分块大小为10
                relations = {(table_id, "2", "bk_monitor", "time_series") for table_id in table_ids}
                mock_get_relations.return_value = relations

                # 模拟线程池
                mock_thread_pool = mock.Mock()
                mock_thread_pool_class.return_value = mock_thread_pool

                # 调用被测试的方法
                ResultTableCacheManager.refresh_by_strategy_records()

                # 验证调用
                mock_get_relations.assert_called_once()

                # 验证线程池的使用
                assert mock_thread_pool.apply_async.call_count == 2  # 2个分块 * 1种刷新方法

                # 验证线程池关闭方法被调用
                mock_thread_pool.close.assert_called_once()
                mock_thread_pool.join.assert_called_once()
