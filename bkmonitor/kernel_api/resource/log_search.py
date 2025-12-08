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


class GetIndexSetListResource(Resource):
    """
    日志查询服务 -- 获取索引集列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data.get("bk_biz_id")
        logger.info("SearchIndexSetListResource: try to search index set list, bk_biz_id->[%s]", bk_biz_id)
        result = api.log_search.search_index_set(bk_biz_id=bk_biz_id)
        return result


class GetIndexSetFieldListResource(Resource):
    """
    日志查询服务 -- 获取索引集字段列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, label="索引集ID")

    def perform_request(self, validated_request_data):
        index_set_id = validated_request_data.get("index_set_id")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        logger.info(
            "GetIndexSetFieldListResource: try to get index set field list, index_set_id->[%s], bk_biz_id->[%s]",
            index_set_id,
            bk_biz_id,
        )
        result = api.log_search.log_search_index_set(index_set_id=index_set_id)
        return result


class SearchLogResource(Resource):
    """
    日志查询服务 -- 日志查询 (用于 AI MCP 请求)
    """

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        index_set_id = validated_request_data.get("index_set_id")
        bk_biz_id = validated_request_data.pop("bk_biz_id", None)
        logger.info(
            "SearchLogResource: try to search log, index_set_id->[%s], bk_biz_id->[%s]", index_set_id, bk_biz_id
        )
        result = api.log_search.es_query_search(**validated_request_data)
        return result
