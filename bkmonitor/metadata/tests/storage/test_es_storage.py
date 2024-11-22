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

import json
from unittest.mock import MagicMock

import pytest

from metadata import models
from metadata.resources import CreateResultTableResource
from metadata.tests.common_utils import consul_client


@pytest.fixture
def mock_consul(mocker):
    # Mock Consul 的 KV 操作
    mock_consul_client = mocker.patch("metadata.utils.consul_tools.consul.BKConsul")
    # Mock KV 操作，模拟返回值
    mock_kv = mocker.MagicMock()
    mock_kv.get.return_value = (None, None)  # 模拟返回空值
    mock_kv.put.return_value = True  # 模拟 put 操作成功
    mock_consul_client.return_value.kv = mock_kv
    return mock_consul_client


@pytest.fixture
def mock_es_client(mocker):
    """
    Mock Elasticsearch Client
    """
    mock_client = MagicMock()
    mock_get_alias = mock_client.indices.get_alias
    # 模拟返回值
    mock_get_alias.return_value = {
        'v2_2_bklog_rt_create_20241121_1': {'aliases': {}},
        'v2_2_bklog_rt_create_20241121_0': {
            'aliases': {
                '2_bklog_rt_create_20241121_read': {},
                '2_bklog_rt_create_20241122_read': {},
                'write_20241121_2_bklog_rt_create': {},
                'write_20241122_2_bklog_rt_create': {},
            }
        },
    }
    return mock_client


@pytest.fixture
def create_or_delete_records(mocker):
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source = models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="2_bklog.rt_create",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.KafkaTopicInfo.objects.create(
        bk_data_id=50010,
        topic='test_50010',
        partition=0,
    )
    # field1,_ = models.ResultTableField.objects.get_or_create(
    #     table_id="2_bklog.rt_create",
    #     field_name='time',
    #     field_type='string',
    #     is_config_by_user=True,
    #
    # )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    models.KafkaStorage.objects.all().delete()
    # field1.delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_create_result_table_resource_for_es_storage(create_or_delete_records, mock_consul):
    params = dict(
        bk_data_id=50010,
        table_id="2_bklog.rt_create",
        table_name_zh="1001_bklog_test",
        is_custom_table=True,
        schema_type="fix",
        bk_biz_id="2",
        default_storage=models.ClusterInfo.TYPE_ES,
        default_storage_config={
            "mapping_settings": {
                "dynamic_templates": [
                    {
                        "strings_as_keywords": {
                            "match_mapping_type": "string",
                            "mapping": {"norms": "false", "type": "keyword"},
                        }
                    }
                ],
                "properties": {"new_time": {"type": "alias", "path": "time"}},
            }
        },
        operator="admin",
        data_label="1001_bklog_test",
    )
    # 执行创建操作
    CreateResultTableResource().request(**params)
    rt = models.ResultTable.objects.get(table_id="2_bklog.rt_create")
    es_rt = models.ESStorage.objects.get(table_id="2_bklog.rt_create")
    assert rt.bk_biz_id == 2
    assert es_rt.mapping_settings == json.dumps(
        {
            "dynamic_templates": [
                {
                    "strings_as_keywords": {
                        "match_mapping_type": "string",
                        "mapping": {"norms": "false", "type": "keyword"},
                    }
                }
            ],
            "properties": {"new_time": {"type": "alias", "path": "time"}},
        }
    )

    field1_option = models.ResultTableFieldOption.objects.get(table_id="2_bklog.rt_create", field_name='time')
    assert field1_option.value == 'new_time'
    assert field1_option.name == 'es_alias_path'

    # 测试别名配置能否正确组装
    field_alias_mappings = es_rt.compose_field_alias_settings()

    expected = {"properties": {"new_time": {"type": "alias", "path": "time"}}}
    assert field_alias_mappings == expected
