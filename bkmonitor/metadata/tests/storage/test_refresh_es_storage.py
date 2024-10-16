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
from unittest import mock

import pytest
from dateutil import tz
from elasticsearch import NotFoundError

from metadata.models import ESStorage


@pytest.fixture
def es_storage():
    # 创建一个mock的返回值
    es_storage_ins = ESStorage(
        table_id='2_bklog.test_rotation', need_create_index=True, slice_gap=1440, time_zone=0, date_format='%Y%m%d'
    )

    mock_return_value = {
        'index_version': 'v2',
        'datetime_object': datetime(2024, 10, 16, 0, 0, tzinfo=tz.tzutc()),
        'index': 0,
        'size': 18498270403,
    }
    es_storage_ins.current_index_info = mock.Mock(return_value=mock_return_value)
    # 使用 patch.object 来模拟 now 属性
    with mock.patch.object(ESStorage, 'now', new_callable=mock.PropertyMock) as mock_now:
        # 定义 now 属性返回的模拟值
        mock_now.return_value = datetime(2024, 10, 15, 10, 0, tzinfo=tz.tzutc())
        yield es_storage_ins


@pytest.fixture
def mock_es_client():
    client = mock.Mock()
    # Mock the return value of indices.stats to simulate a real response
    client.indices.stats.return_value = {"indices": {"ready_index": {"total": {"store": {"size_in_bytes": 123456}}}}}
    return client


EXPECTED_CURRENT_ALIAS = 'write_20241015_2_bklog_test_rotation'
EXPECTED_FUTURE_ALIAS = 'write_20241016_2_bklog_test_rotation'
EXPECTED_FUTURE_INDEX = 'v2_2_bklog_test_rotation_20241016_0'
PAST_AVAILABLE_INDEX = 'v2_2_bklog_test_rotation_20241015_0'


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_alias_creation_with_ready_index(es_storage, mock_es_client):
    # 场景1：新索引就绪，能够正常创建当前和明天的别名及其对应的索引绑定关系
    es_storage.es_client = mock_es_client
    es_storage.is_index_ready = mock.Mock(return_value=True)
    es_storage.get_current_index_name = mock.Mock(return_value="ready_index")

    mock_es_client.indices.get_alias.side_effect = NotFoundError
    mock_es_client.indices.update_aliases.return_value = {}
    es_storage.create_or_update_aliases()

    update_aliases_calls = mock_es_client.indices.update_aliases.call_args_list
    # 验证第一个调用的参数,即当天的索引->新别名 的绑定关系切换
    first_call_args = update_aliases_calls[0][1]['body']  # 获取第一个调用的参数
    assert 'actions' in first_call_args
    assert 'add' in first_call_args['actions'][0]
    assert first_call_args['actions'][0]['add']['alias'] == EXPECTED_CURRENT_ALIAS
    assert first_call_args['actions'][0]['add']['index'] == EXPECTED_FUTURE_INDEX

    # 验证第二个调用的参数，即明天的索引->新别名 的绑定关系创建/切换
    second_call_args = update_aliases_calls[1][1]['body']
    assert 'actions' in second_call_args
    assert 'add' in second_call_args['actions'][0]
    assert second_call_args['actions'][0]['add']['alias'] == EXPECTED_FUTURE_ALIAS
    assert second_call_args['actions'][0]['add']['index'] == EXPECTED_FUTURE_INDEX

    assert mock_es_client.indices.update_aliases.call_count == 2


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_create_or_update_aliases_index_not_ready(es_storage, mock_es_client):
    # 模拟新索引未就绪，那么未来的别名将绑定上次可用的索引
    mock_es_client.cluster.health.return_value = {
        "indices": {
            EXPECTED_FUTURE_INDEX: {"status": "yellow"},  # 设置索引状态为 yellow，表示未就绪
            PAST_AVAILABLE_INDEX: {"status": "green"},  # 设置上次可用的索引状态为 green，表示就绪
        }
    }

    es_storage.es_client = mock_es_client
    is_index_ready = es_storage.is_index_ready(es_storage.es_client, EXPECTED_FUTURE_INDEX)
    assert not is_index_ready

    mock_es_client.indices.get_alias.return_value = {PAST_AVAILABLE_INDEX: {}}

    es_storage.create_or_update_aliases()

    update_aliases_calls = mock_es_client.indices.update_aliases.call_args_list

    # 验证第一个调用的参数,即明天的索引->新别名 的绑定关系切换，此处不应出现当天的别名切换，因为新索引未就绪
    first_call_args = update_aliases_calls[0][1]['body']  # 获取第一个调用的参数
    assert 'actions' in first_call_args
    assert 'add' in first_call_args['actions'][0]
    assert first_call_args['actions'][0]['add']['alias'] == EXPECTED_FUTURE_ALIAS
    assert first_call_args['actions'][0]['add']['index'] == PAST_AVAILABLE_INDEX

    assert mock_es_client.indices.update_aliases.call_count == 1
