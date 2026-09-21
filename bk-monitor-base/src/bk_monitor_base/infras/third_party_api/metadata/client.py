from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient


class MetadataApiClient(BkApiClient, ABC):
    """
    元数据 API Client
    """

    abstract_class: ClassVar[bool] = True

    module_name: ClassVar[str] = "metadata"

    esb_base_url: ClassVar[str] = ""
    esb_path: ClassVar[str] = ""

    apigw_base_url: ClassVar[str] = "api/bk-monitor/prod/"

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """
        处理响应结果，返回数据部分
        """
        result = super().handle_response(response)
        # metadata API 通常直接返回数据，不需要额外处理
        return result.get("data", result)


class GetLabel(MetadataApiClient):
    """
    获取分类标签（一二级标签）
    """

    action: ClassVar[str] = "get_label"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/list_label/"


class CreateDataId(MetadataApiClient):
    """
    创建监控数据源
    """

    action: ClassVar[str] = "create_data_id"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/create_data_id/"


class CreateResultTable(MetadataApiClient):
    """
    创建监控结果表
    """

    action: ClassVar[str] = "create_result_table"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/create_result_table/"


class ListResultTable(MetadataApiClient):
    """
    查询监控结果表
    """

    action: ClassVar[str] = "list_result_table"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/list_result_table/"


class ModifyResultTable(MetadataApiClient):
    """
    修改监控结果表
    """

    action: ClassVar[str] = "modify_result_table"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/modify_result_table/"


class GetDataId(MetadataApiClient):
    """
    获取监控数据源具体信息
    """

    action: ClassVar[str] = "get_data_id"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_data_id/"


class QueryDataSourceBySpaceUid(MetadataApiClient):
    """
    根据space_uid查询data_source
    """

    action: ClassVar[str] = "query_data_source_by_space_uid"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/query_data_source_by_space_uid/"


class GetResultTable(MetadataApiClient):
    """
    获取监控结果表具体信息
    """

    action: ClassVar[str] = "get_result_table"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_result_table/"


class GetResultTableStorage(MetadataApiClient):
    """
    获取监控结果表存储信息
    """

    action: ClassVar[str] = "get_result_table_storage"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_result_table_storage/"


class GetTsData(MetadataApiClient):
    """
    数据查询
    """

    action: ClassVar[str] = "get_ts_data"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/data_query/get_ts_data/"


class GetEsData(MetadataApiClient):
    """
    ES数据查询
    """

    action: ClassVar[str] = "get_es_data"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/data_query/get_es_data/"


class ModifyDataId(MetadataApiClient):
    """
    修改dataid和dataname的关系
    """

    action: ClassVar[str] = "modify_data_id"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/modify_data_id/"


class CreateResultTableMetricSplit(MetadataApiClient):
    """
    创建一个结果表CMDB拆分
    """

    action: ClassVar[str] = "create_result_table_metric_split"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/create_result_table_metric_split/"


class CreateEventGroup(MetadataApiClient):
    """
    创建事件分组
    """

    action: ClassVar[str] = "create_event_group"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/create_event_group/"


class ModifyEventGroup(MetadataApiClient):
    """
    修改事件分组
    """

    action: ClassVar[str] = "modify_event_group"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/modify_event_group/"


class DeleteEventGroup(MetadataApiClient):
    """
    删除事件分组
    """

    action: ClassVar[str] = "delete_event_group"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/delete_event_group/"


class GetEventGroup(MetadataApiClient):
    """
    获取事件分组
    """

    action: ClassVar[str] = "get_event_group"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_event_group/"


class QueryEventGroup(MetadataApiClient):
    """
    查询事件分组
    """

    action: ClassVar[str] = "query_event_group"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/query_event_group/"


class CreateTimeSeriesGroup(MetadataApiClient):
    """
    创建自定义时序分组
    """

    action: ClassVar[str] = "create_time_series_group"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/create_time_series_group/"


class ModifyTimeSeriesGroup(MetadataApiClient):
    """
    修改自定义时序分组
    """

    action: ClassVar[str] = "modify_time_series_group"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/modify_time_series_group/"


class DeleteTimeSeriesGroup(MetadataApiClient):
    """
    删除自定义时序分组
    """

    action: ClassVar[str] = "delete_time_series_group"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/delete_time_series_group/"


class GetTimeSeriesGroup(MetadataApiClient):
    """
    获取自定义时序分组
    """

    action: ClassVar[str] = "get_time_series_group"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_time_series_group/"


class QueryTimeSeriesGroup(MetadataApiClient):
    """
    查询自定义时序分组
    """

    action: ClassVar[str] = "query_time_series_group"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/query_time_series_group/"


class QueryTagValues(MetadataApiClient):
    """
    查询指定tag/dimension values
    """

    action: ClassVar[str] = "query_tag_values"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/query_tag_values/"


class QueryClusterInfo(MetadataApiClient):
    """
    查询集群信息
    """

    action: ClassVar[str] = "query_cluster_info"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_cluster_info/"


class AccessBkDataByResultTable(MetadataApiClient):
    """
    创建降采样dataflow
    """

    action: ClassVar[str] = "access_bk_data_by_result_table"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/access_bk_data_by_result_table/"


class IsDataLabelExist(MetadataApiClient):
    """
    判断结果表中是否存在指定data_label
    """

    action: ClassVar[str] = "is_data_label_exist"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/is_data_label_exist/"


class CreateDownSampleDataFlow(MetadataApiClient):
    """
    创建降采样dataflow
    """

    action: ClassVar[str] = "create_down_sample_data_flow"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/create_down_sample_data_flow/"


class FullCmdbNodeInfo(MetadataApiClient):
    """
    补充CMDB节点信息（需要保证表中有bk_target_ip、bk_target_cloud_id两个字段）
    """

    action: ClassVar[str] = "full_cmdb_node_info"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/full_cmdb_node_info/"


class CheckOrCreateKafkaStorage(MetadataApiClient):
    """
    检查对应结果表的kafka存储是否存在，不存在则创建
    """

    action: ClassVar[str] = "check_or_create_kafka_storage"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/check_or_create_kafka_storage/"


class RegisterBCSCluster(MetadataApiClient):
    """
    将BCS集群信息注册到metadata，并进行一系列初始化操作
    """

    action: ClassVar[str] = "register_bcs_cluster"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/register_bcs_cluster/"


class ModifyBCSResourceInfo(MetadataApiClient):
    """
    修改bcs的resource内容，通常为调整dataid
    """

    action: ClassVar[str] = "modify_bcs_resource_info"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/modify_bcs_resource_info/"


class ListBCSResourceInfo(MetadataApiClient):
    """
    查询BCS资源信息
    """

    action: ClassVar[str] = "list_bcs_resource_info"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/list_bcs_resource_info/"


class ListBCSClusterInfo(MetadataApiClient):
    """
    查询BCS集群信息
    """

    action: ClassVar[str] = "list_bcs_cluster_info"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/list_bcs_cluster_info/"


class QueryBCSMetrics(MetadataApiClient):
    """
    查询BCS指标
    """

    action: ClassVar[str] = "query_bcs_metrics"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/query_bcs_metrics/"


class EsRoute(MetadataApiClient):
    """
    ES路由
    """

    action: ClassVar[str] = "es_route"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/es_route/"


class KafkaTail(MetadataApiClient):
    """
    Kafka Tail
    """

    action: ClassVar[str] = "kafka_tail"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/kafka_tail/"


class GetTimeSeriesMetrics(MetadataApiClient):
    """
    获取时序指标
    """

    action: ClassVar[str] = "get_time_series_metrics"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_time_series_metrics/"


class ListSpaceTypes(MetadataApiClient):
    """
    查询空间类型列表
    """

    action: ClassVar[str] = "list_space_types"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/list_space_types/"


class ListSpaces(MetadataApiClient):
    """
    查询空间列表
    """

    action: ClassVar[str] = "list_spaces"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/list_spaces/"


class GetSpaceDetail(MetadataApiClient):
    """
    获取空间详情
    """

    action: ClassVar[str] = "get_space_detail"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_space_detail/"


class GetClustersBySpaceUid(MetadataApiClient):
    """
    根据空间UID获取集群信息
    """

    action: ClassVar[str] = "get_clusters_by_space_uid"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_clusters_by_space_uid/"


class ListStickySpaces(MetadataApiClient):
    """
    查询置顶空间列表
    """

    action: ClassVar[str] = "list_sticky_spaces"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/list_sticky_spaces/"


class StickSpace(MetadataApiClient):
    """
    置顶空间
    """

    action: ClassVar[str] = "stick_space"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/stick_space/"


class CreateSpace(MetadataApiClient):
    """
    创建空间
    """

    action: ClassVar[str] = "create_space"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/create_space/"


class QueryDataSource(MetadataApiClient):
    """
    查询数据源
    """

    action: ClassVar[str] = "query_data_source"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/query_data_source/"


class ListClusters(MetadataApiClient):
    """
    查询集群列表
    """

    action: ClassVar[str] = "list_clusters"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/list_clusters/"


class GetStorageClusterDetail(MetadataApiClient):
    """
    获取存储集群详情
    """

    action: ClassVar[str] = "get_storage_cluster_detail"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/get_storage_cluster_detail/"


class RegisterCluster(MetadataApiClient):
    """
    注册集群
    """

    action: ClassVar[str] = "register_cluster"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/register_cluster/"


class UpdateRegisteredCluster(MetadataApiClient):
    """
    更新已注册的集群
    """

    action: ClassVar[str] = "update_registered_cluster"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/update_registered_cluster/"


class QueryResultTableStorageDetail(MetadataApiClient):
    """
    查询结果表存储详情
    """

    action: ClassVar[str] = "query_result_table_storage_detail"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/query_result_table_storage_detail/"


class GetDataLabelsMap(MetadataApiClient):
    """
    获取数据标签映射
    """

    action: ClassVar[str] = "get_data_labels_map"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/get_data_labels_map/"


class ListTransferCluster(MetadataApiClient):
    """
    获取所有transfer集群信息
    """

    action: ClassVar[str] = "list_transfer_cluster"
    method: ClassVar[str] = "GET"
    apigw_path: ClassVar[str] = "app/metadata/list_transfer_cluster/"


class CreateClusterInfo(MetadataApiClient):
    """
    创建存储集群
    """

    action: ClassVar[str] = "create_cluster_info"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/create_cluster_info/"


class ModifyClusterInfo(MetadataApiClient):
    """
    修改存储集群
    """

    action: ClassVar[str] = "modify_cluster_info"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/modify_cluster_info/"


class DeleteClusterInfo(MetadataApiClient):
    """
    删除存储集群
    """

    action: ClassVar[str] = "delete_cluster_info"
    method: ClassVar[str] = "POST"
    apigw_path: ClassVar[str] = "app/metadata/delete_cluster_info/"


# 实例化客户端对象
get_label_client = GetLabel()

get_data_id_client = GetDataId()
create_data_id_client = CreateDataId()
modify_data_id_client = ModifyDataId()
query_data_source_client = QueryDataSource()
query_data_source_by_space_uid_client = QueryDataSourceBySpaceUid()

create_result_table_client = CreateResultTable()
list_result_table_client = ListResultTable()
modify_result_table_client = ModifyResultTable()
get_result_table_client = GetResultTable()
get_result_table_storage_client = GetResultTableStorage()
get_ts_data_client = GetTsData()
get_es_data_client = GetEsData()
create_result_table_metric_split_client = CreateResultTableMetricSplit()

create_event_group_client = CreateEventGroup()
modify_event_group_client = ModifyEventGroup()
delete_event_group_client = DeleteEventGroup()
get_event_group_client = GetEventGroup()
query_event_group_client = QueryEventGroup()

create_time_series_group_client = CreateTimeSeriesGroup()
modify_time_series_group_client = ModifyTimeSeriesGroup()
delete_time_series_group_client = DeleteTimeSeriesGroup()
get_time_series_group_client = GetTimeSeriesGroup()
query_time_series_group_client = QueryTimeSeriesGroup()
get_time_series_metrics_client = GetTimeSeriesMetrics()

query_tag_values_client = QueryTagValues()
query_cluster_info_client = QueryClusterInfo()
access_bk_data_by_result_table_client = AccessBkDataByResultTable()
is_data_label_exist_client = IsDataLabelExist()
create_down_sample_data_flow_client = CreateDownSampleDataFlow()
full_cmdb_node_info_client = FullCmdbNodeInfo()
check_or_create_kafka_storage_client = CheckOrCreateKafkaStorage()
register_bcs_cluster_client = RegisterBCSCluster()
modify_bcs_resource_info_client = ModifyBCSResourceInfo()
list_bcs_resource_info_client = ListBCSResourceInfo()
list_bcs_cluster_info_client = ListBCSClusterInfo()
query_bcs_metrics_client = QueryBCSMetrics()
es_route_client = EsRoute()
kafka_tail_client = KafkaTail()
list_space_types_client = ListSpaceTypes()
list_spaces_client = ListSpaces()
get_space_detail_client = GetSpaceDetail()
get_clusters_by_space_uid_client = GetClustersBySpaceUid()
list_sticky_spaces_client = ListStickySpaces()
stick_space_client = StickSpace()
create_space_client = CreateSpace()
list_clusters_client = ListClusters()
get_storage_cluster_detail_client = GetStorageClusterDetail()
register_cluster_client = RegisterCluster()
update_registered_cluster_client = UpdateRegisteredCluster()
query_result_table_storage_detail_client = QueryResultTableStorageDetail()
get_data_labels_map_client = GetDataLabelsMap()
list_transfer_cluster_client = ListTransferCluster()
create_cluster_info_client = CreateClusterInfo()
modify_cluster_info_client = ModifyClusterInfo()
delete_cluster_info_client = DeleteClusterInfo()
