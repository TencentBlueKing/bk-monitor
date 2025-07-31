"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from monitor_web.incident.events.constants import EntityType, IndexType
from core.drf_resource.base import Resource
from monitor_web.incident.events.serializers import EventsSearchSerializer, EventDetailSerializer
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.data_explorer.event import resources as event_resources
from monitor_web.data_explorer.event.serializers import EventTimeSeriesRequestSerializer
from apm_web.event.serializers import EventTimeSeriesRequestSerializer as ApmEventTimeSeriesRequestSerializer
from monitor_web.data_explorer.event.constants import EventSource, EventType
from monitor_web.incident.utils import get_chinese_labels_dict, pascal_to_snake
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from core.drf_resource import api
from typing import Any
import copy


class IncidentEventsSearchResource(Resource):
    """
    故障告警指标查询接口
    支持 Entity 和 Edge 两种类型的事件查询
    """

    # ==================== 配置常量 ====================
    DEFAULT_EXPRESSION = "a"
    DEFAULT_AGGREGATION_METHOD = "SUM"
    DEFAULT_INDEX_FIELD = "_index"
    DEFAULT_GROUP_BY_FIELDS = ["type", "source", "event_name"]

    WHERE_SPECIAL_FILTER_VALUES = ["apm_application_name", "apm_service_name", "apm_service_category", "cluster_id"]

    def __init__(self):
        super().__init__()

    RequestSerializer = EventsSearchSerializer

    # ==================== 数据源映射配置 ====================
    EntityTypeDataSourceMapping = {
        EntityType.BcsPod.value: DataSourceLabel.CUSTOM,
        EntityType.APMService.value: DataSourceLabel.BK_APM,
        EntityType.BkNodeHost.value: DataSourceLabel.CUSTOM,
    }

    EntityTypeDataTypeMapping = {
        EntityType.BcsPod.value: DataTypeLabel.EVENT,
        EntityType.APMService.value: DataTypeLabel.EVENT,
        EntityType.BkNodeHost.value: DataTypeLabel.EVENT,
    }

    # dimension内一些特殊字段需要做映射处理
    WhereSpecialKeyMapping = {
        "inner_ip": "host",
    }

    # ==================== 主要入口方法 ====================
    def perform_request(self, validated_request_data: dict) -> dict:
        """
        执行事件搜索请求，根据IndexType分类处理
        """
        index_info = validated_request_data.get("index_info", {})
        index_type = index_info.get("index_type", "")
        bk_biz_id = validated_request_data.get("bk_biz_id")

        base_response = self._build_base_response(bk_biz_id)

        # 根据IndexType分发到对应的查询处理器
        if index_type == IndexType.ENTITY.value:
            return self._query_entity_events(validated_request_data, base_response)
        elif index_type == IndexType.EDGE.value:
            return self._query_edge_events(validated_request_data, base_response)
        else:
            return base_response

    # ==================== 查询处理器 ====================
    def _query_entity_events(self, validated_request_data: dict, base_response: dict) -> dict:
        """
        查询Entity类型的事件数据
        """
        entity_query_requests = self._build_entity_query_requests(validated_request_data)
        entity_query_response = self._execute_queries(entity_query_requests, base_response)
        return self._format_events_response(entity_query_response, base_response)

    def _query_edge_events(self, validated_request_data: dict, base_response: dict) -> dict:
        """
        查询Edge类型的事件数据
        """
        # TODO: 实现Edge类型的查询逻辑
        edge_query_requests = self._build_edge_query_requests(validated_request_data)
        edge_query_response = self._execute_queries(edge_query_requests, base_response)
        return self._format_events_response(edge_query_response, base_response)

    # ==================== 查询构建器 ====================
    def _build_entity_query_requests(self, validated_request_data: dict) -> list:
        """
        构建Entity类型的查询请求配置
        """
        # 解析请求参数
        index_info = validated_request_data.get("index_info", {})
        entity_type = index_info.get("entity_type", "")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        dimensions_filter = index_info.get("dimensions", {})

        # 获取数据源配置
        data_source_label = self.EntityTypeDataSourceMapping.get(entity_type, "")
        data_type_label = self.EntityTypeDataTypeMapping.get(entity_type, "")

        # 构建基础查询配置
        base_config = self._build_base_query_config(data_source_label, data_type_label, bk_biz_id, start_time, end_time)

        # 应用过滤条件
        self._apply_dimension_filters(base_config, dimensions_filter)

        # 生成多表查询请求
        tables = self._get_tables_by_entity_type(entity_type, bk_biz_id=bk_biz_id, **dimensions_filter)
        requests = []
        for table in tables:
            request_copy = copy.deepcopy(base_config)
            request_copy["query_configs"][0]["table"] = table
            requests.append(request_copy)

        validated_requests = []
        for request in requests:
            if entity_type == EntityType.APMService.value:
                # 针对APM服务类型，需要额外添加app_name和service_name
                serializer = ApmEventTimeSeriesRequestSerializer(data=request)
            else:
                serializer = EventTimeSeriesRequestSerializer(data=request)
            serializer.is_valid()
            validated_requests.append(serializer.validated_data)
        return validated_requests

    def _build_edge_query_requests(self, validated_request_data: dict) -> list:
        """
        构建Edge类型的查询请求配置
        """
        # TODO: 实现Edge类型的查询请求配置
        return []

    def _build_base_query_config(
        self, data_source_label: str, data_type_label: str, bk_biz_id: int, start_time: int, end_time: int
    ) -> dict:
        """
        构建基础查询配置
        """
        return {
            "expression": self.DEFAULT_EXPRESSION,
            "query_configs": [
                {
                    "data_source_label": data_source_label,
                    "data_type_label": data_type_label,
                    "query_string": "*",
                    "where": [],
                    "group_by": self.DEFAULT_GROUP_BY_FIELDS,
                    "filter_dict": {},
                    "metrics": [
                        {
                            "field": self.DEFAULT_INDEX_FIELD,
                            "method": self.DEFAULT_AGGREGATION_METHOD,
                            "alias": self.DEFAULT_EXPRESSION,
                        }
                    ],
                }
            ],
            "bk_biz_id": bk_biz_id,
            "start_time": start_time,
            "end_time": end_time,
        }

    # ==================== 数据源配置器 ====================
    @classmethod
    def _get_bk_data_id_by_cluster_id(cls, cluster_id: str) -> str:
        """
        根据集群ID获取BK_DATA_ID
        """
        if not cluster_id:
            return ""
        cluster_infos: list = api.metadata.list_bcs_cluster_info(cluster_ids=[cluster_id])
        cluster_to_data_id: dict = {
            cluster_info["cluster_id"]: cluster_info["k8s_event_data_id"] for cluster_info in cluster_infos
        }
        return cluster_to_data_id.get(cluster_id, "")

    @classmethod
    def _get_event_prefix_by_table(cls, table: str) -> str:
        """
        根据table名获取事件前缀
        """
        if table == "gse_system_event":
            return "gse_system_event"
        return "bkmonitor_event"

    @classmethod
    def _get_tables_by_entity_type(cls, entity_type: str, **kwargs) -> set[str]:
        """
        根据实体类型获取对应的table名集合
        """
        table_getters = {
            EntityType.BcsPod.value: cls._get_bcs_pod_tables,
            EntityType.APMService.value: cls._get_apm_service_tables,
            EntityType.BkNodeHost.value: cls._get_bk_node_host_tables,
        }

        getter = table_getters.get(entity_type)
        return getter(**kwargs) if getter else set()

    @classmethod
    def _get_bcs_pod_tables(cls, **kwargs) -> set[str]:
        """
        获取BcsPod类型的表名
        """
        bk_biz_id = kwargs.get("bk_biz_id", "")
        bk_data_id = cls._get_bk_data_id_by_cluster_id(kwargs.get("cluster_id", ""))
        if bk_data_id and bk_biz_id:
            return {f"{bk_biz_id}_bkmonitor_event_{bk_data_id}"}
        return set()

    @classmethod
    def _get_apm_service_tables(cls, **kwargs) -> set[str]:
        """
        获取APMService类型的表名
        """
        return {"builtin"}

    @classmethod
    def _get_bk_node_host_tables(cls, **kwargs) -> set[str]:
        """
        获取BkNodeHost类型的表名
        """
        bk_biz_id = kwargs.get("bk_biz_id", "")
        bk_data_id = cls._get_bk_data_id_by_cluster_id(kwargs.get("cluster_id", ""))

        tables = {"gse_system_event"}
        if bk_data_id and bk_biz_id:
            tables.add(f"{bk_biz_id}_bkmonitor_event_{bk_data_id}")
        return tables

    # ==================== 过滤条件处理器 ====================
    def _apply_dimension_filters(self, time_series_request: dict, dimensions_filter: dict) -> None:
        """
        应用维度过滤条件到查询配置
        """
        if not dimensions_filter:
            return

        # 添加Where过滤条件
        where_filters = []
        for key, value in dimensions_filter.items():
            if not value or key in self.WHERE_SPECIAL_FILTER_VALUES:
                continue
            where_filters.append(
                {"key": self.WhereSpecialKeyMapping.get(key, key), "method": "eq", "value": [value], "condition": "and"}
            )
        time_series_request["query_configs"][0]["where"] = where_filters

        # 添加特殊参数
        app_name = dimensions_filter.get("apm_application_name", "")
        apm_service = dimensions_filter.get("apm_service_name", "")
        if app_name:
            time_series_request["app_name"] = app_name
        if apm_service:
            time_series_request["service_name"] = apm_service

    # ==================== 查询执行器 ====================
    def _execute_queries(self, validated_query_requests: list, base_response: dict) -> dict:
        """
        执行查询请求
        """
        events_search_response = base_response

        # 不同数据源的数据统一聚合到响应内
        def _aggregation(req_data: dict[str, Any]):
            query_configs: list[dict] = req_data.get("query_configs", [{}])
            table = query_configs[0].get("table", "")
            resp = event_resources.EventTimeSeriesResource().perform_request(req_data)
            self._format_events_response(resp, events_search_response, table)

        # 并发执行查询
        if validated_query_requests:
            run_threads([InheritParentThread(target=_aggregation, args=(req,)) for req in validated_query_requests])

        return events_search_response

    # ==================== 响应格式化器 ====================
    def _format_events_response(self, time_series_response: dict, base_response: dict, table: str = None) -> dict:
        """
        格式化事件响应数据
        """
        for series_data in time_series_response.get("series", []):
            dimensions = series_data.get("dimensions", {})

            # 跳过无效数据
            if not dimensions.get("event_name"):
                continue

            # 构建事件信息
            event_info = self._build_event_info(dimensions, table)
            event_name = event_info["event_name"]

            # 更新统计信息
            self._update_statistics(base_response, dimensions)

            # 构建序列数据
            series_info = self._build_series_info(series_data)

            # 组装事件数据
            base_response["events"][event_name] = {**event_info, "series": [series_info]}

        return base_response

    @classmethod
    def _build_event_info(cls, dimension: dict, table: str) -> dict:
        """
        构建事件基础信息
        """
        prefix = cls._get_event_prefix_by_table(table)
        event_name = f"{prefix}.{pascal_to_snake(dimension.get('event_name', ''))}"
        return {
            "event_name": event_name,
            "event_alias": event_name,
            "event_source": dimension.get("source", ""),
            "event_level": dimension.get("type", ""),
        }

    def _update_statistics(self, base_response: dict, dimensions: dict) -> None:
        """
        更新统计信息
        """
        source = dimensions.get("source", "")
        event_level = dimensions.get("type", "")

        if event_level in base_response["statistics"]["event_level"]:
            base_response["statistics"]["event_level"][event_level] += 1
        if source in base_response["statistics"]["event_source"]:
            base_response["statistics"]["event_source"][source] += 1

    def _build_series_info(self, series_data: dict) -> dict:
        """
        构建序列数据信息
        """
        return {
            "dimensions": series_data.get("dimensions", {}),
            "target": series_data.get("target", ""),
            "metric_field": series_data.get("metric_field", ""),
            "datapoints": [[datapoint[1], datapoint[0]] for datapoint in series_data.get("datapoints", [])],
            "alias": series_data.get("alias", ""),
            "type": series_data.get("type", ""),
            "dimensions_translation": series_data.get("dimensions_translation", {}),
            "unit": series_data.get("unit", ""),
        }

    # ==================== 响应构建器 ====================
    @classmethod
    def _build_base_response(cls, bk_biz_id: int) -> dict:
        """
        构建基础响应数据
        """
        return {
            "bk_biz_id": bk_biz_id,
            "statistics": {
                "event_source": get_chinese_labels_dict(EventSource),
                "event_level": get_chinese_labels_dict(EventType),
            },
            "events": {},
        }


class IncidentEventsDetailResource(Resource):
    """
    故障告警事件详情查询接口
    """

    def __init__(self):
        super().__init__()

    RequestSerializer = EventDetailSerializer

    def perform_request(self, validated_request_data: dict) -> dict:
        return event_resources.EventTagDetailResource().perform_request(validated_request_data)
