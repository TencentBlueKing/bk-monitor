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

from rest_framework import serializers

from core.drf_resource import Resource, api
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer

logger = logging.getLogger(__name__)


class QueryMultiResourceRelationResource(Resource):
    """
    查询某时间点资源的对应关联关系 -- 关联关系MCP
    """

    class RequestSerializer(serializers.Serializer):
        class QueryListItemSerializer(serializers.Serializer):
            timestamp = serializers.IntegerField(required=True, label="时间戳（Unix 时间戳，秒级）")
            source_info = serializers.DictField(required=True, label="源资源信息（维度映射）")
            target_type = serializers.CharField(required=False, default="system", label="目标资源类型")
            path_resource = serializers.ListField(
                child=serializers.CharField(), required=False, allow_empty=True, label="关联路径资源类型列表"
            )

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        query_list = serializers.ListField(child=QueryListItemSerializer(), min_length=1, label="查询列表")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        query_list = validated_request_data["query_list"]

        logger.info("QueryMultiResourceRelationResource: try to query relation,bk_biz_id->[%s]", bk_biz_id)

        # 参数格式转换
        source_info_list = []
        for query_item in query_list:
            source_info = query_item["source_info"].copy()
            source_info["data_timestamp"] = query_item["timestamp"]
            source_info["target_type"] = query_item.get("target_type", "system")
            source_info["path_resource"] = query_item.get("path_resource") or ["node"]
            source_info_list.append(source_info)

        return api.unify_query.get_kubernetes_relation(bk_biz_ids=[bk_biz_id], source_info_list=source_info_list)


class QueryMultiResourceRelationRangeResource(Resource):
    """
    查询时间范围内资源的对应关联关系 -- 关联关系MCP
    """

    class RequestSerializer(serializers.Serializer):
        class QueryListItemSerializer(TimeSpanValidationPassThroughSerializer):
            start_time = serializers.IntegerField(required=True, label="开始时间（Unix 时间戳，秒级）")
            end_time = serializers.IntegerField(required=True, label="结束时间（Unix 时间戳，秒级）")
            step = serializers.CharField(required=True, label="查询步长，如 60s")
            source_info = serializers.DictField(required=True, label="源资源信息（维度映射）")
            target_type = serializers.CharField(required=False, default="system", label="目标资源类型")
            path_resource = serializers.ListField(
                child=serializers.CharField(), required=False, allow_empty=True, label="关联路径资源类型列表"
            )

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        query_list = serializers.ListField(child=QueryListItemSerializer(), min_length=1, label="查询列表")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        query_list = validated_request_data["query_list"]

        logger.info("QueryMultiResourceRelationRangeResource: try to query relation,bk_biz_id->[%s]", bk_biz_id)
        return api.unify_query.query_multi_resource_range(bk_biz_ids=[str(bk_biz_id)], query_list=query_list)
