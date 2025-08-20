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
from monitor_web.data_explorer.event.serializers import (
    EventTimeSeriesRequestSerializer,
    EventTagDetailRequestSerializer,
)
from apm_web.event.serializers import (
    EventTimeSeriesRequestSerializer as ApmEventTimeSeriesRequestSerializer,
    EventTagDetailRequestSerializer as ApmEventTagDetailRequestSerializer,
)
from monitor_web.data_explorer.event.constants import EventSource, EventType
from monitor_web.incident.metrics.utils import transform_to_ip4
from monitor_web.incident.utils import pascal_to_snake
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from core.drf_resource import api
from typing import Any
import copy
import threading


class BaseIncidentEventsResource(Resource):
    """
    故障告警事件查询接口基类
    """

    DEFAULT_EXPRESSION = "a"
    DEFAULT_AGGREGATION_METHOD = "SUM"
    DEFAULT_INDEX_FIELD = "_index"
    DEFAULT_GROUP_BY_FIELDS = ["type", "event_name"]
    DEFAULT_QUERY_STRING = "*"

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

    # 表名与维度过滤条件映射关系
    TableWhereSpecialKeyMapping = {
        "gse_system_event": {
            "inner_ip": "bk_target_ip",
            "bk_cloud_id": "bk_target_cloud_id",
        },
        "bkmonitor_event": {
            "inner_ip": "host",
            "pod_name": "pod",
            "namespace": "namespace",
            "cluster_id": "bcs_cluster_id",
        },
        "cicd_event": {},
    }

    def get_special_keys_by_table(self, table: str) -> list:
        """
        根据表名获取特殊字段
        """
        for table_key, mapping_keys in self.TableWhereSpecialKeyMapping.items():
            if table_key in table:
                return mapping_keys
        return []

    # 表名与事件来源的映射关系
    TableSourceMapping = {
        EventSource.HOST.label: ["gse_system_event"],
        EventSource.BCS.label: ["bkmonitor_event"],
        EventSource.BKCI.label: ["cicd_event"],
        EventSource.DEFAULT.label: ["system_event"],
    }

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()

    # ==================== 数据源配置器 ====================
    @classmethod
    def get_bk_data_id_by_cluster_id(cls, cluster_id: str) -> str:
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
    def get_tables_by_entity_type(cls, entity_type: str, **kwargs) -> set[str]:
        """
        根据实体类型获取对应的table名集合
        """
        table_getters = {
            EntityType.BcsPod.value: cls.get_bcs_pod_tables,
            EntityType.APMService.value: cls.get_apm_service_tables,
            EntityType.BkNodeHost.value: cls.get_bk_node_host_tables,
        }
        getter = table_getters.get(entity_type)
        return getter(**kwargs) if getter else set()

    @classmethod
    def get_bcs_pod_tables(cls, **kwargs) -> set[str]:
        """
        获取BcsPod类型的表名
        """
        tables = {"cicd_event"}
        bk_biz_id = kwargs.get("bk_biz_id", "")
        bk_data_id = cls.get_bk_data_id_by_cluster_id(kwargs.get("cluster_id", ""))
        if bk_data_id and bk_biz_id:
            tables.add(f"{bk_biz_id}_bkmonitor_event_{bk_data_id}")
        return tables

    @classmethod
    def get_apm_service_tables(cls, **kwargs) -> set[str]:
        """
        获取APMService类型的表名
        """
        return {"builtin"}

    @classmethod
    def get_bk_node_host_tables(cls, **kwargs) -> set[str]:
        """
        获取BkNodeHost类型的表名
        """
        bk_biz_id = kwargs.get("bk_biz_id", "")
        bk_data_id = cls.get_bk_data_id_by_cluster_id(kwargs.get("cluster_id", ""))

        tables = {"gse_system_event", "cicd_event"}
        if bk_data_id and bk_biz_id:
            tables.add(f"{bk_biz_id}_bkmonitor_event_{bk_data_id}")
        return tables

    # ==================== 过滤条件处理器 ====================
    def apply_dimension_filters(self, time_series_request: dict, dimensions_filter: dict, table: str) -> None:
        """
        应用维度过滤条件到查询配置
        """
        if not dimensions_filter:
            return

        special_keys = self.get_special_keys_by_table(table)

        # 处理特殊字段
        for key in special_keys:
            if key not in dimensions_filter:
                continue
            if table == "gse_system_event" and key == "inner_ip":
                dimensions_filter[key] = transform_to_ip4(dimensions_filter[key])

        # 添加Where过滤条件
        where_filters = []
        for key, value in dimensions_filter.items():
            if not value or key not in special_keys:
                continue
            where_filters.append(
                {
                    "key": special_keys[key],
                    "method": "eq",
                    "value": [value],
                    "condition": "and",
                }
            )

        # 将where_filters应用到每个query_config
        for query_config in time_series_request["query_configs"]:
            query_config["where"].extend(where_filters)

        # 添加特殊参数
        app_name = dimensions_filter.get("apm_application_name", "")
        apm_service = dimensions_filter.get("apm_service_name", "")
        if app_name:
            time_series_request["app_name"] = app_name
        if apm_service:
            time_series_request["service_name"] = apm_service

    def _get_source_by_table(self, table: str) -> str:
        """
        根据表名获取事件来源
        """
        for source, tables in self.TableSourceMapping.items():
            for mapping_table in tables:
                if mapping_table in table:
                    return source
        return EventSource.DEFAULT.label


class IncidentEventsSearchResource(BaseIncidentEventsResource):
    """
    故障告警指标查询接口
    支持 Entity 和 Edge 两种类型的事件查询
    """

    # ==================== 配置常量 ====================

    def __init__(self):
        super().__init__()

    RequestSerializer = EventsSearchSerializer

    # ==================== 主要入口方法 ====================
    def perform_request(self, validated_request_data: dict) -> dict:
        """
        执行事件搜索请求，根据IndexType分类处理
        """
        index_info = validated_request_data.get("index_info", {})
        index_type = index_info.get("index_type", "")
        bk_biz_id = validated_request_data.get("bk_biz_id")

        base_response = {
            "bk_biz_id": bk_biz_id,
            "statistics": {
                "event_source": {source: 0 for source in EventSource.label_mapping().values()},
                "event_level": {level: 0 for level in EventType.label_mapping().values()},
            },
            "events": {},
        }

        # 根据IndexType分发到对应的查询处理器,仅支持Entity类型的事件查询
        if index_type == IndexType.ENTITY.value:
            return self.query_entity_events(validated_request_data, base_response)
        else:
            return base_response

    # ==================== 查询处理器 ====================
    def query_entity_events(self, validated_request_data: dict, base_response: dict) -> dict:
        """
        查询Entity类型的事件数据
        """
        entity_query_requests = self.build_entity_query_requests(validated_request_data)
        entity_query_response = self.execute_queries(entity_query_requests, base_response)
        return self.format_events_response(entity_query_response, base_response)

    # ==================== 查询构建器 ====================
    def build_entity_query_requests(self, validated_request_data: dict) -> list:
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
        base_config = self.build_base_query_config(data_source_label, data_type_label, bk_biz_id, start_time, end_time)

        # 生成多表查询请求
        tables = self.get_tables_by_entity_type(entity_type, bk_biz_id=bk_biz_id, **dimensions_filter)
        requests = []
        for table in tables:
            request_copy = copy.deepcopy(base_config)
            request_copy["query_configs"][0]["table"] = table
            self.apply_dimension_filters(request_copy, dimensions_filter, table)
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

    def build_base_query_config(
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
                    "query_string": self.DEFAULT_QUERY_STRING,
                    "where": [],
                    "group_by": self.DEFAULT_GROUP_BY_FIELDS,
                    "interval": 3600,
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

    # ==================== 查询执行器 ====================
    def execute_queries(self, validated_query_requests: list, base_response: dict) -> dict:
        """
        执行查询请求
        """
        events_search_response = base_response

        # 不同数据源的数据统一聚合到响应内
        def _aggregation(req_data: dict[str, Any]):
            resp = event_resources.EventTimeSeriesResource().perform_request(req_data)
            query_config: dict = resp.get("query_config", {})
            query_config_list = query_config.get("query_configs", [])
            table = next(iter(query_config_list), {}).get("table", "")
            with self._lock:
                self.format_events_response(resp, events_search_response, table)

        # 并发执行查询
        if validated_query_requests:
            run_threads([InheritParentThread(target=_aggregation, args=(req,)) for req in validated_query_requests])

        return events_search_response

    # ==================== 响应格式化器 ====================
    def format_events_response(self, time_series_response: dict, base_response: dict, table: str = None) -> dict:
        """
        格式化事件响应数据
        """
        for series_data in time_series_response.get("series", []):
            dimensions = series_data.get("dimensions", {})
            datapoints = series_data.get("datapoints", [])
            # 跳过无效数据
            if not dimensions.get("event_name"):
                continue

            # 构建事件信息
            event_info = self.build_event_info(dimensions, table)
            event_name = event_info["event_name"]

            # 更新统计信息
            source = self._get_source_by_table(table)
            event_level = dimensions.get("type", "")
            if event_level in base_response["statistics"]["event_level"]:
                base_response["statistics"]["event_level"][event_level] += 1
            if source in base_response["statistics"]["event_source"]:
                base_response["statistics"]["event_source"][source] += sum(datapoint[0] for datapoint in datapoints)

            # 构建序列数据
            series_info = {
                "dimensions": series_data.get("dimensions", {}),
                "target": series_data.get("target", ""),
                "metric_field": series_data.get("metric_field", ""),
                "datapoints": [[datapoint[1], datapoint[0]] for datapoint in datapoints],
                "alias": series_data.get("alias", ""),
                "type": series_data.get("type", ""),
                "dimensions_translation": series_data.get("dimensions_translation", {}),
                "unit": series_data.get("unit", ""),
            }

            # 组装事件数据
            base_response["events"][event_name] = {**event_info, "series": [series_info]}

        return base_response

    def build_event_info(self, dimension: dict, table: str) -> dict:
        """
        构建事件基础信息
        """
        prefix = "bkmonitor_event" if table != "gse_system_event" else "gse_system_event"
        event_name = f"{prefix}.{pascal_to_snake(dimension.get('event_name', ''))}"
        return {
            "event_name": event_name,
            "event_alias": event_name,
            "event_source": self._get_source_by_table(table),
            "event_level": dimension.get("type", ""),
        }


class IncidentEventsDetailResource(BaseIncidentEventsResource):
    """
    故障告警事件详情查询接口
    """

    def __init__(self):
        super().__init__()

    RequestSerializer = EventDetailSerializer

    def perform_request(self, validated_request_data: dict) -> dict:
        query_request = self.build_tag_detail_request(validated_request_data)
        event_tag_detail_response = event_resources.EventTagDetailResource().perform_request(query_request)
        for value in event_tag_detail_response.values():
            self.build_target_info(value, query_request, validated_request_data)
        return event_tag_detail_response

    def build_tag_detail_request(self, validated_request_data: dict) -> dict:
        """
        构建事件详情查询请求
        """
        index_info: dict = validated_request_data.get("index_info", {})
        entity_type: str = index_info.get("entity_type", "")
        dimensions_filter: dict = index_info.get("dimensions", {})
        bk_biz_id: int = validated_request_data.get("bk_biz_id")
        start_time: int = validated_request_data.get("start_time")
        end_time: int = validated_request_data.get("end_time") or 0
        interval: int = validated_request_data.get("interval", 3600)
        data_source_label: str = self.EntityTypeDataSourceMapping.get(entity_type, "")
        data_type_label: str = self.EntityTypeDataTypeMapping.get(entity_type, "")
        query_request = {
            "expression": self.DEFAULT_EXPRESSION,
            "query_configs": [],
            "bk_biz_id": bk_biz_id,
            "start_time": start_time,
            "end_time": end_time,
        }
        tables = self.get_tables_by_entity_type(entity_type, bk_biz_id=bk_biz_id, **dimensions_filter)
        for table in tables:
            query_request["query_configs"].append(
                {
                    "data_source_label": data_source_label,
                    "data_type_label": data_type_label,
                    "query_string": self.DEFAULT_QUERY_STRING,
                    "where": [{"condition": "and", "key": "type", "method": "eq", "value": ["Normal", "Warning", ""]}],
                    "group_by": [],
                    "filter_dict": {},
                    "table": table,
                    "interval": interval,
                }
            )

        self.apply_dimension_filters(query_request, dimensions_filter, table)

        if entity_type == EntityType.APMService.value:
            serializer = ApmEventTagDetailRequestSerializer(data=query_request)
        else:
            serializer = EventTagDetailRequestSerializer(data=query_request)
        serializer.is_valid()
        query_request = serializer.validated_data
        return query_request

    def build_target_info(self, response: dict, query_request: dict, validated_request_data: dict) -> dict:
        """
        构建目标信息
        """
        index_info: dict = validated_request_data.get("index_info", {})
        index_type: str = index_info.get("index_type", "")
        entity_type: str = index_info.get("entity_type", "")
        entity_name: str = index_info.get("entity_name", "")
        dimensions: dict = index_info.get("dimensions", {})
        query_configs: list[dict] = query_request.get("query_configs", [])
        table: str = query_configs[0].get("table", "") if query_configs else ""

        # total ≤ 20 显示详情列表，否则显示 topk
        total: int = response.get("total", 0)
        event_detail_data = response["list"] if total <= 20 else response["topk"]

        for event_detail in event_detail_data:
            target_info = {
                "target_type": index_type,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "table": table,
                "dimensions": {},
            }
            target_dimensions = target_info["dimensions"]

            # 处理维度映射（优先从 origin_data 中透传）
            special_keys = self.get_special_keys_by_table(table)
            for key, value in dimensions.items():
                if key in special_keys:
                    target_dimensions[special_keys[key]] = value

            origin_data: dict = event_detail.get("origin_data", {})
            for key, value in origin_data.items():
                if key.startswith("dimensions."):
                    target_dimensions[key.split(".", 1)[1]] = value

            event_name = event_detail.get("event_name", {})
            target_info["event_name"] = event_name.get("value", "")

            app_name = dimensions.get("apm_application_name", "")
            if app_name:
                target_dimensions["app_name"] = app_name
            service_name = dimensions.get("apm_service_name", "")
            if service_name:
                target_dimensions["service_name"] = service_name

            event_detail["target_info"] = target_info
