# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from dateutil import tz

from metadata.models import StorageClusterRecord
from metadata.models.storage import ESStorage


@pytest.fixture
def mock_es_clients():
    """
    创建多个 Mock 的 Elasticsearch 客户端，模拟不同集群返回的 get_alias 数据。
    """
    client_1 = MagicMock()
    client_1.indices.get_alias.return_value = {
        'v2_2_bklog_rt_create_20241125_0': {
            'aliases': {
                '2_bklog_rt_create_20241205_read': {},  # 过期别名
                '2_bklog_rt_create_20241218_read': {},  # 未过期别名
            }
        },
        'v2_2_bklog_rt_create_20241120_0': {
            'aliases': {
                '2_bklog_rt_create_20241205_read': {},  # 过期别名
            }
        },
    }
    client_1.indices.delete_alias.return_value = True
    client_1.indices.delete.return_value = True

    client_2 = MagicMock()
    client_2.indices.get_alias.return_value = {
        'v2_2_bklog_rt_create_20241130_0': {
            'aliases': {
                '2_bklog_rt_create_20241218_read': {},  # 未过期别名
            }
        },
        'v2_2_bklog_rt_create_20241115_0': {
            'aliases': {
                '2_bklog_rt_create_20241205_read': {},  # 过期别名
            }
        },
    }
    client_2.indices.delete_alias.return_value = True
    client_2.indices.delete.return_value = True

    client_3 = MagicMock()
    client_3.indices.get_alias.return_value = {
        'v2_2_bklog_rt_create_20241130_0': {
            'aliases': {
                '2_bklog_rt_create_20241201_read': {},  # 过期别名
            }
        },
    }
    client_3.indices.delete_alias.return_value = True
    client_3.indices.delete.return_value = True

    return {1: client_1, 2: client_2, 3: client_3}


@pytest.fixture
def es_storage():
    """
    创建一个 Mock 的 ESStorage 对象，并配置默认属性和方法
    """
    es_storage_ins = ESStorage()
    es_storage_ins.table_id = "2_bklog_rt_create"
    es_storage_ins.retention = 7  # 模拟保留时间为 7 天
    es_storage_ins.date_format = "%Y%m%d"

    # Mock can_delete 方法
    es_storage_ins.can_delete = MagicMock(return_value=True)

    # 使用 patch.object 来模拟 now 属性为 offset-naive 的 datetime
    with patch.object(type(es_storage_ins), 'now', new=datetime(2024, 12, 19, 10, 0, tzinfo=tz.tzutc())):
        yield es_storage_ins


@pytest.fixture
def create_or_delete_records(mocker):
    """
    创建测试用的 StorageClusterRecord 数据
    """
    record1 = StorageClusterRecord.objects.create(
        table_id="2_bklog_rt_create",
        cluster_id=1,
        is_deleted=False,
        is_current=False,
    )
    record2 = StorageClusterRecord.objects.create(
        table_id="2_bklog_rt_create",
        cluster_id=2,
        is_deleted=False,
        is_current=False,
    )
    record2 = StorageClusterRecord.objects.create(
        table_id="2_bklog_rt_create",
        cluster_id=3,
        is_deleted=False,
        is_current=False,
    )
    yield
    record1.delete()
    record2.delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
@patch("metadata.utils.es_tools.get_client")
def test_clean_index_v2(mock_get_client, es_storage, create_or_delete_records, mock_es_clients):
    """
    测试 clean_index_v2 方法在多集群场景下的逻辑
    """

    # 根据 cluster_id 返回对应的 mock 客户端
    def mock_get_client_by_cluster_id(cluster_id):
        return mock_es_clients[cluster_id]

    mock_get_client.side_effect = mock_get_client_by_cluster_id

    # 执行清理逻辑
    es_storage.clean_history_es_index()

    # 验证【过期别名】的删除
    mock_es_clients[1].indices.delete_alias.assert_any_call(
        index='v2_2_bklog_rt_create_20241125_0', name='2_bklog_rt_create_20241205_read'
    )

    # 验证没有【未过期别名】的索引被正常删除
    mock_es_clients[1].indices.delete.assert_any_call(index='v2_2_bklog_rt_create_20241120_0')
    mock_es_clients[2].indices.delete.assert_any_call(index='v2_2_bklog_rt_create_20241115_0')
    mock_es_clients[3].indices.delete.assert_any_call(index='v2_2_bklog_rt_create_20241130_0')

    # 验证 StorageClusterRecord 的 is_deleted 更新逻辑
    # Cluster 1 仍有未过期的索引，因此 is_deleted 应为 False
    record1 = StorageClusterRecord.objects.get(cluster_id=1)
    assert record1.is_deleted is False

    record2 = StorageClusterRecord.objects.get(cluster_id=2)
    assert record2.is_deleted is False

    record3 = StorageClusterRecord.objects.get(cluster_id=3)
    assert record3.is_deleted is True
