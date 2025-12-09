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

from bkm_space.utils import bk_biz_id_to_space_uid
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


class SearchLogV2Resource(Resource):
    """
    日志查询服务 -- 日志查询 (用于 AI MCP 请求)
    """

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, label="索引集ID")
        query_string = serializers.CharField(required=False, default="*", label="查询字符串")
        start_time = serializers.CharField(required=True, label="开始时间")
        end_time = serializers.CharField(required=True, label="结束时间")
        limit = serializers.IntegerField(required=False, default=10, label="返回条数")

    def perform_request(self, validated_request_data):
        index_set_id = validated_request_data.get("index_set_id")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        query_string = validated_request_data.get("query_string", "*")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        limit = validated_request_data.get("limit")

        logger.info(
            "SearchLogResource: try to search log, index_set_id->[%s], bk_biz_id->[%s]", index_set_id, bk_biz_id
        )

        # 构造 unify_query.query_raw 请求参数
        table_id = f"bklog_index_set_{index_set_id}"  # 日志索引集规则
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)  # 业务ID转SPACE_UID，用于构建Headers

        query_params = {
            "query_list": [
                {
                    "data_source": "bklog",
                    "table_id": table_id,
                    "query_string": query_string,
                }
            ],
            "metric_merge": "a",  # 返回引用名为 "a" 的查询结果，便于后续使用,日志侧无需关心
            "start_time": start_time,
            "end_time": end_time,
            "step": "auto",
            "limit": limit,
            "space_uid": space_uid,
        }

        result = api.unify_query.query_raw(**query_params)
        return result
