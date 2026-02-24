"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from apm_web.event.resources import EventTimeSeriesResource
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from monitor_web.data_explorer.event.constants import EventSource, EventType
from monitor_web.incident.metrics.utils import transform_to_ip4
from monitor_web.incident.utils import pascal_to_snake
from monitor_web.data_explorer.event.utils import get_data_labels_map
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from bkmonitor.utils.request import get_request_username
from core.drf_resource.exceptions import record_exception
from core.drf_resource import api
from typing import Any
import copy
import abc
import threading
import re


BCS_TABLE_PATTERN = re.compile(r"^\d+_bkmonitor_event_\d+$")


class BaseIncidentEventsResource(Resource, abc.ABC):
    """
    故障告警事件查询接口基类
    """

    @abc.abstractmethod
    def _perform_request(self, validated_request_data: dict[str, Any]):
        pass

    def perform_request(self, validated_request_data: dict[str, Any]):
        try:
            return self._perform_request(validated_request_data)
        except Exception as exc:
            span = trace.get_current_span()
            span.set_attribute("user.username", get_request_username())
            span.set_status(
                Status(
                    status_code=StatusCode.ERROR,
                    description=f"{type(exc).__name__}: {exc}",
                )
            )
            record_exception(span, exc, out_limit=10)
            return {}

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
        "cicd_event": {
            "bk_biz_id": "bk_biz_id",
        },
        "builtin": {},
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
        EventSource.HOST.label: ["gse_system_event", "system_event"],
        EventSource.BCS.label: ["bkmonitor_event"],
        EventSource.BKCI.label: ["cicd_event"],
        EventSource.DEFAULT.label: ["builtin"],
    }

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()

    # ==================== 数据源配置器 ====================
    def get_origin_table(self, bk_biz_id: int, table: str) -> str:
        """
        获取原始表名，无结果代表本来就是原始表名
        """
        data_labels_map = get_data_labels_map(bk_biz_id, [table])
        for key, value in data_labels_map.items():
            if value == table:
                return key
        return table

    def get_bk_data_id_by_cluster_id(self, cluster_id: str) -> str:
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

    def get_tables_by_entity_type(self, entity_type: str, **kwargs) -> set[str]:
        """
        根据实体类型获取对应的table名集合
        """
        table_getters = {
            EntityType.BcsPod.value: self.get_bcs_pod_tables,
            EntityType.APMService.value: self.get_apm_service_tables,
            EntityType.BkNodeHost.value: self.get_bk_node_host_tables,
        }
        getter = table_getters.get(entity_type)
        return getter(**kwargs) if getter else set()

    def get_bcs_pod_tables(self, **kwargs) -> set[str]:
        """
        获取BcsPod类型的表名
        """
        tables = {"cicd_event"}
        bk_biz_id = kwargs.get("bk_biz_id", "")
        bk_data_id = self.get_bk_data_id_by_cluster_id(kwargs.get("cluster_id", ""))
        if bk_data_id and bk_biz_id:
            tables.add(f"{bk_biz_id}_bkmonitor_event_{bk_data_id}")
        return tables

    def get_apm_service_tables(self, **kwargs) -> set[str]:
        """
        获取APMService类型的表名
        """
        return {"builtin"}

    def get_bk_node_host_tables(self, **kwargs) -> set[str]:
        """
        获取BkNodeHost类型的表名
        """
        bk_biz_id = kwargs.get("bk_biz_id", "")
        bk_data_id = self.get_bk_data_id_by_cluster_id(kwargs.get("cluster_id", ""))

        tables = {"gse_system_event", "cicd_event"}
        if bk_data_id and bk_biz_id:
            tables.add(f"{bk_biz_id}_bkmonitor_event_{bk_data_id}")
        return tables

    def process_dimensions_keys_by_table(self, table: str, dimensions_filter: dict, keys: list[str], **kwargs) -> dict:
        """
        根据表名处理dimensions对应key的过滤条件,并返回处理后的dimensions
        """
        if not dimensions_filter:
            return
        dimensions = copy.deepcopy(dimensions_filter)
        for key in keys:
            if table == "gse_system_event":
                match key:
                    case "inner_ip":
                        # 主机系统事件：inner_ip 为 node-x-x-x-x 需转换为 IPv4
                        dimensions[key] = transform_to_ip4(dimensions[key])
            elif table == "cicd_event":
                match key:
                    case "bk_biz_id":
                        # 流水线事件：bk_biz_id 为空，需透传bk_biz_id
                        dimensions[key] = kwargs.get("bk_biz_id", "")
        return dimensions

    # ==================== 过滤条件处理器 ====================
    def apply_dimension_filters_by_table(self, query_config: dict, dimensions_filter: dict, bk_biz_id: int) -> None:
        """
        应用维度过滤条件到查询配置
        """
        if not dimensions_filter:
            return

        table = query_config["table"]
        special_keys = self.get_special_keys_by_table(table)

        processed_dimensions = self.process_dimensions_keys_by_table(
            table, dimensions_filter, special_keys, bk_biz_id=bk_biz_id
        )

        # 添加Where过滤条件
        where_filters = []
        for key, value in processed_dimensions.items():
            where_key = special_keys.get(key, None)
            if not where_key or value is None:
                continue
            where_filters.append(
                {
                    "key": where_key,
                    "method": "eq",
                    "value": [value],
                    "condition": "and",
                }
            )
        query_config["where"].extend(where_filters)

    def _get_source_by_table(self, table: str) -> str:
        """
        根据表名获取事件来源
        """
        table_str = str(table or "")
        for source, tables in self.TableSourceMapping.items():
            for mapping_table in tables:
                if mapping_table == "bkmonitor_event":
                    if BCS_TABLE_PATTERN.match(table_str):
                        return source
                else:
                    if table_str == mapping_table:
                        return source
        return EventSource.DEFAULT.label

    def _get_tables_by_sources(self, sources: list[str]) -> set[str]:
        """
        根据事件来源获取表名
        """
        tables = set()
        for source, mapping_tables in self.TableSourceMapping.items():
            if source in sources:
                tables.update(mapping_tables)
        return tables

    def build_base_query_config(self, validated_request_data: dict) -> dict:
        """
        构建基础查询配置
        """
        index_info = validated_request_data.get("index_info", {})
        dimensions_filter = index_info.get("dimensions", {})
        bk_biz_id = validated_request_data.get("bk_biz_id")
        start_time = validated_request_data.get("start_time", 0)
        end_time = validated_request_data.get("end_time", 0)
        base_query = {
            "expression": self.DEFAULT_EXPRESSION,
            "query_configs": [],
            "bk_biz_id": bk_biz_id,
            "start_time": start_time or 0,
            "end_time": end_time or 0,
        }

        app_name = dimensions_filter.get("apm_application_name", "")
        apm_service = dimensions_filter.get("apm_service_name", "")
        if app_name:
            base_query["app_name"] = app_name
        if apm_service:
            base_query["service_name"] = apm_service

        return base_query


class IncidentEventsSearchResource(BaseIncidentEventsResource):
    """
    故障告警指标查询接口
    支持 Entity 和 Edge 两种类型的事件查询
    """

    def __init__(self):
        super().__init__()

    RequestSerializer = EventsSearchSerializer

    def _perform_request(self, validated_request_data: dict) -> dict:
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

    def query_entity_events(self, validated_request_data: dict, base_response: dict) -> dict:
        """
        查询Entity类型的事件数据
        """
        entity_query_requests = self.build_entity_query_requests(validated_request_data)
        entity_query_response = self.execute_queries(entity_query_requests, base_response)
        return self.format_events_response(entity_query_response, base_response)

    def build_entity_query_requests(self, validated_request_data: dict) -> list:
        """
        构建Entity类型的查询请求配置
        """
        # 解析请求参数
        index_info = validated_request_data.get("index_info", {})
        entity_type = index_info.get("entity_type", "")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        dimensions_filter = index_info.get("dimensions", {})
        interval = validated_request_data.get("interval", 3600)
        # 获取数据源配置
        data_source_label = self.EntityTypeDataSourceMapping.get(entity_type, "")
        data_type_label = self.EntityTypeDataTypeMapping.get(entity_type, "")

        # 生成多表查询请求
        tables = self.get_tables_by_entity_type(entity_type, bk_biz_id=bk_biz_id, **dimensions_filter)
        requests = []
        for table in tables:
            query_config = {
                "data_source_label": data_source_label,
                "data_type_label": data_type_label,
                "query_string": self.DEFAULT_QUERY_STRING,
                "where": [],
                "table": table,
                "group_by": self.DEFAULT_GROUP_BY_FIELDS,
                "interval": interval,
                "filter_dict": {},
                "metrics": [
                    {
                        "field": self.DEFAULT_INDEX_FIELD,
                        "method": self.DEFAULT_AGGREGATION_METHOD,
                        "alias": self.DEFAULT_EXPRESSION,
                    }
                ],
            }
            self.apply_dimension_filters_by_table(query_config, dimensions_filter, bk_biz_id)
            base_config = self.build_base_query_config(validated_request_data)
            base_config["query_configs"].append(query_config)
            requests.append(base_config)
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

    def execute_queries(self, validated_query_requests: list, base_response: dict) -> dict:
        """
        执行查询请求
        """
        events_search_response = base_response

        # 不同数据源的数据统一聚合到响应内
        def _aggregation(req_data: dict[str, Any]):
            if any(x['data_source_label'] == DataSourceLabel.BK_APM for x in req_data['query_configs']):
                resp = EventTimeSeriesResource().perform_request(req_data)
            else:
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
            event_name = event_info["event_name"] + "." + event_info["event_level"]

            # 更新统计信息
            source = self._get_source_by_table(table)
            event_level = dimensions.get("type", "")
            total = sum(datapoint[0] for datapoint in datapoints)
            if event_level in base_response["statistics"]["event_level"]:
                base_response["statistics"]["event_level"][event_level] += total
            if source in base_response["statistics"]["event_source"]:
                base_response["statistics"]["event_source"][source] += total

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
        table_str = str(table or "")
        # BCS: {number}_bkmonitor_event_{number}，其他表精确匹配
        prefix = "bkmonitor_event" if BCS_TABLE_PATTERN.match(table_str) else table_str
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

    def _perform_request(self, validated_request_data: dict) -> dict:
        query_request = self.build_tag_detail_request(validated_request_data)
        event_tag_detail_response = event_resources.EventTagDetailResource().perform_request(query_request)
        for value in event_tag_detail_response.values():
            if isinstance(value, dict):
                self.build_target_info(value, query_request, validated_request_data)
        return event_tag_detail_response

    def get_type_filters(self, index_info: dict) -> list[str]:
        """
        获取事件类型过滤条件
        """
        type_filters: list[str] = index_info.get("type_filter", [])
        for i, type_filter in enumerate(type_filters):
            if type_filter == "Default":
                type_filters[i] = ""
        if type_filters:
            return type_filters
        return ["Normal", "Warning", ""]

    def get_source_filters(self, index_info: dict) -> list[str]:
        """
        获取事件来源过滤条件
        """
        source_filters: list[str] = index_info.get("source_filter", [])
        for source in source_filters:
            if source not in EventSource.label_mapping().values():
                source_filters.remove(source)
        if source_filters:
            return source_filters
        return EventSource.label_mapping().values()

    def build_tag_detail_request(self, validated_request_data: dict) -> dict:
        """
        构建事件详情查询请求
        """
        index_info: dict = validated_request_data.get("index_info", {})
        entity_type: str = index_info.get("entity_type", "")
        dimensions_filter: dict = index_info.get("dimensions", {})
        bk_biz_id: int = validated_request_data.get("bk_biz_id")
        interval: int = validated_request_data.get("interval", 3600)
        data_source_label: str = self.EntityTypeDataSourceMapping.get(entity_type, "")
        data_type_label: str = self.EntityTypeDataTypeMapping.get(entity_type, "")
        type_filters = self.get_type_filters(index_info)
        source_filters = self.get_source_filters(index_info)

        filter_tables = self._get_tables_by_sources(source_filters)
        tables = self.get_tables_by_entity_type(entity_type, bk_biz_id=bk_biz_id, **dimensions_filter)
        detail_query_request = self.build_base_query_config(validated_request_data)
        for table in tables:
            if not any(filter_table in table for filter_table in filter_tables):
                continue
            query_config = {
                "data_source_label": data_source_label,
                "data_type_label": data_type_label,
                "query_string": self.DEFAULT_QUERY_STRING,
                "where": [{"condition": "and", "key": "type", "method": "eq", "value": type_filters}],
                "group_by": [],
                "table": table,
                "filter_dict": {},
                "interval": interval,
            }
            self.apply_dimension_filters_by_table(query_config, dimensions_filter, bk_biz_id)
            detail_query_request["query_configs"].append(query_config)
        if entity_type == EntityType.APMService.value:
            serializer = ApmEventTagDetailRequestSerializer(data=detail_query_request)
        else:
            serializer = EventTagDetailRequestSerializer(data=detail_query_request)
        serializer.is_valid()
        detail_query_request = serializer.validated_data
        return detail_query_request

    def _select_table_by_source(self, source: str, tables: list[str]) -> str:
        """
        根据事件来源选择表名
        """
        # BCS: 物理表为 {bk_biz_id}_bkmonitor_event_{bk_data_id}，其余来源使用全量匹配
        if source == EventSource.BCS.label:
            for table in tables:
                if BCS_TABLE_PATTERN.match(str(table or "")):
                    return table
            return ""
        # 非 BCS：按映射列表做精确匹配
        mapping_tables = set(self._get_tables_by_sources([source]))
        for table in tables:
            if str(table or "") in mapping_tables:
                return table
        return ""

    def build_target_info(self, response: dict, query_request: dict, validated_request_data: dict) -> dict:
        """
        构建目标信息
        """
        query_configs = query_request.get("query_configs", [])
        tables = [query_config.get("table", "") for query_config in query_configs]
        bk_biz_id: int = validated_request_data.get("bk_biz_id")
        start_time: int = validated_request_data.get("start_time", 0) * 1000  # 时间戳转毫秒，对齐透传过来的时间戳
        index_info: dict = validated_request_data.get("index_info", {})
        index_type: str = index_info.get("index_type", "")
        entity_type: str = index_info.get("entity_type", "")
        entity_name: str = index_info.get("entity_name", "")
        dimensions: dict = index_info.get("dimensions", {})
        # total ≤ 20 显示详情列表，否则显示 topk
        total: int = response.get("total", 0)
        event_detail_data = response.get("list", []) if total <= 20 else response.get("topk", [])

        for event_detail in event_detail_data:
            source_dict = event_detail.get("source", {})
            source = source_dict.get("value", "")
            source_label = EventSource.label_mapping().get(source, "")
            now_table = self._select_table_by_source(source_label, tables)
            origin_table = self.get_origin_table(bk_biz_id, now_table)
            target_info = {
                "target_type": index_type,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "table": origin_table,
                "dimensions": {},
            }
            target_dimensions = target_info["dimensions"]

            # 处理维度映射（基于表规则的受控映射）
            special_keys = self.get_special_keys_by_table(now_table)
            processed_dimensions = self.process_dimensions_keys_by_table(
                now_table, dimensions, special_keys, bk_biz_id=bk_biz_id
            )
            for key, value in processed_dimensions.items():
                if key in special_keys:
                    target_dimensions[special_keys[key]] = value

            event_name = event_detail.get("event_name", {})
            target_info["event_name"] = event_name.get("value", "")

            time_dict = event_detail.get("time", {})
            time = time_dict.get("value", 0)
            target_info["start_time"] = time if time else start_time

            app_name = dimensions.get("apm_application_name", "")
            if app_name:
                target_dimensions["app_name"] = app_name
            service_name = dimensions.get("apm_service_name", "")
            if service_name:
                target_dimensions["service_name"] = service_name

            event_detail["target_info"] = target_info
