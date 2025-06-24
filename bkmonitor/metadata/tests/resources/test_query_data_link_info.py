import json
import logging
import pytest
from unittest import mock
from metadata.resources.bkdata_link import QueryDataLinkInfoResource
from metadata.models import DataSource
from metadata import models

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
def test_data_source_not_exist(mocker):
    """测试数据源不存在的情况"""
    mocker.patch("metadata.models.DataSource.objects.get", side_effect=models.DataSource.DoesNotExist)
    resource = QueryDataLinkInfoResource()
    with pytest.raises(Exception) as exc_info:
        resource.perform_request({"bk_data_id": 9999})
    assert "数据源ID 9999 不存在" in str(exc_info.value)


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
    # 验证不包含的信息
    assert "etl_infos" not in result_data
    assert "authorized_space_uids" not in result_data
    assert "expired_metrics" not in result_data
    assert "rt_detail_router" not in result_data
    assert "space_to_result_table_router_infos" not in result_data


@pytest.mark.django_db(databases=["monitor_api"])
def test_query_with_exception(mocker, mock_data_source):
    """测试查询过程中出现异常的情况"""
    resource = QueryDataLinkInfoResource()

    # 模拟查询过程中抛出异常
    mocker.patch("metadata.models.DataSource.objects.get", side_effect=Exception("Test exception"))

    with pytest.raises(Exception) as exc_info:
        resource.perform_request({"bk_data_id": mock_data_source.bk_data_id})
    # 验证错误信息格式是否匹配实际抛出的格式
    assert "查询数据链路信息失败" in str(exc_info.value)
