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
import pytest
from unittest.mock import MagicMock

from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.models.space.constants import DATA_LABEL_TO_RESULT_TABLE_KEY, DATA_LABEL_TO_RESULT_TABLE_CHANNEL


@pytest.fixture
def mock_space_table_id_redis():
    """创建SpaceTableIDRedis的mock fixture"""
    return SpaceTableIDRedis()


@pytest.mark.django_db(databases=["monitor_api"])
def test_push_data_label_table_ids(mock_space_table_id_redis):
    """测试push_data_label_table_ids方法"""
    with (
        mock.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis,
        mock.patch("metadata.models.space.space_table_id_redis.filter_model_by_in_page") as mock_refine,
        mock.patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
    ):
        # 模拟返回数据
        mock_data = [
            {"table_id": "system", "data_label": "host_cpu"},
            {"table_id": "custom.metric", "data_label": "app_metric,memory_metrics"},  # 移除逗号后的空格
        ]
        mock_refine.return_value = mock_data

        # 调用测试方法
        mock_space_table_id_redis.push_data_label_table_ids(
            data_label_list=["host_cpu", "app_metric,memory_metrics"],  # 保持输入格式一致
            table_id_list=["system", "custom.metric"],
            is_publish=True,
        )

        # 验证redis操作
        expected_redis_values = {
            "memory_metrics": '["custom.metric"]',
            "app_metric": '["custom.metric"]',
            "host_cpu": '["system.__default__"]',
        }
        mock_hmset_to_redis.assert_called_once_with(DATA_LABEL_TO_RESULT_TABLE_KEY, expected_redis_values)
        mock_publish.assert_called_once_with(
            DATA_LABEL_TO_RESULT_TABLE_CHANNEL, ["host_cpu", "app_metric", "memory_metrics"]
        )


def test_push_with_empty_result(mock_space_table_id_redis):
    """测试当没有匹配结果时的情况"""
    with mock.patch.object(mock_space_table_id_redis, "_refine_available_data_label") as mock_refine:
        mock_refine.return_value = []
        result = mock_space_table_id_redis.push_data_label_table_ids(data_label_list=["not_exist_label"])
        assert result is None


def test_push_and_publish_es_aliases_single():
    """测试push_and_publish_es_aliases方法 - 单个data_label情况"""
    from metadata.service.space_redis import push_and_publish_es_aliases

    with (
        mock.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis,
        mock.patch("metadata.models.ResultTable.objects.filter") as mock_filter,
        mock.patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
    ):
        mock_data = ["custom.metric"]
        mock_queryset = MagicMock()
        mock_queryset.values_list.return_value = mock_data
        mock_filter.return_value = mock_queryset

        push_and_publish_es_aliases("host_cpu")

        expected_redis_values = {
            "host_cpu": '["custom.metric"]',
        }
        mock_hmset_to_redis.assert_called_once_with(DATA_LABEL_TO_RESULT_TABLE_KEY, expected_redis_values)
        mock_publish.assert_called_once_with(DATA_LABEL_TO_RESULT_TABLE_CHANNEL, ["host_cpu"])


def test_push_and_publish_es_aliases_multiple():
    """测试push_and_publish_es_aliases方法 - 多个data_label情况"""
    from metadata.service.space_redis import push_and_publish_es_aliases

    with (
        mock.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis,
        mock.patch("metadata.models.ResultTable.objects.filter") as mock_filter,
        mock.patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
    ):
        mock_data = ["custom.metric"]
        mock_queryset = MagicMock()
        mock_queryset.values_list.return_value = mock_data
        mock_filter.return_value = mock_queryset

        # 修复输入字符串中的多余逗号问题
        push_and_publish_es_aliases("app_metric,memory_metrics,")

        expected_redis_values = {
            "app_metric": '["custom.metric"]',
            "memory_metrics": '["custom.metric"]',
        }
        mock_hmset_to_redis.assert_called_once_with(DATA_LABEL_TO_RESULT_TABLE_KEY, expected_redis_values)
        mock_publish.assert_called_once_with(DATA_LABEL_TO_RESULT_TABLE_CHANNEL, list(expected_redis_values.keys()))
