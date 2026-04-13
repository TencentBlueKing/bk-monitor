"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

from rest_framework import serializers
from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.log_search.handlers.scene_search import AllConditionsBuilder
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.utils.drf import list_route


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
        required=False, default=dict, help_text="前置级联筛选条件, e.g. {\"stream\": \"stdout\"}"
    )


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
    def search(self, request):
        """
        @api {post} /search/scene/search/ 场景化检索-日志内容
        @apiName scene_search
        @apiGroup 14_SceneSearch
        @apiDescription 通过 table_id_conditions 路由选表，完整支持现有 search 接口的所有查询参数。
        """
        data = self.params_valid(SceneSearchSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
        handler = SceneUnifyQueryHandler(data)
        return Response(handler.search())

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

    @list_route(methods=["POST"], url_path="date_histogram")
    def date_histogram(self, request):
        """
        @api {post} /search/scene/date_histogram/ 场景化检索-趋势图
        @apiName scene_search_date_histogram
        @apiGroup 14_SceneSearch
        @apiDescription 获取场景下日志时间分布趋势图数据。
        """
        data = self.params_valid(SceneDateHistogramSerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])
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
