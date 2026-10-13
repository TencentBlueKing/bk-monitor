from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.config import get_config
from bk_monitor_base.infras.third_party_api.api_client import BkApiClient


class BkDataApiClient(BkApiClient, ABC):
    """
    BKDATA API Client
    """

    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "bkdata"
    esb_base_url: ClassVar[str] = ""
    apigw_base_url: ClassVar[str] = "api/bk-base/prod/"
    timeout: ClassVar[int] = 5 * 60

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        return super().handle_response(response).get("data")


class NotifyLogDataIdChanged(BkDataApiClient):
    """
    通知计算平台数据源变更
    """

    action: ClassVar[str] = "notify_log_dataid_changed"
    method: ClassVar[str] = "PUT"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v4/tmp/notify_log_dataid_changed/"


class ApplyDataLink(BkDataApiClient):
    """
    申请数据链路
    """

    action: ClassVar[str] = "apply_data_link"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v4/apply/"


class GetBkbaseRawDataWithDataId(BkDataApiClient):
    """
    获取计算平台对应的data_id的raw_data信息，适用于获取V3链路迁移至V4链路后的data_name
    """

    action: ClassVar[str] = "get_bkbase_raw_data_with_data_id"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/access/rawdata/{bkbase_data_id}/"


class DeleteDataLink(BkDataApiClient):
    """
    删除数据链路
    """

    action: ClassVar[str] = "delete_data_link"
    method: ClassVar[str] = "DELETE"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = (
        "v4/tenants/{bk_tenant_id}/namespaces/{namespace}/{kind}/{name}/"
        if get_config().blueking.enable_multi_tenancy
        else "v4/namespaces/{namespace}/{kind}/{name}/"
    )


class AuthProjectsDataCheck(BkDataApiClient):
    """
    检查项目是否有结果表权限
    """

    action: ClassVar[str] = "auth_projects_data_check"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/auth/projects/{project_id}/data/check/"


class AuthResultTable(BkDataApiClient):
    """
    授权接口(管理员接口): 给项目加表权限
    """

    action: ClassVar[str] = "auth_result_table"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/auth/projects/{project_id}/data/add/"


class BatchAuthResultTable(BkDataApiClient):
    """
    批量授权接口(管理员接口): 给项目加表权限
    """

    action: ClassVar[str] = "batch_auth_result_table"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/auth/projects/{project_id}/data/batch_add/"


class QueryAuthProjectsData(BkDataApiClient):
    """
    批量检查项目是否有结果表权限
    """

    action: ClassVar[str] = "query_auth_projects_data"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/auth/projects/{project_id}/data/batch_check/"


class AccessDeployPlan(BkDataApiClient):
    """
    提交接入部署计划(数据源接入)
    """

    action: ClassVar[str] = "access_deploy_plan"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/access/deploy_plan/"


class GetDatabusCleans(BkDataApiClient):
    """
    获取数据清洗信息列表
    """

    action: ClassVar[str] = "get_databus_cleans"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/databus/cleans/"


class QueryMetricAndDimension(BkDataApiClient):
    """
    查询指标和维度
    """

    action: ClassVar[str] = "query_metric_and_dimension"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v4/dd/"


class DatabusCleans(BkDataApiClient):
    """
    接入数据清洗
    """

    action: ClassVar[str] = "data_bus_cleans"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/databus/cleans/"


class ListDataLink(BkDataApiClient):
    """
    拉取计算平台V4资源列表
    """

    action: ClassVar[str] = "list_data_bus_raw_data"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = (
        "v4/tenants/{bk_tenant_id}/namespaces/{namespace}/{kind}/"
        if (get_config().blueking.enable_multi_tenancy)
        else "v4/namespaces/{namespace}/{kind}/"
    )


class StartDatabusCleans(BkDataApiClient):
    """
    启动清洗配置
    """

    action: ClassVar[str] = "start_databus_cleans"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/databus/tasks/"


class GetDataLink(BkDataApiClient):
    """
    获取数据链路
    """

    action: ClassVar[str] = "get_data_link"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = (
        "v4/tenants/{bk_tenant_id}/namespaces/{namespace}/{kind}/{name}/"
        if (get_config().blueking.enable_multi_tenancy)
        else "v4/namespaces/{namespace}/{kind}/{name}/"
    )


class BulkListResultTable(BkDataApiClient):
    """
    按照业务ID批量拉取计算平台结果表元信息
    """

    action: ClassVar[str] = "bulk_list_result_table"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/meta/result_tables/"


class DeleteDataFlow(BkDataApiClient):
    """
    删除DataFlow
    """

    action: ClassVar[str] = "delete_data_flow"
    method: ClassVar[str] = "DELETE"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/"


class GetKafkaInfo(BkDataApiClient):
    """
    查询计算平台使用的 kafka 信息
    """

    action: ClassVar[str] = "get_kafka_info"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/databus/bkmonitor/"


class GetLatestDeployDataFlow(BkDataApiClient):
    """
    获取DataFlow的最近部署信息
    """

    action: ClassVar[str] = "get_latest_deploy_data_flow"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/latest_deploy_data/"


class GetResultTable(BkDataApiClient):
    """
    查询指定结果表
    """

    action: ClassVar[str] = "get_result_table"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/meta/result_tables/{result_table_id}"


class StartDataFlow(BkDataApiClient):
    """
    启动 DataFlow
    """

    action: ClassVar[str] = "start_data_flow"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/start/"


class StopDataFlow(BkDataApiClient):
    """
    停止DataFlow
    """

    action: ClassVar[str] = "stop_data_flow"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/stop/"


class StopDatabusCleans(BkDataApiClient):
    """
    停止清洗配置
    """

    action: ClassVar[str] = "stop_databus_cleans"
    method: ClassVar[str] = "DELETE"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/databus/tasks/{result_table_id}/"


class TailKafkaData(BkDataApiClient):
    """
    计算平台Kafka采样接口
    """

    action: ClassVar[str] = "tail_kafka_data"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = (
        "v4/tenants/{bk_tenant_id}/namespaces/{namespace}/dataids/{name}/tail_kafka/"
        if get_config().blueking.enable_multi_tenancy
        else "v4/namespaces/{namespace}/dataids/{name}/tail_kafka/"
    )


class ApplyDataFlow(BkDataApiClient):
    """
    创建计算平台流程
    """

    action: ClassVar[str] = "apply_data_flow"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/create/"


class CreateDataHub(BkDataApiClient):
    """
    数据接入及存储
    """

    action: ClassVar[str] = "create_data_hub"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/datahub/hubs/"


class CreateDataStorages(BkDataApiClient):
    """
    创建数据入库
    """

    action: ClassVar[str] = "create_data_storages"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/databus/data_storages/"


class UpdateDatabusCleans(BkDataApiClient):
    """
    更新数据清洗
    """

    action: ClassVar[str] = "update_databus_cleans"
    method: ClassVar[str] = "PUT"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/databus/cleans/{processing_id}/"


class UpdateDataFlowNode(BkDataApiClient):
    """
    更新DataFlow节点
    """

    action: ClassVar[str] = "update_data_flow_node"
    method: ClassVar[str] = "PUT"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/nodes/{node_id}/"


class AddDataFlowNode(BkDataApiClient):
    """
    添加DataFlow节点
    """

    action: ClassVar[str] = "add_data_flow_node"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/nodes/"


class GetSceneServicePlan(BkDataApiClient):
    """
    获取场景服务详情
    """

    action: ClassVar[str] = "get_scene_service_plan"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/aiops/scene_service/plans/{plan_id}/"


class GetReleaseModelInfo(BkDataApiClient):
    """
    获取模型详情信息
    """

    action: ClassVar[str] = "get_release_model_info"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/model/releases/{model_release_id}/"


class GetDataFlowList(BkDataApiClient):
    """
    获取DataFlow列表信息
    """

    action: ClassVar[str] = "get_data_flow_list"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/"


class GetDataFlow(BkDataApiClient):
    """
    获取DataFlow信息
    """

    action: ClassVar[str] = "get_data_flow"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/"


class GetDataFlowGraph(BkDataApiClient):
    """
    获取DataFlow里的画布信息,即画布中的节点信息
    """

    action: ClassVar[str] = "get_data_flow_graph"
    method: ClassVar[str] = "GET"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/graph/"


class CreateDataFlow(BkDataApiClient):
    """
    创建DataFlow
    """

    action: ClassVar[str] = "create_data_flow"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/"


class RestartDataFlow(BkDataApiClient):
    """
    重启DataFlow
    """

    action: ClassVar[str] = "restart_data_flow"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = ""
    apigw_path: ClassVar[str] = "v3/dataflow/flow/flows/{flow_id}/restart/"


notify_log_data_id_changed_client = NotifyLogDataIdChanged()
apply_data_link_client = ApplyDataLink()
get_bkbase_raw_data_with_data_id_client = GetBkbaseRawDataWithDataId()
delete_data_link_client = DeleteDataLink()
auth_projects_data_check_client = AuthProjectsDataCheck()
auth_result_table_client = AuthResultTable()
batch_auth_result_table_client = BatchAuthResultTable()
query_auth_projects_data_client = QueryAuthProjectsData()
access_deploy_plan_client = AccessDeployPlan()
get_databus_cleans_client = GetDatabusCleans()
query_metric_and_dimension_client = QueryMetricAndDimension()
databus_cleans_client = DatabusCleans()
list_data_link_client = ListDataLink()
start_databus_cleans_client = StartDatabusCleans()
get_data_link_client = GetDataLink()
bulk_list_result_table_client = BulkListResultTable()
delete_data_flow_client = DeleteDataFlow()
get_kafka_info_client = GetKafkaInfo()
get_latest_deploy_data_flow_client = GetLatestDeployDataFlow()
get_result_table_client = GetResultTable()
start_data_flow_client = StartDataFlow()
stop_data_flow_client = StopDataFlow()
stop_databus_cleans_client = StopDatabusCleans()
tail_kafka_data_client = TailKafkaData()
apply_data_flow_client = ApplyDataFlow()
create_data_hub_client = CreateDataHub()
create_data_storages_client = CreateDataStorages()
update_databus_cleans_client = UpdateDatabusCleans()
update_data_flow_node_client = UpdateDataFlowNode()
add_data_flow_node_client = AddDataFlowNode()
get_scene_service_plan_client = GetSceneServicePlan()
get_release_model_info_client = GetReleaseModelInfo()
get_data_flow_list_client = GetDataFlowList()
get_data_flow_client = GetDataFlow()
get_data_flow_graph_client = GetDataFlowGraph()
create_data_flow_client = CreateDataFlow()
restart_data_flow_client = RestartDataFlow()
