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
from monitor_web.data_explorer.event.constants import EventSource, EventType
from monitor_web.incident.utils import get_chinese_labels_dict, pascal_to_snake
from core.drf_resource import api


class IncidentEventsSearchResource(Resource):
    """
    故障告警指标查询接口
    """

    # 查询配置常量
    DEFAULT_EXPRESSION = "a"
    DEFAULT_AGGREGATION_METHOD = "SUM"
    DEFAULT_INDEX_FIELD = "_index"
    DEFAULT_GROUP_BY_FIELDS = ["type", "source", "event_name"]

    # 特殊值过滤列表
    SPECIAL_FILTER_VALUES = ["", None, "app_name", "apm_service"]

    def __init__(self):
        super().__init__()

    RequestSerializer = EventsSearchSerializer

    EntityTypeDataSourceMapping = {
        EntityType.BcsPod.value: DataSourceLabel.CUSTOM,
        EntityType.APMService.value: DataSourceLabel.BK_APM,
        EntityType.BkNodeHost.value: DataSourceLabel.CUSTOM,
    }

    EntityTypeDataTypeMapping = {
        EntityType.BcsPod: DataTypeLabel.EVENT,
        EntityType.APMService: DataTypeLabel.EVENT,
        EntityType.BkNodeHost: DataTypeLabel.EVENT,
    }

    @classmethod
    def get_table_by_entity_type(cls, entity_type: str, **kwargs) -> str:
        """
        根据实体类型获取对应的table名

        Args:
            entity_type: 实体类型 (BcsPod/APMService/BkNodeHost)
            **kwargs: 额外参数，包含bk_biz_id、cluster_id、bk_data_id等

        Returns:
            str: 数据表名，如果无法确定则返回空字符串
        """
        if entity_type == EntityType.BcsPod:
            # bcs_pod类型的entity type需要拿到bk_data_id
            bk_biz_id = kwargs.get("bk_biz_id", "")
            cluster_infos: list = api.metadata.list_bcs_cluster_info(cluster_ids=[kwargs.get("cluster_id", "")])
            cluster_to_data_id: dict = {
                cluster_info["cluster_id"]: cluster_info["k8s_event_data_id"] for cluster_info in cluster_infos
            }
            bk_data_id = cluster_to_data_id.get(kwargs.get("cluster_id", ""))
            if bk_data_id:
                return f"{bk_biz_id}_bkmonitor_event_{bk_data_id}"

        elif entity_type == EntityType.APMService:
            # apm_service 可以不带table
            return ""

        elif entity_type == EntityType.BkNodeHost:
            return "gse_system_event"
        return ""

    @classmethod
    def get_where_filter_by_dimensions(cls, dimensions: dict) -> list:
        """
        根据维度数据生成Where过滤条件

        Args:
            dimensions: 维度字典，包含各种过滤条件

        Returns:
            list: Where过滤条件列表，每个条件包含field、method、value
        """
        where_filters = []
        for key, value in dimensions.items():
            # 过滤掉app_name和apm_service这些特殊值
            if value in IncidentEventsSearchResource.SPECIAL_FILTER_VALUES:
                continue
            where_filters.append({"field": key, "method": "eq", "value": value, "condition": "and"})
        return where_filters

    def build_base_query_config(
        self, data_source_label: str, data_type_label: str, bk_biz_id: int, start_time: int, end_time: int
    ) -> dict:
        """
        构建基础查询配置

        Args:
            data_source_label: 数据源标签
            data_type_label: 数据类型标签
            bk_biz_id: 业务ID
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            dict: 基础查询配置
        """
        return {
            "expression": self.DEFAULT_EXPRESSION,
            "query_configs": [
                {
                    "data_source_label": data_source_label,
                    "data_type_label": data_type_label,
                    "query_string": "",
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

    @classmethod
    def build_base_response(cls, bk_biz_id: int) -> dict:
        return {
            "bk_biz_id": bk_biz_id,
            "statistics": {
                "event_source": get_chinese_labels_dict(EventSource),
                "event_level": get_chinese_labels_dict(EventType),
            },
            "events": {},
        }

    def apply_dimension_filters(self, time_series_request: dict, dimensions_filter: dict) -> None:
        """
        应用维度过滤条件到查询配置

        Args:
            time_series_request: 时间序列查询请求配置
            dimensions_filter: 维度过滤条件
        """
        if not dimensions_filter:
            return

        # 添加Where过滤条件
        where_filters = self.get_where_filter_by_dimensions(dimensions_filter)
        time_series_request["query_configs"][0]["where"] = where_filters

        # 兼容event_timeseries resource的特殊参数
        app_name = dimensions_filter.get("app_name", "")
        apm_service = dimensions_filter.get("apm_service", "")
        if app_name:
            time_series_request["app_name"] = app_name
        if apm_service:
            time_series_request["apm_service"] = apm_service

    @classmethod
    def build_event_info(cls, dimension: dict) -> dict:
        """
        构建事件基础信息

        Args:
            dimension: 维度数据

        Returns:
            dict: 事件基础信息
        """
        event_name = f"event.{pascal_to_snake(dimension.get('event_name', ''))}"
        return {
            "event_name": event_name,
            "event_alias": event_name,
            "event_source": dimension.get("source", ""),
            "event_level": dimension.get("type", ""),
        }

    def query_entity_events(self, validated_request_data: dict, base_response: dict) -> dict:
        """
        查询Entity类型的事件数据（完整流程）

        Args:
            validated_request_data: 经过验证的请求数据
            base_response: 基础响应数据

        Returns:
            dict: Entity类型事件搜索响应数据
        """
        # 构建查询请求
        time_series_request = self.build_entity_query_request(validated_request_data)

        # 执行查询
        time_series_response = event_resources.EventTimeSeriesResource().perform_request(time_series_request)

        # 格式化响应数据
        return self.format_entity_events_response(time_series_response, base_response)

    def query_edge_events(self, validated_request_data: dict, base_response: dict) -> dict:
        """
        查询Edge类型的事件数据（完整流程）

        Args:
            validated_request_data: 经过验证的请求数据
            base_response: 基础响应数据

        Returns:
            dict: Edge类型事件搜索响应数据
        """
        # TODO: 实现Edge类型的查询逻辑
        # 目前返回基础响应，后续可以根据需求实现具体的Edge查询逻辑
        return base_response

    def build_entity_query_request(self, validated_request_data: dict) -> dict:
        """
        构建Entity类型的查询请求配置

        Args:
            validated_request_data: 经过验证的请求数据

        Returns:
            dict: 时间序列查询请求配置
        """
        # 解析Entity相关参数
        index_info = validated_request_data.get("index_info", {})
        entity_type = index_info.get("entity_type", "")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        dimensions_filter = index_info.get("dimensions", [])

        # 获取数据源映射
        data_source_label = self.EntityTypeDataSourceMapping.get(entity_type, "")
        data_type_label = self.EntityTypeDataTypeMapping.get(entity_type, "")

        # 构建基础查询配置
        time_series_request = self.build_base_query_config(
            data_source_label, data_type_label, bk_biz_id, start_time, end_time
        )

        # 应用维度过滤条件
        self.apply_dimension_filters(time_series_request, dimensions_filter)

        # 根据entity_type生成table
        table = self.get_table_by_entity_type(entity_type, bk_biz_id=bk_biz_id, **dimensions_filter)
        if table:
            time_series_request["query_configs"][0]["table"] = table

        return time_series_request

    def format_entity_events_response(self, time_series_response: dict, base_response: dict) -> dict:
        """
        格式化Entity类型的事件响应数据

        Args:
            time_series_response: 事件时间序列响应数据
            base_response: 基础响应数据

        Returns:
            dict: 格式化后的响应数据
        """
        for series_data in time_series_response.get("series", []):
            dimension = series_data.get("dimension", {})

            # 跳过没有event_name的数据
            if not dimension.get("event_name"):
                continue

            # 构建事件基础信息
            event_info = self.build_event_info(dimension)
            event_name = event_info["event_name"]

            # 更新统计信息
            source = dimension.get("source", "")
            event_level = dimension.get("type", "")
            if event_level in base_response["statistics"]["event_level"]:
                base_response["statistics"]["event_level"][event_level] += 1
            if source in base_response["statistics"]["event_source"]:
                base_response["statistics"]["event_source"][source] += 1

            # 构建序列数据
            series_info = {
                "dimensions": dimension,
                "target": series_data.get("target", ""),
                "metric_field": series_data.get("metric_field", ""),
                "datapoints": [[datapoint[1], datapoint[0]] for datapoint in series_data.get("datapoints", [])],
                "alias": series_data.get("alias", ""),
                "type": series_data.get("type", ""),
                "dimensions_translation": series_data.get("dimensions_translation", {}),
                "unit": series_data.get("unit", ""),
            }

            # 组装最终的事件数据
            base_response["events"][event_name] = {**event_info, "series": [series_info]}

        return base_response

    def perform_request(self, validated_request_data: dict) -> dict:
        """
        执行事件搜索请求，根据IndexType分类处理

        Args:
            validated_request_data: 经过验证的请求数据

        Returns:
            dict: 事件搜索响应数据
        """
        # 解析请求参数
        index_info = validated_request_data.get("index_info", {})
        index_type = index_info.get("index_type", "")
        bk_biz_id = validated_request_data.get("bk_biz_id")

        # 构建基础响应
        base_response = self.build_base_response(bk_biz_id)

        # 根据IndexType分类处理
        if index_type == IndexType.ENTITY.value:
            return self.query_entity_events(validated_request_data, base_response)
        elif index_type == IndexType.EDGE.value:
            return self.query_edge_events(validated_request_data, base_response)
        else:
            # 未知类型，返回基础响应
            return base_response


class IncidentEventsDetailResource(Resource):
    """
    故障告警事件详情查询接口
    """

    def __init__(self):
        super().__init__()

    RequestSerializer = EventDetailSerializer

    def perform_request(self, validated_request_data: dict) -> dict:
        return event_resources.EventTagDetailResource().perform_request(validated_request_data)
