"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from core.drf_resource import Resource
from packages.monitor_web.grafana.resources.event import GetDataSourceConfigResource
from packages.monitor_web.data_explorer.event.resources import EventLogsResource, EventViewConfigResource
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer
from rest_framework import serializers

logger = logging.getLogger(__name__)


class ListEventsResource(Resource):
    """
    事件MCP--事件列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        data_source_label = serializers.CharField(label="数据来源")
        data_type_label = serializers.CharField(label="数据类型")
        return_dimensions = serializers.BooleanField(label="是否返回维度", default=True)

    def perform_request(self, validated_request_data):
        logger.info("ListEventsResource: try to list events,bk_biz_id->[%s]", validated_request_data["bk_biz_id"])
        return GetDataSourceConfigResource().request(validated_request_data)


class GetEventViewConfigResource(Resource):
    """
    事件MCP--事件视图配置
    """

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        data_source_label = serializers.ChoiceField(label="数据来源", choices=["bk_monitor", "custom"])
        data_type_label = serializers.ChoiceField(label="数据类型", choices=["log", "event"])
        table = serializers.CharField(required=True, label="表名")
        start_time = serializers.CharField(required=True, label="开始时间")
        end_time = serializers.CharField(required=True, label="结束时间")

    @staticmethod
    def _build_data_source_config(data: dict) -> dict:
        """构建数据源配置项"""
        config_keys = ["data_source_label", "data_type_label", "table"]
        return {key: data[key] for key in config_keys}

    def perform_request(self, validated_request_data):
        logger.info(
            "GetEventViewConfigResource: try to get event view config,bk_biz_id->[%s]",
            validated_request_data["bk_biz_id"],
        )
        data_source_config = self._build_data_source_config(validated_request_data)
        # 提取顶层参数
        top_level_keys = ["start_time", "end_time", "bk_biz_id"]
        query_params = {
            "data_sources": [data_source_config],
            **{key: validated_request_data[key] for key in top_level_keys},
        }
        return EventViewConfigResource().request(query_params)


class SearchEventLogResource(Resource):
    """
    事件MCP--事件日志查询
    """

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        data_source_label = serializers.ChoiceField(label="数据来源", choices=["bk_monitor", "custom"])
        data_type_label = serializers.ChoiceField(label="数据类型", choices=["log", "event"])
        table = serializers.CharField(required=True, label="表名")
        query_string = serializers.CharField(required=False, default="*", label="查询字符串")
        start_time = serializers.CharField(required=True, label="开始时间")
        end_time = serializers.CharField(required=True, label="结束时间")
        limit = serializers.IntegerField(required=False, default=100, label="限制")
        offset = serializers.IntegerField(required=False, default=0, label="偏移")
        sort = serializers.ListSerializer(
            label="排序字段", required=False, child=serializers.CharField(), default=[], allow_empty=True
        )

    @staticmethod
    def _build_query_config(data: dict) -> dict:
        """构建查询配置项"""
        config_keys = ["data_source_label", "data_type_label", "table", "query_string"]
        return {key: data[key] for key in config_keys}

    def perform_request(self, validated_request_data):
        logger.info(
            "SearchEventLogResource: try to search event log,bk_biz_id->[%s]", validated_request_data["bk_biz_id"]
        )
        query_config = self._build_query_config(validated_request_data)
        # 提取顶层参数
        top_level_keys = ["start_time", "end_time", "bk_biz_id", "limit", "offset", "sort"]
        query_params = {
            "query_configs": [query_config],
            **{key: validated_request_data[key] for key in top_level_keys},
        }
        return EventLogsResource().request(query_params)
