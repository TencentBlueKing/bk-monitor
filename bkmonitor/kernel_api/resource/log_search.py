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
from typing import Any

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


class SearchLogResource(Resource):
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


class SearchIndexSetContextResource(Resource):
    """
    日志查询服务 -- 查询索引集上下文

    用于查询指定日志条目的上下文信息，支持向上或向下滚动查看更多日志。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, label="索引集ID")
        size = serializers.IntegerField(required=False, default=50, label="获取条数")
        zero = serializers.BooleanField(required=True, label="上下文标识")
        begin = serializers.IntegerField(
            required=True,
            label="偏移数",
        )
        dtEventTimeStamp = serializers.CharField(required=True, label="上下文-日志时间")
        serverIp = serializers.CharField(required=True, label="上下文-日志所属IP")
        path = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="上下文-日志路径")
        gseIndex = serializers.CharField(required=True, label="上下文-GSE发包序号")
        iterationIndex = serializers.CharField(
            required=False,
            allow_null=True,
            allow_blank=True,
            label="上下文-GSE包序号",
        )

    def perform_request(self, validated_request_data):
        logger.info(
            "SearchIndexSetContextResource: query context, index_set_id->[%s], bk_biz_id->[%s]",
            validated_request_data.get("index_set_id"),
            validated_request_data.get("bk_biz_id"),
        )

        result = api.log_search.search_index_set_context(**validated_request_data)
        return result


class FieldAnalyzeResource(Resource):
    """
    日志查询服务 -- 字段分析

    支持多种字段分析场景：
    1. Top K 分析：按字段值分组统计，按值排序，限制条数
       示例：{"group_by": true, "order_by": "value", "limit": 20}
    2. 时间序列分析：按字段值分组统计，按时间排序
       示例：{"group_by": true, "order_by": "time"}
    3. 总体统计：整体计数，不分组
       示例：{"group_by": false, "order_by": "time"}
    4. 分布分析：按字段值分组统计，无限制
       示例：{"group_by": true, "order_by": "time", "limit": null}
    """

    # 排序字段映射
    ORDER_BY_MAPPING = {
        "value": ["-_value"],
        "time": ["-dtEventTimeStamp", "-gseIndex", "-iterationIndex"],
    }

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, label="索引集ID")
        field_name = serializers.CharField(required=True, label="字段名称")
        query_string = serializers.CharField(required=False, default="*", label="查询字符串")
        group_by = serializers.BooleanField(required=False, default=True, label="是否按字段分组")
        order_by = serializers.ChoiceField(
            required=False,
            choices=["value", "time"],
            default="time",
            label="排序方式：value-按值排序，time-按时间排序",
        )
        limit = serializers.IntegerField(required=False, default=None, allow_null=True, label="限制返回条数")
        step = serializers.CharField(required=False, default="1h", label="时间步长")
        # 过滤条件，格式：{"field_list": [{"field_name": "xxx", "value": ["xxx"], "op": "eq"}], "condition_list": []}
        conditions = serializers.DictField(required=False, allow_null=True, label="过滤条件")
        start_time = serializers.CharField(required=True, label="开始时间")
        end_time = serializers.CharField(required=True, label="结束时间")

    def _build_aggregation_function(self, field_name: str, group_by: bool) -> list[dict[str, Any]]:
        """构建聚合函数配置"""
        if group_by:
            return [{"method": "count", "dimensions": [field_name]}]
        return [{"method": "count"}]

    def _build_query_item(
        self,
        table_id: str,
        field_name: str,
        query_string: str,
        conditions: dict[str, Any] | None,
        aggregation_function: list[dict[str, Any]],
        limit: int | None = None,
    ) -> dict[str, Any]:
        """构建查询项配置"""
        query_item: dict[str, Any] = {
            "data_source": "bklog",
            "reference_name": "a",
            "dimensions": [],
            "time_field": "time",
            "conditions": conditions or {"field_list": [], "condition_list": []},
            "query_string": query_string,
            "function": aggregation_function,
            "table_id": table_id,
            "field_name": field_name,
        }
        if limit is not None:
            query_item["limit"] = limit
        return query_item

    def perform_request(self, validated_request_data):
        # 提取参数
        bk_biz_id = validated_request_data["bk_biz_id"]
        index_set_id = validated_request_data["index_set_id"]
        field_name = validated_request_data["field_name"]
        query_string = validated_request_data.get("query_string", "*")
        group_by = validated_request_data.get("group_by", True)
        order_by = validated_request_data.get("order_by", "time")
        limit = validated_request_data.get("limit")
        step = validated_request_data.get("step", "1h")
        conditions = validated_request_data.get("conditions")
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]

        logger.info(
            "FieldAnalyzeResource: analyze field, index_set_id->[%s], field_name->[%s], bk_biz_id->[%s], "
            "group_by->[%s], order_by->[%s], limit->[%s]",
            index_set_id,
            field_name,
            bk_biz_id,
            group_by,
            order_by,
            limit,
        )

        # 构建查询参数
        table_id = f"bklog_index_set_{index_set_id}"
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        aggregation_function = self._build_aggregation_function(field_name, group_by)
        query_item = self._build_query_item(table_id, field_name, query_string, conditions, aggregation_function, limit)

        query_params = {
            "query_list": [query_item],
            "metric_merge": "a",
            "order_by": self.ORDER_BY_MAPPING[order_by],
            "step": step,
            "start_time": start_time,
            "end_time": end_time,
            "space_uid": space_uid,
        }

        return api.unify_query.query_reference(**query_params)


class SearchLogClusteringPatternResource(Resource):
    """
    日志查询服务 -- 日志聚类模式查询
    """

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.CharField(required=True, label="索引集ID")
        keyword = serializers.CharField(required=False, default="*", label="搜索关键字")
        start_time = serializers.CharField(required=True, label="开始时间")
        end_time = serializers.CharField(required=True, label="结束时间")
        begin = serializers.IntegerField(required=False, default=0, label="偏移数")
        size = serializers.IntegerField(required=False, default=10, label="返回条数")
        pattern_level = serializers.ChoiceField(
            required=True,
            choices=["01", "03", "05", "07", "09"],
            label="敏感度：01 03 05 07 09",
        )
        show_new_pattern = serializers.BooleanField(required=True, label="只显示新类")

    def perform_request(self, validated_request_data):
        index_set_id = validated_request_data.get("index_set_id")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        logger.info(
            "SearchPatternResource: try to search pattern, index_set_id->[%s], bk_biz_id->[%s]", index_set_id, bk_biz_id
        )

        result = api.log_search.search_pattern(**validated_request_data)
        return result
