from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.third_party_api.metadata.api import (
    CreateDataSourceParams,
    GetDataSourceResult,
    ModifyDataSourceParams,
)


def test_create_data_source(requests_mock):
    """
    测试创建数据源
    """
    requests_mock.post(
        "http://bkapi.example.com/api/bk-monitor/prod/app/metadata/create_data_id/",
        json={
            "result": True,
            "data": {
                "bk_data_id": 12345,
            },
        },
    )

    params = CreateDataSourceParams(
        data_name="test_data_source",
        etl_config="bk_standard_v2_time_series",
        source_label="bk_monitor",
        type_label="time_series",
    )

    response: int = api.metadata.create_data_source(bk_tenant_id="system", operator="admin", **params)
    assert response == 12345
    assert isinstance(response, int)


def test_get_data_source_by_id(requests_mock):
    """
    测试通过 bk_data_id 获取数据源
    """
    requests_mock.get(
        "http://bkapi.example.com/api/bk-monitor/prod/app/metadata/get_data_id/",
        json={
            "result": True,
            "data": {
                "bk_data_id": 12345,
                "data_id": 12345,
                "bk_tenant_id": "system",
                "mq_config": {"cluster_id": 1},
                "etl_config": "bk_standard_v2_time_series",
                "option": {},
                "type_label": "time_series",
                "source_label": "bk_monitor",
                "token": "test_token_12345",
                "transfer_cluster_id": "default",
                "data_name": "test_data_source",
                "is_platform_data_id": False,
                "space_type_id": "bkcc",
                "space_uid": "bkcc__2",
                "bk_biz_id": 2,
            },
        },
    )

    response: GetDataSourceResult = api.metadata.get_data_source(bk_tenant_id="system", bk_data_id=12345)
    assert response["bk_data_id"] == 12345
    assert response["data_id"] == 12345
    assert response["data_name"] == "test_data_source"
    assert response["type_label"] == "time_series"
    assert response["source_label"] == "bk_monitor"
    assert response["bk_tenant_id"] == "system"
    assert response["bk_biz_id"] == 2


def test_get_data_source_by_name(requests_mock):
    """
    测试通过 data_name 获取数据源
    """
    requests_mock.get(
        "http://bkapi.example.com/api/bk-monitor/prod/app/metadata/get_data_id/",
        json={
            "result": True,
            "data": {
                "bk_data_id": 12345,
                "data_id": 12345,
                "bk_tenant_id": "system",
                "mq_config": {"cluster_id": 1},
                "etl_config": "bk_standard_v2_time_series",
                "option": {},
                "type_label": "time_series",
                "source_label": "bk_monitor",
                "token": "test_token_12345",
                "transfer_cluster_id": "default",
                "data_name": "test_data_source",
                "is_platform_data_id": False,
                "space_type_id": "bkcc",
                "space_uid": "bkcc__2",
                "bk_biz_id": 2,
            },
        },
    )

    response: GetDataSourceResult = api.metadata.get_data_source(bk_tenant_id="system", data_name="test_data_source")
    assert response["bk_data_id"] == 12345
    assert response["data_name"] == "test_data_source"
    assert response["type_label"] == "time_series"
    assert response["source_label"] == "bk_monitor"


def test_modify_data_source(requests_mock):
    """
    测试修改数据源
    """
    requests_mock.post(
        "http://bkapi.example.com/api/bk-monitor/prod/app/metadata/modify_data_id/",
        json={
            "result": True,
            "data": {
                "bk_data_id": 12345,
                "data_id": 12345,
                "bk_tenant_id": "system",
                "mq_config": {"cluster_id": 1},
                "etl_config": "bk_standard_v2_time_series",
                "option": {"test_option": "test_value"},
                "type_label": "time_series",
                "source_label": "bk_monitor",
                "token": "test_token_12345",
                "transfer_cluster_id": "default",
                "data_name": "modified_data_source",
                "is_platform_data_id": False,
                "space_type_id": "bkcc",
                "space_uid": "bkcc__2",
                "bk_biz_id": 2,
            },
        },
    )

    params: ModifyDataSourceParams = {
        "data_id": 12345,
        "data_name": "modified_data_source",
        "option": {"test_option": "test_value"},
    }

    response: GetDataSourceResult = api.metadata.modify_data_source(bk_tenant_id="system", operator="admin", **params)
    assert response["bk_data_id"] == 12345
    assert response["data_name"] == "modified_data_source"
    assert response["option"] == {"test_option": "test_value"}


def test_full_cmdb_node_info(requests_mock):
    """
    测试补充CMDB节点信息
    """
    requests_mock.post(
        "http://bkapi.example.com/api/bk-monitor/prod/app/metadata/full_cmdb_node_info/",
        json={
            "result": True,
            "data": {
                "table_id": "test_table_123",
                "cmdb_info": {
                    "level": "set",
                    "path": "业务 > 集群1 > 模块1",
                },
                "nodes": [
                    {
                        "bk_inst_id": 1,
                        "bk_inst_name": "test_node_1",
                    }
                ],
            },
        },
    )

    response = api.metadata.full_cmdb_node_info(bk_tenant_id="system", table_id="test_table_123")
    assert response["table_id"] == "test_table_123"
    assert response["cmdb_info"]["level"] == "set"
    assert response["cmdb_info"]["path"] == "业务 > 集群1 > 模块1"
    assert len(response["nodes"]) == 1
    assert response["nodes"][0]["bk_inst_id"] == 1
    assert response["nodes"][0]["bk_inst_name"] == "test_node_1"


def test_create_result_table_metric_split(requests_mock):
    """
    测试创建结果表CMDB拆分
    """
    requests_mock.post(
        "http://bkapi.example.com/api/bk-monitor/prod/app/metadata/create_result_table_metric_split/",
        json={
            "result": True,
            "data": {
                "table_id": "split_table_123",
                "cmdb_level": "set",
                "status": "success",
                "operator": "admin",
            },
        },
    )

    response = api.metadata.create_result_table_metric_split(
        bk_tenant_id="system",
        table_id="split_table_123",
        cmdb_level="set",
        operator="admin",
    )
    assert response["table_id"] == "split_table_123"
    assert response["cmdb_level"] == "set"
    assert response["status"] == "success"
    assert response["operator"] == "admin"
