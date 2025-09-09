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

from alarm_backends.core.cache.strategy import StrategyCacheManager
from constants.data_source import DataSourceLabel, DataTypeLabel


def test_record_table_biz_relations():
    """
    测试记录策略使用的表名与业务ID关系
    """
    # 模拟缓存对象以避免实际的Redis调用
    with mock.patch("alarm_backends.core.cache.strategy.StrategyCacheManager.cache") as mock_cache:
        mock_pipeline = mock.Mock()
        mock_cache.pipeline.return_value = mock_pipeline

        strategies = [
            {
                "bk_biz_id": 2,
                "items": [
                    {
                        "query_configs": [
                            {
                                "result_table_id": "table1",
                                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                                "data_type_label": DataTypeLabel.TIME_SERIES,
                            }
                        ]
                    },
                    {
                        "query_configs": [
                            {
                                "result_table_id": "table2",
                                "data_source_label": DataSourceLabel.BK_DATA,
                                "data_type_label": DataTypeLabel.TIME_SERIES,
                            }
                        ]
                    },
                ],
            },
            {
                "bk_biz_id": 3,
                "items": [
                    {
                        "query_configs": [
                            {
                                "result_table_id": "table1",  # 相同表名不同业务
                                "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                                "data_type_label": DataTypeLabel.LOG,
                                "index_set_id": "log_table1",
                            }
                        ]
                    }
                ],
            },
        ]

        StrategyCacheManager.record_table_biz_relations(strategies)

        # 验证管道调用
        mock_cache.pipeline.assert_called_once()
        mock_pipeline.delete.assert_called_once_with(StrategyCacheManager.STRATEGY_TABLE_BIZ_CACHE_KEY)
        mock_pipeline.expire.assert_called_once_with(
            StrategyCacheManager.STRATEGY_TABLE_BIZ_CACHE_KEY, StrategyCacheManager.CACHE_TIMEOUT
        )
        mock_pipeline.execute.assert_called_once()

        # 检查 sadd 是否使用正确的参数调用
        expected_calls = [
            mock.call(
                StrategyCacheManager.STRATEGY_TABLE_BIZ_CACHE_KEY,
                f"table1|2|{DataSourceLabel.BK_MONITOR_COLLECTOR}",
            ),
            mock.call(
                StrategyCacheManager.STRATEGY_TABLE_BIZ_CACHE_KEY,
                f"table2|2|{DataSourceLabel.BK_DATA}",
            ),
            mock.call(
                StrategyCacheManager.STRATEGY_TABLE_BIZ_CACHE_KEY,
                f"log_table1|3|{DataSourceLabel.BK_LOG_SEARCH}",
            ),
        ]
        mock_pipeline.sadd.assert_has_calls(expected_calls, any_order=True)
        assert mock_pipeline.sadd.call_count == 3


def test_record_table_biz_relations_empty_strategies():
    """
    测试空策略列表的情况
    """
    with mock.patch("alarm_backends.core.cache.strategy.StrategyCacheManager.cache") as mock_cache:
        mock_pipeline = mock.Mock()
        mock_cache.pipeline.return_value = mock_pipeline

        strategies = []

        StrategyCacheManager.record_table_biz_relations(strategies)

        # 对于空策略列表，不会调用pipeline，因为没有记录需要保存
        mock_cache.pipeline.assert_not_called()
        mock_pipeline.delete.assert_not_called()
        mock_pipeline.expire.assert_not_called()
        mock_pipeline.execute.assert_not_called()
        mock_pipeline.sadd.assert_not_called()


def test_record_table_biz_relations_missing_fields():
    """
    测试策略字段缺失的情况
    """
    with mock.patch("alarm_backends.core.cache.strategy.StrategyCacheManager.cache") as mock_cache:
        mock_pipeline = mock.Mock()
        mock_cache.pipeline.return_value = mock_pipeline

        strategies = [
            {
                # 缺少 bk_biz_id
                "items": [
                    {
                        "query_configs": [
                            {
                                "result_table_id": "table1",
                                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                                "data_type_label": DataTypeLabel.TIME_SERIES,
                            }
                        ]
                    }
                ]
            },
            {
                "bk_biz_id": 2,
                # 缺少 items
            },
            {
                "bk_biz_id": 3,
                "items": [
                    {
                        # 缺少 query_configs
                    }
                ],
            },
        ]

        StrategyCacheManager.record_table_biz_relations(strategies)

        # 在这种情况下不会调用pipeline，因为没有有效的记录 (bk_biz_id为None)
        mock_cache.pipeline.assert_not_called()
        mock_pipeline.delete.assert_not_called()
        mock_pipeline.expire.assert_not_called()
        mock_pipeline.execute.assert_not_called()
        mock_pipeline.sadd.assert_not_called()


def test_get_table_biz_relations():
    """
    测试获取策略使用的表名与业务ID关系
    """
    with mock.patch("alarm_backends.core.cache.strategy.StrategyCacheManager.cache") as mock_cache:
        mock_records = [
            f"table1|2|{DataSourceLabel.BK_MONITOR_COLLECTOR}".encode(),
            f"table2|2|{DataSourceLabel.BK_DATA}".encode(),
            f"table1|3|{DataSourceLabel.BK_LOG_SEARCH}".encode(),
            f"table3|4|{DataSourceLabel.CUSTOM}",  # 字符串类型记录
        ]

        mock_cache.smembers.return_value = mock_records

        result = StrategyCacheManager.get_table_biz_relations()

        # 验证 smembers 被调用
        mock_cache.smembers.assert_called_once_with(StrategyCacheManager.STRATEGY_TABLE_BIZ_CACHE_KEY)

        # 检查结果
        expected_result = {
            ("table1", "2", DataSourceLabel.BK_MONITOR_COLLECTOR),
            ("table2", "2", DataSourceLabel.BK_DATA),
            ("table1", "3", DataSourceLabel.BK_LOG_SEARCH),
            ("table3", "4", DataSourceLabel.CUSTOM),
        }
        assert result == expected_result


def test_get_table_biz_relations_empty():
    """
    测试获取空关系的情况
    """
    with mock.patch("alarm_backends.core.cache.strategy.StrategyCacheManager.cache") as mock_cache:
        mock_cache.smembers.return_value = set()

        result = StrategyCacheManager.get_table_biz_relations()

        mock_cache.smembers.assert_called_once_with(StrategyCacheManager.STRATEGY_TABLE_BIZ_CACHE_KEY)
        assert result == set()


def test_get_table_biz_relations_malformed_record():
    """
    测试处理格式错误记录的情况
    """
    with mock.patch("alarm_backends.core.cache.strategy.StrategyCacheManager.cache") as mock_cache:
        mock_records = [
            f"table1|2|{DataSourceLabel.BK_MONITOR_COLLECTOR}".encode(),
            b"malformed_record",  # 缺少分隔符
            b"table2|3|extra|field|too_many",  # 分隔符过多
        ]

        mock_cache.smembers.return_value = mock_records

        result = StrategyCacheManager.get_table_biz_relations()

        expected_result = {("table1", "2", DataSourceLabel.BK_MONITOR_COLLECTOR)}
        assert result == expected_result
