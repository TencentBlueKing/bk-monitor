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
from metadata.resources import CreateResultTableResource, ModifyResultTableResource
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
    mock_get_mapping = mock_client.indices.get_mapping
    # 模拟返回值
    mock_get_alias.return_value = {
        'v2_2_bklog_rt_create_20241125_0': {
            'aliases': {
                '2_bklog_rt_create_20241125_read': {},
                '2_bklog_rt_create_20241126_read': {},
                'write_20241125_2_bklog_rt_create': {},
                'write_20241126_2_bklog_rt_create': {},
            }
        }
    }

    mock_get_mapping.return_value = {
        'v2_2_bklog_rt_create_20241125_0': {
            'mappings': {
                'dynamic_templates': [
                    {
                        'strings_as_keywords': {
                            'match_mapping_type': 'string',
                            'mapping': {'norms': 'false', 'type': 'keyword'},
                        }
                    }
                ],
                'properties': {
                    'bk_agent_id': {},
                    'bk_biz_id': {},
                    'bk_cloud_id': {},
                    'bk_cmdb_level': {},
                    'bk_host_id': {},
                    'bk_supplier_id': {},
                    'bk_target_host_id': {},
                    'ip': {},
                    'test_field1': {'type': 'text'},
                    # 'new_field1': {'type': 'alias', 'path': 'test_field1'},
                    'time': {},
                },
            }
        }
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
def test_create_and_modify_result_table_resource_for_es_storage(
    create_or_delete_records, mock_consul, mock_es_client, mocker
):
    """
    测试CreateResultTable接口和ModifyResultTable（日志类型）
    """
    # 请求参数
    params = dict(
        bk_data_id=50010,
        table_id="2_bklog.rt_create",
        table_name_zh="1001_bklog_test",
        is_custom_table=True,
        schema_type="free",
        bk_biz_id="2",
        default_storage=models.ClusterInfo.TYPE_ES,
        # field_list参数中，将读别名放置在对应的option中
        field_list=[
            {
                "field_name": "test_field1",
                "field_type": "float",
                "tag": "metric",
                "description": "",
                "option": {"field_index": 1, "es_type": "text"},
            }
        ],
        query_alias_settings=[{"field_name": "test_field1", "query_alias": "new_field1"}],
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
            },
        },
        operator="admin",
        data_label="1001_bklog_test",
    )

    # 调用CreateResultTable接口
    CreateResultTableResource().request(**params)
    rt = models.ResultTable.objects.get(table_id="2_bklog.rt_create")
    es_rt = models.ESStorage.objects.get(table_id="2_bklog.rt_create")
    assert rt.bk_biz_id == 2

    # mapping_settings是否符合预期
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
        }
    )

    # 是否创建了对应的别名配置记录  原字段:test_field1 读别名: new_field1
    field1_alias = models.ESFieldQueryAliasOption.objects.get(
        field_path="test_field1", query_alias="new_field1", table_id="2_bklog.rt_create"
    )
    assert field1_alias.is_deleted is False

    # 测试别名配置能否正确组装
    field_alias_mappings = es_rt.compose_field_alias_settings()

    expected = {"properties": {"new_field1": {"type": "alias", "path": "test_field1"}}}
    assert field_alias_mappings == expected

    # 测试索引body能否正确组装
    index_body = es_rt.index_body
    expected = {
        'settings': {},
        'mappings': {
            'dynamic_templates': [
                {
                    'strings_as_keywords': {
                        'match_mapping_type': 'string',
                        'mapping': {'norms': 'false', 'type': 'keyword'},
                    }
                }
            ],
            'properties': {
                'bk_agent_id': {},
                'bk_biz_id': {},
                'bk_cloud_id': {},
                'bk_cmdb_level': {},
                'bk_host_id': {},
                'bk_supplier_id': {},
                'bk_target_host_id': {},
                'ip': {},
                'test_field1': {'type': 'text'},
                'new_field1': {'type': 'alias', 'path': 'test_field1'},
                'time': {},
            },
        },
    }
    assert index_body == expected

    es_rt.es_client = mock_es_client
    # 测试能否正常获取激活状态的索引
    activate_index_list = es_rt.get_activate_index_list()
    assert activate_index_list == ['v2_2_bklog_rt_create_20241125_0']

    # 测试mapping配置比对逻辑
    is_same = es_rt.is_mapping_same(index_name='v2_2_bklog_rt_create_20241125_0')
    assert not is_same

    modify_params = dict(
        table_id="2_bklog.rt_create",
        table_name_zh="1001_bklog_test",
        is_custom_table=True,
        schema_type="fix",
        bk_biz_id="2",
        default_storage=models.ClusterInfo.TYPE_ES,
        # field_list参数中，将读别名放置在对应的option中
        field_list=[
            # {
            #     "field_name": "test_field1",
            #     "field_type": "float",
            #     "tag": "metric",
            #     "description": "",
            #     "option": {"field_index": 1, "es_type": "text", "query_alias": "new_field1"},
            # },
            {
                "field_name": "test_field2",
                "field_type": "float",
                "tag": "metric",
                "description": "",
                "option": {"field_index": 1, "es_type": "text"},
            }
        ],
        query_alias_settings=[{"field_name": "test_field2", "query_alias": "new_field2"}],
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
            },
        },
        operator="admin",
        data_label="1001_bklog_test",
    )

    mocker.patch('metadata.models.ESStorage.update_index_and_aliases', return_value=None)
    ModifyResultTableResource().request(**modify_params)

    # 是否创建了对应的字段别名配置  原字段:test_field1 读别名: new_field1

    field1_alias = models.ESFieldQueryAliasOption.objects.get(
        field_path="test_field1", query_alias="new_field1", table_id="2_bklog.rt_create"
    )
    assert field1_alias.is_deleted is True

    field2_alias = models.ESFieldQueryAliasOption.objects.get(
        field_path="test_field2", query_alias="new_field2", table_id="2_bklog.rt_create"
    )
    assert field2_alias.is_deleted is False

    # 测试别名配置能否正确组装
    field_alias_mappings = es_rt.compose_field_alias_settings()

    expected = {"properties": {"new_field2": {"type": "alias", "path": "test_field2"}}}
    assert field_alias_mappings == expected

    # 测试索引body能否正确组装
    index_body = es_rt.index_body
    expected = {
        'settings': {},
        'mappings': {
            'dynamic_templates': [
                {
                    'strings_as_keywords': {
                        'match_mapping_type': 'string',
                        'mapping': {'norms': 'false', 'type': 'keyword'},
                    }
                }
            ],
            'properties': {
                'bk_agent_id': {},
                'bk_biz_id': {},
                'bk_cloud_id': {},
                'bk_cmdb_level': {},
                'bk_host_id': {},
                'bk_supplier_id': {},
                'bk_target_host_id': {},
                'ip': {},
                'test_field2': {'type': 'text'},
                'new_field2': {'type': 'alias', 'path': 'test_field2'},
                'time': {},
            },
        },
    }
    assert index_body == expected

    # 测试mapping配置比对逻辑
    is_same = es_rt.is_mapping_same(index_name='v2_2_bklog_rt_create_20241125_0')
    assert not is_same
