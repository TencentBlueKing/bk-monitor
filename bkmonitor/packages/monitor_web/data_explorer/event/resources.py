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

from typing import Any, Dict, List

from bkmonitor.models import MetricListCache
from core.drf_resource import Resource

from . import serializers
from .constants import (
    DISPLAY_FIELDS,
    ENTITIES,
    EVENT_FIELD_ALIAS,
    INNER_FIELD_TYPE_MAPPINGS,
    TYPE_OPERATION_MAPPINGS,
    EventDataLabelEnum,
    EventDimensionTypeEnum,
)
from .mock_data import (
    API_LOGS_RESPONSE,
    API_TIME_SERIES_RESPONSE,
    API_TOPK_RESPONSE,
    API_TOTAL_RESPONSE,
    API_VIEW_CONFIG_RESPONSE,
)


class EventTimeSeriesResource(Resource):
    RequestSerializer = serializers.EventTimeSeriesRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        # result: Dict[str, Any] = resource.grafana.graph_unify_query(validated_request_data)
        return API_TIME_SERIES_RESPONSE


class EventLogsResource(Resource):
    RequestSerializer = serializers.EventLogsRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        # 系统事件可读性：alarm_backends/service/access/event/records/oom.py
        return API_LOGS_RESPONSE


class EventViewConfigResource(Resource):
    RequestSerializer = serializers.EventViewConfigRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        if validated_request_data.get("is_mock"):
            return API_VIEW_CONFIG_RESPONSE

        data_sources = validated_request_data["data_sources"]
        tables = [data_source["table"] for data_source in data_sources]
        dimensions_queryset = MetricListCache.objects.filter(result_table_id__in=tables).values(
            "dimensions", "result_table_id", "data_label"
        )
        # 维度元数据集
        dimension_metadatas = {}

        # 遍历查询集并聚合数据
        for dimension_metadata in dimensions_queryset:
            dimensions = dimension_metadata['dimensions']
            result_table_id = dimension_metadata['result_table_id']
            result_table_label = dimension_metadata['data_label']

            for dimension in dimensions:
                dimension_name = dimension['id']
                if dimension_name not in dimension_metadatas:
                    dimension_metadatas[dimension_name] = {'result_table_ids': [], 'data_labels': []}
                if result_table_id not in dimension_metadatas[dimension_name]['result_table_ids']:
                    dimension_metadatas[dimension_name]['result_table_ids'].append(result_table_id)
                if result_table_label not in dimension_metadatas[dimension_name]['data_labels']:
                    dimension_metadatas[dimension_name]['data_labels'].append(result_table_label)

        inner_fields = []
        system_event_fields = []
        k8s_event_fields = []
        cicd_event_fields = []

        for dimension_name, result_table_info in dimension_metadatas.items():
            dimension_type = self.get_field_type(dimension_name)
            dimension_alias = self.get_field_alias(dimension_name, result_table_info)
            is_option_enabled = self.is_option_enabled(dimension_name)
            is_dimensions = self.get_is_dimensions(dimension_name)
            supported_operations = self.get_supported_operations(dimension_type)
            field = {
                "name": dimension_name,
                "alias": dimension_alias,
                "type": dimension_type,
                "is_option_enabled": is_option_enabled,
                "is_dimensions": is_dimensions,
                "supported_operations": supported_operations,
            }
            if dimension_name in INNER_FIELD_TYPE_MAPPINGS:
                inner_fields.append(field)
            elif result_table_info["data_labels"][0] == EventDataLabelEnum.SYSTEM_EVENT.value:
                system_event_fields.append(field)
            elif result_table_info["data_labels"][0] == EventDataLabelEnum.K8S_EVENT.value:
                k8s_event_fields.append(field)
            else:
                cicd_event_fields.append(field)

        # 按照内置字段，system_event 字段，k8s_event 字段，cicd_event 字段排序
        fields = [*inner_fields, *system_event_fields, *k8s_event_fields, *cicd_event_fields]
        return {"display_fields": DISPLAY_FIELDS, "entities": ENTITIES, "field": fields}

    @classmethod
    def get_field_alias(cls, field, result_table_info) -> str:
        """
        获取字段别名
        """
        # 先渲染 common
        if EVENT_FIELD_ALIAS["common"].get(field):
            return "{}（{}）".format(EVENT_FIELD_ALIAS["common"].get(field), field)
        if EVENT_FIELD_ALIAS[result_table_info["data_labels"][0]].get(field):
            return "{}（{}）".format(EVENT_FIELD_ALIAS[result_table_info["data_labels"][0]].get(field), field)
        return field

    @classmethod
    def get_is_dimensions(cls, field):
        # 如果是内置字段，不需要补充 dimensions.
        return field not in INNER_FIELD_TYPE_MAPPINGS

    @classmethod
    def get_field_type(cls, field) -> str:
        """ "
        获取字段类型
        """
        # 自定义字段统一返回 keyword
        return INNER_FIELD_TYPE_MAPPINGS.get(field, EventDimensionTypeEnum.KEYWORD.value)

    @classmethod
    def is_option_enabled(cls, dimension_type) -> bool:
        return dimension_type in {EventDimensionTypeEnum.KEYWORD.value, EventDimensionTypeEnum.INTEGER.value}

    @classmethod
    def get_supported_operations(cls, dimension_type) -> List[dict]:
        return TYPE_OPERATION_MAPPINGS[dimension_type]


class EventTopKResource(Resource):
    RequestSerializer = serializers.EventTopKRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return API_TOPK_RESPONSE


class EventTotalResource(Resource):
    RequestSerializer = serializers.EventTotalRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        return API_TOTAL_RESPONSE
