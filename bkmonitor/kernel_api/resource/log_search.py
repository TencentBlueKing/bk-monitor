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

CLUSTERING_FIELD_PREFIX = "__dist"
CLUSTERING_QUERY_FIELD = "__dist_05"


def normalize_timestamp_to_milliseconds(timestamp: int | str) -> str:
    timestamp = int(timestamp)
    if timestamp >= 1_000_000_000_000_000_000:
        timestamp //= 1_000_000
    elif timestamp < 1_000_000_000_000:
        timestamp *= 1000
    return str(timestamp)


class SceneRouteConditionSerializer(serializers.Serializer):
    field_name = serializers.CharField(required=True, label="路由字段名")
    value = serializers.ListField(child=serializers.CharField(), required=True, label="路由字段值")
    op = serializers.ChoiceField(choices=["eq", "ne", "req", "nreq"], required=True, label="匹配操作符")


def get_log_unify_query_table(
    index_set_id: int | str, conditions: dict[str, Any] | None = None, query_string: str | None = None
) -> str:
    """根据查询条件选择日志索引集的普通表或聚类表。"""
    field_list = (conditions or {}).get("field_list") or []
    has_clustering_condition = any(
        isinstance(condition, dict) and str(condition.get("field_name", "")).startswith(CLUSTERING_FIELD_PREFIX)
        for condition in field_list
    )
    suffix = "_clustered" if has_clustering_condition or CLUSTERING_QUERY_FIELD in (query_string or "") else ""
    return f"bklog_index_set_{index_set_id}{suffix}"


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


class ListLogScenesResource(Resource):
    """获取业务可用的日志场景及场景维度定义。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        logger.info("ListLogScenesResource: list log scenes, bk_biz_id->[%s]", bk_biz_id)
        scenes = api.log_search.list_scenes(bk_biz_id=bk_biz_id)
        return {"scenes": scenes}


class ListSceneDimensionValuesResource(Resource):
    """获取场景动态路由维度的合法值列表。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        scene = serializers.CharField(required=True, label="场景标识")
        dimension_key = serializers.CharField(required=True, label="维度字段名")
        filters = serializers.ListField(
            child=SceneRouteConditionSerializer(), required=False, default=list, label="级联筛选条件"
        )

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        scene = validated_request_data["scene"]
        dimension_key = validated_request_data["dimension_key"]
        filters = validated_request_data["filters"]
        logger.info(
            "ListSceneDimensionValuesResource: list dimension values, "
            "bk_biz_id->[%s], scene->[%s], dimension_key->[%s], filter_count->[%s]",
            bk_biz_id,
            scene,
            dimension_key,
            len(filters),
        )
        return api.log_search.scene_dimension_values(
            bk_biz_id=bk_biz_id,
            scene=scene,
            dimension_key=dimension_key,
            filters=filters,
        )


class GetSceneLogFieldsResource(Resource):
    """获取场景路由条件命中结果表的聚合字段信息。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        # 禁止空外层和空 AND 分组，并在 MCP 边界校验条件结构，避免宽泛选表或无效请求。
        table_id_conditions = serializers.ListField(
            child=serializers.ListField(child=SceneRouteConditionSerializer(), allow_empty=False),
            required=True,
            allow_empty=False,
            label="结果表路由条件，外层为 OR，内层为 AND",
        )

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        table_id_conditions = validated_request_data["table_id_conditions"]
        logger.info(
            "GetSceneLogFieldsResource: get scene fields, bk_biz_id->[%s], condition_groups->[%s]",
            bk_biz_id,
            len(table_id_conditions),
        )
        result = api.log_search.scene_fields(
            space_uid=bk_biz_id_to_space_uid(bk_biz_id),
            bk_biz_id=bk_biz_id,
            table_id_conditions=table_id_conditions,
        )
        return {
            "fields": result.get("fields") or [],
            "time_field": result.get("time_field", ""),
        }


class SearchLogResource(Resource):
    """
    日志查询服务 -- 日志查询 (用于 AI MCP 请求)
    """

    class RequestSerializer(TimeSpanValidationPassThroughSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        target_type = serializers.ChoiceField(
            choices=["index_set", "scene"], required=False, default="index_set", label="检索目标类型"
        )
        index_set_id = serializers.IntegerField(required=False, allow_null=True, label="索引集ID")
        # 场景检索的结果表路由条件。禁止空外层和空 AND 分组，避免 [] 或 [[]] 导致宽泛选表。
        table_id_conditions = serializers.ListField(
            child=serializers.ListField(child=SceneRouteConditionSerializer(), allow_empty=False),
            required=False,
            allow_empty=False,
            label="结果表路由条件，外层为 OR，内层为 AND",
        )
        query_string = serializers.CharField(required=False, default="*", label="查询字符串(检索语法)")
        # 结构化过滤条件，与 query_string 可同时使用（AND 关系），适合精确的字段级过滤。
        # 格式：{"field_list": [{"field_name": "level", "op": "eq", "value": ["ERROR", "WARN"]}], "condition_list": ["and"]}
        # field_list: 字段筛选规则列表，op 支持 eq/ne/req(正则) 等；value 为多值列表(默认 OR 关系)。
        # condition_list: 逻辑运算符列表，长度为 field_list.length - 1，例如 ["and", "or"]。
        conditions = serializers.DictField(required=False, allow_null=True, default=None, label="结构化过滤条件")
        # 需要保留的输出字段列表，用于裁剪返回内容、降低返回数据量(避免 LLM 上下文超限)，例如 ["dtEventTimeStamp", "log", "level"]
        keep_columns = serializers.ListField(
            child=serializers.CharField(),
            required=False,
            allow_null=True,
            allow_empty=True,
            default=None,
            label="保留输出字段列表",
        )
        # 排序字段列表，"-" 前缀表示降序，例如 ["-dtEventTimeStamp"] 表示按时间倒序(最新在前)
        order_by = serializers.ListField(
            child=serializers.CharField(),
            required=False,
            allow_null=True,
            allow_empty=True,
            default=None,
            label="排序字段列表",
        )
        start_time = serializers.CharField(required=True, label="开始时间")
        end_time = serializers.CharField(required=True, label="结束时间")
        offset = serializers.IntegerField(required=False, default=0, min_value=0, label="偏移量(分页用)")
        limit = serializers.IntegerField(required=False, default=10, min_value=1, max_value=10000, label="返回条数")

        def validate(self, attrs):
            attrs = super().validate(attrs)
            target_type = attrs.get("target_type", "index_set")
            index_set_id = attrs.get("index_set_id")
            table_id_conditions = attrs.get("table_id_conditions")

            if target_type == "index_set":
                if index_set_id is None:
                    raise serializers.ValidationError(
                        {"index_set_id": "index_set_id is required when target_type is index_set."}
                    )
                return attrs

            if not table_id_conditions:
                raise serializers.ValidationError(
                    {"table_id_conditions": "table_id_conditions is required when target_type is scene."}
                )

            return attrs

    def perform_request(self, validated_request_data):
        if validated_request_data.get("target_type", "index_set") == "scene":
            return self._search_by_scene(validated_request_data)
        return self._search_by_index_set(validated_request_data)

    @staticmethod
    def _search_by_scene(validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        table_id_conditions = validated_request_data["table_id_conditions"]
        offset = validated_request_data.get("offset", 0)
        limit = validated_request_data.get("limit", 10)
        order_by = validated_request_data.get("order_by") or []
        start_time = normalize_timestamp_to_milliseconds(validated_request_data["start_time"])
        end_time = normalize_timestamp_to_milliseconds(validated_request_data["end_time"])
        sort_list = [
            [field_name[1:], "desc"] if field_name.startswith("-") else [field_name, "asc"] for field_name in order_by
        ]

        logger.info(
            "SearchLogResource: search scene logs, bk_biz_id->[%s], condition_groups->[%s], offset->[%s], limit->[%s]",
            bk_biz_id,
            len(table_id_conditions),
            offset,
            limit,
        )
        result = api.log_search.scene_search(
            space_uid=bk_biz_id_to_space_uid(bk_biz_id),
            bk_biz_id=bk_biz_id,
            table_id_conditions=table_id_conditions,
            keyword=validated_request_data.get("query_string") or "*",
            start_time=start_time,
            end_time=end_time,
            begin=offset,
            size=limit,
            sort_list=sort_list,
            record_history=False,
        )
        items = result.get("list") or []
        return {
            "items": items,
            "total": result.get("total", 0),
            "took": result.get("took", 0),
        }

    @staticmethod
    def _search_by_index_set(validated_request_data):
        index_set_id = validated_request_data.get("index_set_id")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        query_string = validated_request_data.get("query_string", "*")
        conditions = validated_request_data.get("conditions")
        keep_columns = validated_request_data.get("keep_columns")
        order_by = validated_request_data.get("order_by")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        offset = validated_request_data.get("offset", 0)
        limit = validated_request_data.get("limit")

        logger.info(
            "SearchLogResource: try to search log, index_set_id->[%s], bk_biz_id->[%s], offset->[%s], limit->[%s]",
            index_set_id,
            bk_biz_id,
            offset,
            limit,
        )

        # 构造 unify_query.query_raw 请求参数
        table_id = get_log_unify_query_table(index_set_id, conditions, query_string)
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)  # 业务ID转SPACE_UID，用于构建Headers

        query_item = {
            "data_source": "bklog",
            "table_id": table_id,
            "query_string": query_string,
        }
        if conditions:
            query_item["conditions"] = conditions
        if keep_columns:
            query_item["keep_columns"] = keep_columns

        query_params = {
            "query_list": [query_item],
            "metric_merge": "a",  # 返回引用名为 "a" 的查询结果，便于后续使用,日志侧无需关心
            "start_time": start_time,
            "end_time": end_time,
            "step": "auto",
            "limit": limit,
            "_from": offset,  # query_raw 内部会转换为 "from"
            "space_uid": space_uid,
        }
        if order_by:
            query_params["order_by"] = order_by

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
        table_id = get_log_unify_query_table(index_set_id, conditions, query_string)
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
        group_by = serializers.ListField(
            child=serializers.CharField(), required=False, default=list, label="聚类模式分组字段"
        )

    def perform_request(self, validated_request_data):
        index_set_id = validated_request_data.get("index_set_id")
        bk_biz_id = validated_request_data.get("bk_biz_id")
        logger.info(
            "SearchPatternResource: try to search pattern, index_set_id->[%s], bk_biz_id->[%s]", index_set_id, bk_biz_id
        )

        result = api.log_search.search_pattern(**validated_request_data)
        return result
