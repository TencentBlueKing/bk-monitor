"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import csv
import json
import math
from io import BytesIO, TextIOWrapper

import arrow
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.log_search.constants import (
    ExportFileType,
    ExportStatus,
    ExportType,
    FieldDataTypeEnum,
    MAX_RESULT_WINDOW,
    RESULT_WINDOW_COST_TIME,
)
from apps.log_search.decorators import search_history_record
from apps.log_search.exceptions import GetMultiResultFailException
from apps.log_search.handlers.scene_search import AllConditionsBuilder
from apps.log_search.models import AsyncTask, UserIndexSetSearchHistory
from apps.log_search.utils import create_download_response
from apps.log_unifyquery.constants import FIELD_TYPE_MAP, AggTypeEnum
from apps.log_unifyquery.handler.scene_field import SceneFieldHandler
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.log_unifyquery.handler.scene_terms_aggs import SceneTermsAggsHandler
from apps.utils.drf import list_route
from apps.utils.local import get_request_external_username, get_request_username
from apps.utils.thread import MultiExecuteFunc


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

class ConditionFieldSerializer(serializers.Serializer):
    field_name = serializers.CharField(required=True, help_text="Label key, e.g. scene / cluster_id")
    value = serializers.ListField(child=serializers.CharField(), required=True, help_text="Match values list")
    op = serializers.ChoiceField(choices=["eq", "ne", "req", "nreq"], default="eq", help_text="Operator")


class _SceneRouteMixin(serializers.Serializer):
    """场景路由参数，替代 index_set_id。前端统一拼 table_id_conditions。"""

    space_uid = serializers.CharField(required=True, help_text="空间 UID, e.g. bkcc__2")
    bk_biz_id = serializers.IntegerField(required=False, default=None, allow_null=True)

    table_id_conditions = serializers.ListField(
        child=serializers.ListField(child=ConditionFieldSerializer()),
        required=True,
        help_text="AllConditions 二维数组：外层 OR，内层 AND",
    )
    scene_filter_values = serializers.ListField(
        required=False, default=list, allow_empty=True,
        help_text='维度筛选条件，格式与 addition 一致，'
                  'e.g. [{"field": "__ext.io_kubernetes_pod_namespace", "operator": "is", "value": "default"}]',
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("table_id_conditions"):
            raise serializers.ValidationError("table_id_conditions 不能为空")
        return attrs


class SceneSearchSerializer(_SceneRouteMixin):
    """场景化日志检索 — 对标 SearchAttrSerializer，去掉 index_set_id 相关参数"""

    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="*")
    addition = serializers.ListField(allow_empty=True, required=False, default=list)

    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)
    time_range = serializers.CharField(required=False, default=None, allow_blank=True, allow_null=True)
    time_zone = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)

    begin = serializers.IntegerField(required=False, default=0)
    size = serializers.IntegerField(required=False, default=50)

    sort_list = serializers.ListField(
        required=False, allow_null=True, allow_empty=True, default=list,
        child=serializers.ListField(child=serializers.CharField()),
    )
    aggs = serializers.DictField(required=False, default=dict)
    highlight = serializers.DictField(required=False, default=dict)

    ip_chooser = serializers.DictField(default=dict, required=False)

    filter = serializers.ListField(allow_empty=True, required=False, default=list, allow_null=True)

    is_return_doc_id = serializers.BooleanField(required=False, default=False)
    is_desensitize = serializers.BooleanField(required=False, default=True)
    track_total_hits = serializers.BooleanField(required=False, default=True)

    search_after = serializers.ListField(required=False, allow_empty=True, default=list, allow_null=True)
    collapse = serializers.DictField(required=False, default=dict, allow_null=True)


class SceneFieldsSerializer(_SceneRouteMixin):
    """场景化字段列表"""

    start_time = serializers.CharField(required=False, default="", allow_blank=True)
    end_time = serializers.CharField(required=False, default="", allow_blank=True)
    scope = serializers.CharField(required=False, default="default")


class SceneDateHistogramSerializer(_SceneRouteMixin):
    """场景化趋势图"""

    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="*")
    addition = serializers.ListField(allow_empty=True, required=False, default=list)
    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)
    time_range = serializers.CharField(required=False, default=None, allow_blank=True, allow_null=True)
    time_zone = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    interval = serializers.CharField(required=False, default="auto")
    ip_chooser = serializers.DictField(default=dict, required=False)
    filter = serializers.ListField(allow_empty=True, required=False, default=list, allow_null=True)


class SceneAggFieldSerializer(_SceneRouteMixin):
    """场景化字段聚合统计"""

    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="*")
    addition = serializers.ListField(allow_empty=True, required=False, default=list)
    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)
    agg_field = serializers.CharField(required=True, help_text="聚合字段名")
    ip_chooser = serializers.DictField(default=dict, required=False)
    filter = serializers.ListField(allow_empty=True, required=False, default=list, allow_null=True)


class SceneTotalSerializer(_SceneRouteMixin):
    """场景化总数统计"""

    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="*")
    addition = serializers.ListField(allow_empty=True, required=False, default=list)
    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)
    ip_chooser = serializers.DictField(default=dict, required=False)
    filter = serializers.ListField(allow_empty=True, required=False, default=list, allow_null=True)


class SceneDimensionValuesSerializer(serializers.Serializer):
    """场景化维度值预览（支持级联反选）"""

    bk_biz_id = serializers.IntegerField(required=True, help_text="业务 ID")
    scene = serializers.CharField(required=True, help_text="场景标识, e.g. k8s / host / bk_paas")
    dimension_key = serializers.CharField(required=True, help_text="要查询的维度 key, e.g. cluster_id / stream")
    filters = serializers.DictField(
        required=False, default=dict,
        help_text='级联筛选, value 为 str 或 list, e.g. {"stream": ["file","stdout"]}',
    )


# ---------------------------------------------------------------------------
# Field analysis serializers
# ---------------------------------------------------------------------------

class SceneFieldBaseSerializer(_SceneRouteMixin):
    """场景化字段分析基础序列化器 — 对标 QueryFieldBaseSerializer"""

    keyword = serializers.CharField(allow_null=True, allow_blank=True, required=False, default="*")
    addition = serializers.ListField(allow_empty=True, required=False, default=list)

    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)
    time_range = serializers.CharField(required=False, default=None, allow_blank=True, allow_null=True)
    time_zone = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    interval = serializers.CharField(required=False, default="auto", max_length=16)

    agg_field = serializers.CharField(required=False)
    ip_chooser = serializers.DictField(default=dict, required=False)
    filter = serializers.ListField(allow_empty=True, required=False, default=list, allow_null=True)


class SceneFetchTopkListSerializer(SceneFieldBaseSerializer):
    """场景化获取字段topk计数"""

    limit = serializers.IntegerField(required=False, default=5)


class SceneFetchValueListSerializer(SceneFieldBaseSerializer):
    """场景化获取字段值列表"""

    limit = serializers.IntegerField(required=False, default=10)


class SceneFetchStatisticsInfoSerializer(SceneFieldBaseSerializer):
    """场景化获取字段统计信息"""

    field_type = serializers.ChoiceField(required=True, choices=list(FIELD_TYPE_MAP.keys()))


class SceneFetchStatisticsGraphSerializer(SceneFieldBaseSerializer):
    """场景化获取字段统计图表"""

    field_type = serializers.ChoiceField(required=True, choices=list(FIELD_TYPE_MAP.keys()))
    max = serializers.FloatField(required=False)
    min = serializers.FloatField(required=False)
    threshold = serializers.IntegerField(required=False, default=10)
    limit = serializers.IntegerField(required=False, default=5)
    distinct_count = serializers.IntegerField(required=False)


# ---------------------------------------------------------------------------
# Aggs serializers
# ---------------------------------------------------------------------------

class SceneAggsTermsSerializer(_SceneRouteMixin):
    """场景化 terms 聚合 — 对标 AggsTermsSerializer / UnionSearchAggsTermsSerializer"""

    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)
    time_range = serializers.CharField(required=False, default=None, allow_blank=True, allow_null=True)
    keyword = serializers.CharField(required=False, default="*", allow_null=True, allow_blank=True)
    addition = serializers.ListField(allow_empty=True, required=False, default=list)
    fields = serializers.ListField(child=serializers.CharField(), required=True)
    size = serializers.IntegerField(required=False, default=10000)
    ip_chooser = serializers.DictField(default=dict, required=False)
    filter = serializers.ListField(allow_empty=True, required=False, default=list, allow_null=True)


class SceneAggsDateHistogramSerializer(_SceneRouteMixin):
    """场景化 date_histogram 聚合 — 对标 DateHistogramSerializer"""

    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)
    time_range = serializers.CharField(required=False, default=None, allow_blank=True, allow_null=True)
    keyword = serializers.CharField(required=False, default="*", allow_null=True, allow_blank=True)
    addition = serializers.ListField(allow_empty=True, required=False, default=list)
    interval = serializers.CharField(required=False, default="auto", max_length=16)
    group_field = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    ip_chooser = serializers.DictField(default=dict, required=False)
    filter = serializers.ListField(allow_empty=True, required=False, default=list, allow_null=True)


# ---------------------------------------------------------------------------
# Export serializers
# ---------------------------------------------------------------------------

class SceneExportSerializer(_SceneRouteMixin):
    """场景化异步导出 — 对标 SearchExportSerializer"""

    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="*")
    addition = serializers.ListField(allow_empty=True, required=False, default=list)
    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)
    time_range = serializers.CharField(required=False, default=None, allow_blank=True, allow_null=True)
    time_zone = serializers.CharField(default="", allow_null=True, allow_blank=True)

    begin = serializers.IntegerField(required=False, default=0)
    size = serializers.IntegerField(required=False, default=50)

    ip_chooser = serializers.DictField(default=dict, required=False)
    sort_list = serializers.ListField(
        required=False, allow_null=True, allow_empty=True, default=list,
        child=serializers.ListField(child=serializers.CharField()),
    )
    export_fields = serializers.ListField(required=False, default=list)
    is_desensitize = serializers.BooleanField(required=False, default=True)
    file_type = serializers.ChoiceField(
        required=False, choices=ExportFileType.get_choices(), default=ExportFileType.LOG.value
    )


class SceneExportHistorySerializer(_SceneRouteMixin):
    """场景化导出历史"""

    bk_biz_id = serializers.IntegerField(required=True)
    show_all = serializers.BooleanField(required=False, default=False)


class SceneSearchHistorySerializer(_SceneRouteMixin):
    """场景化检索历史"""
    pass


class SceneExportChartDataSerializer(_SceneRouteMixin):
    """场景化导出图表数据"""

    sql = serializers.CharField(required=True)
    keyword = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="*")
    addition = serializers.ListField(allow_empty=True, required=False, default=list)
    start_time = serializers.CharField(required=True)
    end_time = serializers.CharField(required=True)


def _merge_scene_filters_to_addition(data: dict) -> dict:
    """Merge scene_filter_values into addition list.

    scene_filter_values uses the same format as addition:
        [{"field": "xxx", "operator": "is", "value": "yyy"}, ...]
    """
    scene_filters = data.pop("scene_filter_values", None)
    if not scene_filters:
        return data
    addition = data.get("addition") or []
    addition.extend(scene_filters)
    data["addition"] = addition
    return data


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------

class SceneSearchViewSet(APIViewSet):
    serializer_class = serializers.Serializer

    def get_permissions(self):
        return []

    @list_route(methods=["GET"], url_path="scenes")
    def scenes(self, request):
        """
        @api {get} /search/scene/scenes/ 场景化检索-场景列表
        @apiName scene_search_scenes
        @apiGroup 14_SceneSearch
        @apiDescription 返回所有可用场景及其维度定义，前端据此渲染场景选择器和维度筛选器，
            并拼装 table_id_conditions。
        """
        from apps.log_databus.constants import SCENE_SEARCH_DIMENSIONS
        from apps.log_search.constants import SceneLabelEnum

        scenes = []
        for value, label in SceneLabelEnum.get_choices():
            scenes.append({
                "id": value,
                "name": str(label),
                "dimensions": SCENE_SEARCH_DIMENSIONS.get(value, []),
            })
        return Response(scenes)

    @list_route(methods=["POST"], url_path="search")
    @search_history_record
    def search(self, request):
        """
        @api {post} /search/scene/search/ 场景化检索-日志内容
        @apiName scene_search
        @apiGroup 14_SceneSearch
        @apiDescription 通过 table_id_conditions 路由选表，完整支持现有 search 接口的所有查询参数。
        """
        data = self.params_valid(SceneSearchSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        data = _merge_scene_filters_to_addition(data)
        handler = SceneUnifyQueryHandler(data)
        result = Response(handler.search())
        result.data["history_obj"] = {
            "index_set_id": 0,
            "params": {
                "keyword": data.get("keyword", "*"),
                "addition": data.get("addition", []),
                "ip_chooser": data.get("ip_chooser", {}),
                "table_id_conditions": data["table_id_conditions"],
                "space_uid": data["space_uid"],
            },
            "search_type": "default",
            "search_mode": data.get("search_mode", "ui"),
            "from_favorite_id": 0,
        }
        return result

    @list_route(methods=["POST"], url_path="fields")
    def fields(self, request):
        """
        @api {post} /search/scene/fields/ 场景化检索-字段列表
        @apiName scene_search_fields
        @apiGroup 14_SceneSearch
        @apiDescription 获取场景下匹配结果表的聚合字段列表。
        """
        data = self.params_valid(SceneFieldsSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        handler = SceneUnifyQueryHandler(data)
        return Response(handler.fields(scope=data.get("scope", "default")))

    @list_route(methods=["POST"], url_path="chart")
    def chart(self, request):
        """
        @api {post} /search/scene/chart/ 场景化检索-趋势图
        @apiName scene_search_chart
        @apiGroup 14_SceneSearch
        @apiDescription 获取场景下日志时间分布趋势图数据。对标 index_set/$id/chart/。
        """
        data = self.params_valid(SceneDateHistogramSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        data = _merge_scene_filters_to_addition(data)
        handler = SceneUnifyQueryHandler(data)
        return Response(handler.date_histogram(interval=data.get("interval", "auto")))

    @list_route(methods=["POST"], url_path="agg_field")
    def agg_field(self, request):
        """
        @api {post} /search/scene/agg_field/ 场景化检索-字段聚合统计
        @apiName scene_search_agg_field
        @apiGroup 14_SceneSearch
        @apiDescription 获取场景下指定字段的 Top N 聚合统计。
        """
        data = self.params_valid(SceneAggFieldSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        data = _merge_scene_filters_to_addition(data)
        handler = SceneUnifyQueryHandler(data)
        return Response(handler.agg_field(agg_field=data["agg_field"]))

    @list_route(methods=["POST"], url_path="total")
    def total(self, request):
        """
        @api {post} /search/scene/total/ 场景化检索-总数统计
        @apiName scene_search_total
        @apiGroup 14_SceneSearch
        @apiDescription 获取场景下匹配日志的总条数。
        """
        data = self.params_valid(SceneTotalSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        data = _merge_scene_filters_to_addition(data)
        handler = SceneUnifyQueryHandler(data)
        return Response(handler.total())

    @list_route(methods=["POST"], url_path="dimension_values")
    def dimension_values(self, request):
        """
        @api {post} /search/scene/dimension_values/ 场景化检索-维度值预览
        @apiName scene_search_dimension_values
        @apiGroup 14_SceneSearch
        @apiDescription 获取场景下指定维度的可选值列表（支持级联筛选），供前端下拉框使用。
        """
        from apps.log_search.models import IndexSetTag

        data = self.params_valid(SceneDimensionValuesSerializer)
        values = IndexSetTag.get_dimension_values(
            bk_biz_id=data["bk_biz_id"],
            scene=data["scene"],
            dimension_key=data["dimension_key"],
            filters=data.get("filters") or None,
        )
        return Response({"dimension_key": data["dimension_key"], "values": sorted(values)})

    # ------------------------------------------------------------------
    # Aggs endpoints
    # ------------------------------------------------------------------

    @list_route(methods=["POST"], url_path="aggs/terms")
    def aggs_terms(self, request):
        """
        @api {post} /search/scene/aggs/terms/ 场景化检索-多字段terms聚合
        @apiName scene_aggs_terms
        @apiGroup 14_SceneSearch
        @apiDescription 对场景下多个字段进行terms聚合，返回每个字段的Top N值及doc_count。
        """
        data = self.params_valid(SceneAggsTermsSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        data = _merge_scene_filters_to_addition(data)
        handler = SceneTermsAggsHandler(data.get("fields", []), data)
        return Response(handler.terms())

    @list_route(methods=["POST"], url_path="aggs/date_histogram")
    def aggs_date_histogram(self, request):
        """
        @api {post} /search/scene/aggs/date_histogram/ 场景化检索-时间直方图聚合
        @apiName scene_aggs_date_histogram
        @apiGroup 14_SceneSearch
        @apiDescription 按时间维度聚合日志数量，支持按指定字段分组（group_field），返回结构化的时间桶数据。
        """
        data = self.params_valid(SceneAggsDateHistogramSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        data = _merge_scene_filters_to_addition(data)
        handler = SceneUnifyQueryHandler(data)
        return Response(handler.aggs_date_histogram(
            interval=data.get("interval", "auto"),
            group_field=data.get("group_field"),
        ))

    # ------------------------------------------------------------------
    # Field analysis endpoints
    # ------------------------------------------------------------------

    @list_route(methods=["POST"], url_path="field/fetch_distinct_count_list")
    def fetch_distinct_count_list(self, request):
        """
        @api {post} /search/scene/field/fetch_distinct_count_list/ 场景化检索-字段去重计数
        @apiName scene_fetch_distinct_count_list
        @apiGroup 14_SceneSearch
        """
        params = self.params_valid(SceneFieldBaseSerializer)
        params["table_id_conditions"] = AllConditionsBuilder.from_raw(params["table_id_conditions"])
        params = _merge_scene_filters_to_addition(params)

        fields_handler = SceneUnifyQueryHandler(params)
        fields_result = fields_handler.fields()
        fields_list = [
            f for f in fields_result.get("fields", [])
            if f["field_type"] != "text" and f.get("es_doc_values", False)
        ]

        multi_execute_func = MultiExecuteFunc()
        for field in fields_list:
            handler = SceneFieldHandler({"agg_field": field["field_name"], **params})
            multi_execute_func.append(f"distinct_count_{field['field_name']}", handler.get_distinct_count)

        multi_result = multi_execute_func.run(return_exception=True)

        count_list = []
        for field in fields_list:
            field_name = field["field_name"]
            ret = multi_result.get(f"distinct_count_{field_name}")
            if isinstance(ret, Exception):
                raise GetMultiResultFailException(
                    GetMultiResultFailException.MESSAGE.format(field_name=field_name, e=ret)
                )
            count_list.append({"field_name": field_name, "distinct_count": ret})
        return Response(count_list)

    @list_route(methods=["POST"], url_path="field/fetch_topk_list")
    def fetch_topk_list(self, request):
        """
        @api {post} /search/scene/field/fetch_topk_list/ 场景化检索-字段TopK
        @apiName scene_fetch_topk_list
        @apiGroup 14_SceneSearch
        """
        params = self.params_valid(SceneFetchTopkListSerializer)
        params["table_id_conditions"] = AllConditionsBuilder.from_raw(params["table_id_conditions"])
        params = _merge_scene_filters_to_addition(params)
        handler = SceneFieldHandler(params)
        total_count = handler.get_total_count()
        field_count = handler.get_field_count()
        distinct_count = handler.get_distinct_count()
        topk_list = handler.get_topk_list(params["limit"])
        return Response({
            "name": params["agg_field"],
            "columns": ["_value", "_count"],
            "types": ["float", "float"],
            "limit": params["limit"],
            "total_count": total_count,
            "field_count": field_count,
            "distinct_count": distinct_count,
            "values": topk_list,
        })

    @list_route(methods=["POST"], url_path="field/fetch_value_list")
    def fetch_value_list(self, request):
        """
        @api {post} /search/scene/field/fetch_value_list/ 场景化检索-字段值列表
        @apiName scene_fetch_value_list
        @apiGroup 14_SceneSearch
        """
        params = self.params_valid(SceneFetchValueListSerializer)
        params["table_id_conditions"] = AllConditionsBuilder.from_raw(params["table_id_conditions"])
        params = _merge_scene_filters_to_addition(params)
        handler = SceneFieldHandler(params)
        value_list = handler.get_value_list(params["limit"])

        output = BytesIO()
        text_wrapper = TextIOWrapper(output, encoding="utf-8", newline="")
        csv_writer = csv.writer(text_wrapper)
        csv_writer.writerow(["value", "count", "percent"])
        for item in value_list:
            csv_writer.writerow([item[0], item[1], f"{item[2] * 100:.2f}%"])
        text_wrapper.flush()
        text_wrapper.detach()
        field_name = params["agg_field"]
        file_name = f"bk_log_search_scene_{field_name}.csv"
        return create_download_response(output, file_name, "text/csv")

    @list_route(methods=["POST"], url_path="field/statistics/info")
    def fetch_statistics_info(self, request):
        """
        @api {post} /search/scene/field/statistics/info/ 场景化检索-字段统计信息
        @apiName scene_fetch_statistics_info
        @apiGroup 14_SceneSearch
        """
        params = self.params_valid(SceneFetchStatisticsInfoSerializer)
        params["table_id_conditions"] = AllConditionsBuilder.from_raw(params["table_id_conditions"])
        params = _merge_scene_filters_to_addition(params)
        handler = SceneFieldHandler(params)

        total_count = handler.get_total_count()
        field_count = handler.get_field_count()
        distinct_count = handler.get_distinct_count()
        field_percent = round(field_count / total_count, 2) if total_count and field_count else 0

        data = {
            "total_count": total_count,
            "field_count": field_count,
            "distinct_count": distinct_count,
            "field_percent": field_percent,
        }
        if FIELD_TYPE_MAP.get(params["field_type"], "") == FieldDataTypeEnum.INT.value:
            data["value_analysis"] = {
                "max": handler.get_agg_value(AggTypeEnum.MAX.value),
                "min": handler.get_agg_value(AggTypeEnum.MIN.value),
                "avg": handler.get_agg_value(AggTypeEnum.AVG.value),
                "median": handler.get_agg_value(AggTypeEnum.MEDIAN.value),
            }
        return Response(data)

    @list_route(methods=["POST"], url_path="field/statistics/total")
    def fetch_statistics_total(self, request):
        """
        @api {post} /search/scene/field/statistics/total/ 场景化检索-日志总条数
        @apiName scene_fetch_statistics_total
        @apiGroup 14_SceneSearch
        """
        params = self.params_valid(SceneFieldBaseSerializer)
        params["table_id_conditions"] = AllConditionsBuilder.from_raw(params["table_id_conditions"])
        params = _merge_scene_filters_to_addition(params)
        total_count = SceneFieldHandler(params).get_total_count()
        return Response({"total_count": total_count})

    @list_route(methods=["POST"], url_path="field/statistics/graph")
    def fetch_statistics_graph(self, request):
        """
        @api {post} /search/scene/field/statistics/graph/ 场景化检索-字段统计图表
        @apiName scene_fetch_statistics_graph
        @apiGroup 14_SceneSearch
        """
        params = self.params_valid(SceneFetchStatisticsGraphSerializer)
        params["table_id_conditions"] = AllConditionsBuilder.from_raw(params["table_id_conditions"])
        params = _merge_scene_filters_to_addition(params)
        handler = SceneFieldHandler(params)
        if FIELD_TYPE_MAP.get(params["field_type"], "") == FieldDataTypeEnum.INT.value:
            if params["distinct_count"] < params["threshold"]:
                return Response(handler.get_topk_list(params["threshold"]))
            else:
                return Response(handler.get_bucket_data(params["min"], params["max"]))
        else:
            return Response(handler.get_topk_ts_data(params["limit"]))

    # ------------------------------------------------------------------
    # Export endpoints
    # ------------------------------------------------------------------

    @list_route(methods=["POST"], url_path="export/sample")
    def scene_sample_export(self, request):
        """
        @api {post} /search/scene/export/sample/ 场景化检索-取样下载
        @apiName scene_sample_export
        @apiGroup 14_SceneSearch
        @apiDescription 同步流式取样下载，对标 index_set/$id/export/。
        """
        request_user = get_request_external_username() or get_request_username()
        data = self.params_valid(SceneExportSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        data = _merge_scene_filters_to_addition(data)

        handler = SceneUnifyQueryHandler(data)
        result = handler.search(is_export=True)
        result_list = result.get("origin_log_list", [])

        output = BytesIO()
        for item in result_list:
            json_data = json.dumps(item, ensure_ascii=False).encode("utf8")
            output.write(json_data + b"\n")

        file_name = f"bklog_scene_{arrow.now().format('YYYYMMDD_HHmmss')}.log"
        response = create_download_response(output, file_name)

        AsyncTask.objects.create(
            request_param=data,
            scenario_id="scene",
            index_set_id=0,
            result=True,
            completed_at=timezone.now(),
            export_status=ExportStatus.SUCCESS,
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            export_type=ExportType.SYNC,
            bk_biz_id=data.get("bk_biz_id", 0),
            created_by=request_user,
        )
        return response

    @list_route(methods=["POST"], url_path="export/async")
    def scene_async_export(self, request):
        """
        @api {post} /search/scene/export/async/ 场景化检索-全文下载（异步导出）
        @apiName scene_async_export
        @apiGroup 14_SceneSearch
        @apiDescription 异步后台全文导出，对标 index_set/$id/async_export/。
        """
        return self._scene_export(request, is_quick_export=False)

    @list_route(methods=["POST"], url_path="export/quick")
    def scene_quick_export(self, request):
        """
        @api {post} /search/scene/export/quick/ 场景化检索-快速下载
        @apiName scene_quick_export
        @apiGroup 14_SceneSearch
        @apiDescription 异步分片并行快速导出，对标 index_set/$id/quick_export/。
        """
        return self._scene_export(request, is_quick_export=True)

    def _scene_export(self, request, is_quick_export):
        from apps.log_unifyquery.handler.scene_async_export import SceneAsyncExportHandler

        data = self.params_valid(SceneExportSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        data = _merge_scene_filters_to_addition(data)

        handler = SceneAsyncExportHandler(
            bk_biz_id=data["bk_biz_id"],
            search_dict=data,
            export_fields=data["export_fields"],
            export_file_type=data["file_type"],
        )
        task_id, size = handler.async_export(is_quick_export=is_quick_export)
        return Response({
            "task_id": task_id,
            "prompt": f"任务提交成功，预估等待时间{math.ceil(size / MAX_RESULT_WINDOW * RESULT_WINDOW_COST_TIME)}分钟",
        })

    @list_route(methods=["POST"], url_path="export/history")
    def scene_export_history(self, request):
        """
        @api {post} /search/scene/export/history/ 场景化检索-导出历史
        @apiName scene_export_history
        @apiGroup 14_SceneSearch
        """
        from apps.log_unifyquery.handler.scene_async_export import SceneAsyncExportHandler

        data = self.params_valid(SceneExportHistorySerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        return SceneAsyncExportHandler(
            bk_biz_id=data["bk_biz_id"],
            search_dict={},
        ).get_export_history(
            request=request, view=self, show_all=data["show_all"],
            table_id_conditions=data["table_id_conditions"],
            page=data["page"], pagesize=data["pagesize"],
        )

    @list_route(methods=["POST"], url_path="history")
    def scene_search_history(self, request):
        """
        @api {post} /search/scene/history/ 场景化检索-检索历史
        @apiName scene_search_history
        @apiGroup 14_SceneSearch
        @apiDescription 按 space_uid + table_id_conditions 查询场景化检索历史，去重后返回最近 30 条。
        """
        from apps.utils.lucene import generate_query_string

        data = self.params_valid(SceneSearchHistorySerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])

        username = get_request_external_username() or get_request_username()
        history_qs = UserIndexSetSearchHistory.objects.filter(
            is_deleted=False,
            created_by=username,
            index_set_id=0,
            search_type="default",
        )
        if data.get("space_uid"):
            history_qs = history_qs.filter(params__space_uid=data["space_uid"])
        if data.get("table_id_conditions"):
            history_qs = history_qs.filter(params__table_id_conditions=data["table_id_conditions"])

        history_qs = history_qs.order_by("-created_at").values(
            "id", "params", "search_mode", "created_by", "created_at"
        )

        seen, result = [], []
        for h in history_qs.iterator():
            key = (h["params"].get("keyword", ""), json.dumps(h["params"].get("addition", []), sort_keys=True))
            if key not in seen:
                seen.append(key)
                h["query_string"] = generate_query_string(h["params"])
                result.append(h)
                if len(result) >= 30:
                    break
        return Response(result)

    @list_route(methods=["POST"], url_path="export_chart_data")
    def scene_export_chart_data(self, request):
        """
        @api {post} /search/scene/export_chart_data/ 场景化检索-导出图表CSV
        @apiName scene_export_chart_data
        @apiGroup 14_SceneSearch
        """
        params = self.params_valid(SceneExportChartDataSerializer)
        params["table_id_conditions"] = AllConditionsBuilder.from_raw(params["table_id_conditions"])
        params = _merge_scene_filters_to_addition(params)
        handler = SceneUnifyQueryHandler(params)
        file_name = f"bklog_scene_{arrow.now().format('YYYYMMDD_HHmmss')}.csv"
        response = StreamingHttpResponse(
            handler.export_chart_data(),
            content_type="application/octet-stream",
        )
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response
