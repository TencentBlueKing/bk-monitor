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
from constants.data_source import DataSourceLabel


def test_refresh_with_relations():
    """
    测试基于策略记录刷新结果表缓存 - 存在表业务关系的情况
    """
    with mock.patch(
        "alarm_backends.core.cache.result_table.StrategyCacheManager.get_table_biz_relations"
    ) as mock_get_relations:
        with mock.patch("alarm_backends.core.cache.result_table.ThreadPool") as mock_thread_pool_class:
            # 设置模拟返回值 (包含表ID、业务ID和数据源标签)
            mock_get_relations.return_value = {
                ("table1", "2", DataSourceLabel.BK_MONITOR_COLLECTOR),
                ("table2", "2", DataSourceLabel.BK_DATA),
                ("table1", "3", DataSourceLabel.BK_LOG_SEARCH),
                ("table3", "4", DataSourceLabel.CUSTOM),
            }

            # 模拟线程池
            mock_thread_pool = mock.Mock()
            mock_thread_pool_class.return_value = mock_thread_pool

            # 调用被测试的方法
            ResultTableCacheManager.refresh()

            # 验证调用
            mock_get_relations.assert_called_once()

            # 验证线程池的使用
            mock_thread_pool_class.assert_called_once_with(ResultTableCacheManager.THREAD_POOL_SIZE)
            assert mock_thread_pool.apply_async.call_count == 4  # 4个不同的数据处理调用

            # 验证refresh方法被正确调用
            # 注意：元数据和数据平台只传递表ID列表，日志平台传递业务ID和表ID列表
            expected_calls = [
                mock.call(ResultTableCacheManager.refresh_metadata, args=(["table1"],)),  # BK_MONITOR_COLLECTOR
                mock.call(ResultTableCacheManager.refresh_metadata, args=(["table3"],)),  # CUSTOM
                mock.call(ResultTableCacheManager.refresh_bkdata, args=(["table2"],)),  # BK_DATA
                mock.call(ResultTableCacheManager.refresh_bklog, args=(["3"], ["table1"])),  # BK_LOG_SEARCH
            ]

            mock_thread_pool.apply_async.assert_has_calls(expected_calls, any_order=True)

            # 验证线程池关闭方法被调用
            mock_thread_pool.close.assert_called_once()
            mock_thread_pool.join.assert_called_once()


def test_refresh_empty_relations():
    """
    测试基于策略记录刷新结果表缓存 - 无表业务关系的情况
    """
    with mock.patch(
        "alarm_backends.core.cache.result_table.StrategyCacheManager.get_table_biz_relations"
    ) as mock_get_relations:
        with mock.patch("alarm_backends.core.cache.result_table.ThreadPool") as mock_thread_pool_class:
            with mock.patch.object(ResultTableCacheManager, "logger") as mock_logger:
                # 设置模拟返回值为空
                mock_get_relations.return_value = set()

                # 调用被测试的方法
                ResultTableCacheManager.refresh()

                # 验证调用
                mock_get_relations.assert_called_once()
                mock_logger.info.assert_called_once_with(
                    "[result_table_cache] No table-biz relations found, fallback to full refresh"
                )

                # 验证线程池未被创建
                mock_thread_pool_class.assert_not_called()


def test_refresh_chunking():
    """
    测试基于策略记录刷新结果表缓存 - 表ID分块处理的情况
    """
    with mock.patch(
        "alarm_backends.core.cache.result_table.StrategyCacheManager.get_table_biz_relations"
    ) as mock_get_relations:
        with mock.patch("alarm_backends.core.cache.result_table.ThreadPool") as mock_thread_pool_class:
            # 创建超过分块大小的表ID
            table_ids = [f"table{i}" for i in range(15)]  # 15个表ID，分块大小为10
            relations = {(table_id, "2", DataSourceLabel.BK_MONITOR_COLLECTOR) for table_id in table_ids}
            mock_get_relations.return_value = relations

            # 模拟线程池
            mock_thread_pool = mock.Mock()
            mock_thread_pool_class.return_value = mock_thread_pool

            # 调用被测试的方法
            ResultTableCacheManager.refresh()

            # 验证调用
            mock_get_relations.assert_called_once()

            # 验证分块处理
            assert mock_thread_pool.apply_async.call_count == 2

            # 验证线程池关闭方法被调用
            mock_thread_pool.close.assert_called_once()
            mock_thread_pool.join.assert_called_once()
