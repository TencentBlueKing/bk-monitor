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
import logging
import pytest
from unittest import mock
from metadata.resources.bkdata_link import QueryDataLinkInfoResource
from metadata.models import DataSource

logger = logging.getLogger("metadata")


@pytest.fixture
def mock_data_source():
    """创建模拟数据源"""
    ds = mock.MagicMock(spec=DataSource)
    ds.bk_data_id = 1001
    ds.data_name = "test_data"
    ds.etl_config = "bk_standard_v2_time_series"
    ds.is_enable = True
    ds.is_platform_data_id = False
    ds.created_from = "bkdata"
    ds.mq_cluster_id = 1
    ds.mq_config_id = 1
    ds.source_system = "bkmonitor"
    ds.transfer_cluster_id = "default"
    ds.consul_config_path = "metadata/test/data_id/1001"
    return ds


@pytest.mark.django_db(databases=["monitor_api"])
def test_complete_info_query(mocker, mock_data_source):
    """测试is_complete为True时完整信息查询"""
    resource = QueryDataLinkInfoResource()
    result = resource.perform_request({"bk_data_id": mock_data_source.bk_data_id, "is_complete": True})

    # 验证返回的是有效的JSON字符串
    assert isinstance(result, str)
    result_data = json.loads(result)
    assert "ds_infos" in result_data
    assert "rt_infos" in result_data
    assert "es_storage_infos" in result_data
    assert "bkbase_infos" in result_data
    assert "etl_infos" in result_data
    assert "authorized_space_uids" in result_data
    assert "expired_metrics" in result_data
    assert "rt_detail_router" in result_data
    assert "space_to_result_table_router_infos" in result_data


@pytest.mark.django_db(databases=["monitor_api"])
def test_basic_info_query(mocker, mock_data_source):
    """测试is_complete为False时基础信息查询"""
    resource = QueryDataLinkInfoResource()
    result = resource.perform_request({"bk_data_id": mock_data_source.bk_data_id, "is_complete": False})

    # 验证返回的是有效的JSON字符串
    assert isinstance(result, str)
    result_data = json.loads(result)
    assert "ds_infos" in result_data
    assert "rt_infos" in result_data
    assert "es_storage_infos" in result_data
    assert "bkbase_infos" in result_data
    assert "etl_infos" in result_data
    # 验证不包含的信息
    assert "authorized_space_uids" not in result_data
    assert "expired_metrics" not in result_data
    assert "rt_detail_router" not in result_data
    assert "space_to_result_table_router_infos" not in result_data


@pytest.mark.django_db(databases=["monitor_api"])
def test_query_with_exception(mocker, mock_data_source):
    """测试查询过程中出现异常的情况"""
    resource = QueryDataLinkInfoResource()
    result = resource.perform_request({"bk_data_id": 9999})
    # 验证错误信息格式是否匹配实际抛出的格式
    assert isinstance(result, str)
    result_data = json.loads(result)
    assert "ds_infos" not in result_data
    assert "rt_infos" not in result_data
    assert "es_storage_infos" not in result_data
    assert "bkbase_infos" not in result_data
    assert "etl_infos" not in result_data
    assert "authorized_space_uids" not in result_data
    assert "expired_metrics" not in result_data
    assert "rt_detail_router" not in result_data
    assert "space_to_result_table_router_infos" not in result_data
    # 验证报错返回信息
    assert "error_info" in result
