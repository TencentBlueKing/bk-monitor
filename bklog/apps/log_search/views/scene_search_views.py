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
from bkm_space.utils import space_uid_to_bk_biz_id
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import SCENE_SEARCH
from apps.generic import APIViewSet
from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.drf import BusinessActionPermission
from apps.log_search.constants import (
    ExportFileType,
    ExportStatus,
    ExportType,
    FieldDataTypeEnum,
    MAX_RESULT_WINDOW,
    RESULT_WINDOW_COST_TIME,
    SearchMode,
)
from apps.log_search.decorators import search_history_record
from apps.log_search.exceptions import GetMultiResultFailException
from apps.log_search.handlers.scene_search import AllConditionsBuilder
from apps.log_search.handlers.search.scene_fields_config import (
    SceneFieldsConfigHandler,
    UserSceneCustomConfigHandler,
)
from apps.log_search.models import AsyncTask, UserIndexSetSearchHistory
from apps.log_search.serializers import (
    CreateSceneFieldsConfigSerializer,
    SceneFieldsConfigApplySerializer,
    SceneFieldsConfigDeleteSerializer,
    SceneFieldsConfigListSerializer,
    SceneUserCustomConfigDeleteSerializer,
    SceneUserCustomConfigGetSerializer,
    SceneUserCustomConfigUpsertSerializer,
    UpdateSceneFieldsConfigSerializer,
)
from apps.log_search.utils import create_download_response
from apps.log_unifyquery.constants import FIELD_TYPE_MAP, AggTypeEnum
from apps.log_unifyquery.handler.scene_field import SceneFieldHandler
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.log_unifyquery.handler.scene_terms_aggs import SceneTermsAggsHandler
from apps.utils.drf import list_route
from apps.utils.local import get_request_app_code, get_request_external_username, get_request_username
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

    search_mode = serializers.ChoiceField(
        required=False,
        choices=SearchMode.get_choices(),
        default=SearchMode.UI.value,
    )


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


class SceneDimensionFilterSerializer(serializers.Serializer):
    field_name = serializers.CharField(required=True, help_text="维度 key")
    value = serializers.ListField(child=serializers.CharField(), required=True, help_text="匹配值列表")
    op = serializers.ChoiceField(
        choices=["eq", "ne", "req", "nreq"], default="eq", required=False, help_text="操作符"
    )


class SceneDimensionValuesSerializer(serializers.Serializer):
    """场景化维度值预览（支持级联反选，filters 支持 op）"""

    bk_biz_id = serializers.IntegerField(required=True, help_text="业务 ID")
    scene = serializers.CharField(required=True, help_text="场景标识, e.g. k8s / host / bk_paas")
    dimension_key = serializers.CharField(required=True, help_text="要查询的维度 key, e.g. cluster_id / stream")
    filters = serializers.JSONField(
        required=False,
        default=list,
        help_text="级联筛选：推荐 [{field_name, value, op}]；兼容旧 dict 形式",
    )

    def validate_filters(self, value):
        if not value:
            return []
        if isinstance(value, dict):
            normalized = []
            for f_key, f_values in value.items():
                if isinstance(f_values, str):
                    f_values = [f_values]
                normalized.append({"field_name": f_key, "value": list(f_values), "op": "eq"})
            return normalized
        if not isinstance(value, list):
            raise serializers.ValidationError("filters 必须是 list 或 dict")
        child = SceneDimensionFilterSerializer(data=value, many=True)
        child.is_valid(raise_exception=True)
        return child.validated_data


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


class SceneListSerializer(serializers.Serializer):
    """场景列表查询"""

    bk_biz_id = serializers.IntegerField(required=False, default=None, allow_null=True)


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


def _extract_scene_keys(conds) -> frozenset:
    """Extract `scene` dimension values from table_id_conditions.

    `scene` is the routing classification (a `bkcc__N`-level "which scene")
    while other fields (cluster_id / namespace / ...) are filter dimensions.
    Used by history dedup / filter to classify records by scene only.
    """
    if not conds:
        return frozenset()
    keys = set()
    for and_group in conds:
        for c in and_group or []:
            if c.get("field_name") == "scene":
                for v in c.get("value") or []:
                    keys.add(v)
    return frozenset(keys)


def _extract_routing_dims(conds) -> list:
    """Extract non-scene dimensions from table_id_conditions, normalized for hashing.

    These dimensions (cluster_id / namespace / ...) participate in search-history
    dedup key, so the same keyword under c1 / c2 / c3 stays as distinct records.
    """
    if not conds:
        return []
    dims = []
    for and_group in conds:
        group = []
        for c in and_group or []:
            field = c.get("field_name") or ""
            if not field or field == "scene":
                continue
            group.append({
                "field_name": field,
                "value": list(c.get("value") or []),
                "op": c.get("op", "eq"),
            })
        if group:
            # sort within the AND-group to make order-insensitive
            group.sort(key=lambda x: (x["field_name"], x["op"]))
            dims.append(group)
    dims.sort(key=lambda g: g[0]["field_name"] if g else "")
    return dims


# Scene query_string 拼装逻辑已抽到 apps.utils.scene_lucene，本文件保留 thin wrapper
# 以兼容历史引用。
from apps.utils.scene_lucene import (  # noqa: E402, F401
    build_scene_query_string as _build_scene_query_string,
    format_scene_filter_values as _format_scene_filter_values,
    format_table_id_conditions as _format_table_id_conditions,
)


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------

def _resolve_scene_biz_id(request):
    """解析场景化检索请求的业务 ID。

    场景化检索接口约定只传 space_uid，这里统一解析顺序：
    bk_biz_id（body/query） -> space_uid 反查 bk_biz_id -> 0。
    供灰度开关与业务级权限两个权限类共用，避免重复实现。
    """
    bk_biz_id = (
        request.data.get("bk_biz_id", 0)
        or request.query_params.get("bk_biz_id", 0)
    )
    if bk_biz_id:
        return bk_biz_id
    space_uid = (
        request.data.get("space_uid")
        or request.query_params.get("space_uid")
    )
    if space_uid:
        try:
            return space_uid_to_bk_biz_id(space_uid) or 0
        except Exception:
            return 0
    return 0


class _SceneFeatureTogglePermission(BasePermission):
    """SceneSearchViewSet 灰度开关后端拦截。

    SCENE_SEARCH 开关此前仅作为前端可见性配置透传，后端不做拦截，
    灰度未开的业务仍可直连 API 查询/导出。这里在权限层按业务校验开关，
    与 _SceneViewBusinessPermission 配合（开关在前先拦截）。
    """

    def has_permission(self, request, view):
        biz_id = _resolve_scene_biz_id(request)
        # 解析不到业务 ID 时交由后续业务级权限处理，这里不放行也不误拦。
        if not biz_id:
            return True
        if not FeatureToggleObject.switch(SCENE_SEARCH, int(biz_id)):
            raise PermissionDenied(_("当前业务未开启场景化检索功能"))
        return True


class _SceneViewBusinessPermission(BusinessActionPermission):
    """SceneSearchViewSet 专用业务级权限校验。

    基类 BusinessActionPermission.fetch_biz_id_by_request 只认 bk_biz_id，
    场景化检索接口约定只传 space_uid，会被基类一行 `if not bk_biz_id: return True` 旁路。
    这里覆写解析顺序：bk_biz_id（body/query） -> space_uid -> bk_biz_id 反查，
    其他 BusinessActionPermission 调用点不受影响。
    """

    @classmethod
    def fetch_biz_id_by_request(cls, request):
        return _resolve_scene_biz_id(request)


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------

class SceneSearchViewSet(APIViewSet):
    serializer_class = serializers.Serializer

    def get_permissions(self):
        # 两层校验，开关在前先拦截：
        #   1. _SceneFeatureTogglePermission：按业务校验 SCENE_SEARCH 灰度开关，
        #      灰度未开的业务直接拒绝，避免后端无拦截被直连。
        #   2. _SceneViewBusinessPermission：所有 action 统一走业务级 VIEW_BUSINESS，
        #      会把 space_uid 兜底解析成 bk_biz_id，解决基类只认 bk_biz_id 入参导致的旁路问题。
        # 检索/导出类接口的索引集级 SEARCH_LOG 校验在 ts/raw 返回后按命中结果表执行
        # （见 SceneUnifyQueryHandler.verify_result_table_search_permission）。
        # 后续若细化（如导出 EXPORT_LOG / 模板管理 MANAGE_SCENE_TEMPLATE）时按 action 分组替换即可：
        #   - 检索类：search/fields/chart/agg_field/total/dimension_values/history/aggs_*/field_statistics_*
        #   - 导出类：scene_sample_export/scene_async_export/scene_quick_export/scene_export_history/scene_export_chart_data
        #   - 模板读：list_config/retrieve_config
        #   - 模板写：create_config/update_config/delete_config/apply_config
        #   - 用户偏好：user_custom_config（写入侧由 handler 强制 username=当前用户）
        return [
            _SceneFeatureTogglePermission(),
            _SceneViewBusinessPermission([ActionEnum.VIEW_BUSINESS]),
        ]

    @list_route(methods=["GET"], url_path="scenes")
    def scenes(self, request):
        """
        @api {get} /search/scene/scenes/ 场景化检索-场景列表
        @apiName scene_search_scenes
        @apiGroup 14_SceneSearch
        @apiDescription 返回当前业务可用场景及其维度定义，前端据此渲染场景选择器和维度筛选器，
            并拼装 table_id_conditions。
            - 不传 bk_biz_id 时返回全部场景（向后兼容）；
            - 传 bk_biz_id 时按 IndexSetTag(scene 路由) 主路径判定 + PaaS 兜底，容器/主机始终返回。
        """
        from apps.log_databus.constants import SCENE_SEARCH_DIMENSIONS
        from apps.log_databus.models import CollectorConfig
        from apps.log_search.constants import SceneLabelEnum
        from apps.log_search.models import (
            TAG_TYPE_SCENE,
            IndexSetTag,
            LogIndexSet,
        )
        from bkm_space.utils import bk_biz_id_to_space_uid

        PAAS_APP_CODES = {"bk_paas", "bk_paas3"}

        data = self.params_valid(SceneListSerializer)
        bk_biz_id = data.get("bk_biz_id")

        if bk_biz_id:
            available = {SceneLabelEnum.K8S.value, SceneLabelEnum.HOST.value}
            space_uid = bk_biz_id_to_space_uid(bk_biz_id)
            active_tag_ids = set()
            for tag_ids in LogIndexSet.objects.filter(
                space_uid=space_uid, is_active=True
            ).values_list("tag_ids", flat=True):
                if tag_ids:
                    active_tag_ids.update(int(t) for t in tag_ids if t)
            if active_tag_ids:
                scene_values = IndexSetTag.objects.filter(
                    tag_id__in=active_tag_ids,
                    tag_type=TAG_TYPE_SCENE,
                    name="scene",
                ).values_list("value", flat=True).distinct()
                available.update(v for v in scene_values if v)
            if CollectorConfig.objects.filter(
                bk_biz_id=bk_biz_id, bk_app_code__in=PAAS_APP_CODES
            ).exists():
                available.add(SceneLabelEnum.BK_PAAS.value)
        else:
            available = {v for v, _ in SceneLabelEnum.get_choices()}

        scenes = []
        for value, label in SceneLabelEnum.get_choices():
            if value not in available:
                continue
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
        original_addition = list(data.get("addition") or [])
        original_scene_filter_values = list(data.get("scene_filter_values") or [])
        data = _merge_scene_filters_to_addition(data)
        handler = SceneUnifyQueryHandler(data)
        result = Response(handler.search())
        result.data["history_obj"] = {
            "index_set_id": 0,
            "params": {
                "keyword": data.get("keyword", "*"),
                "addition": original_addition,
                "scene_filter_values": original_scene_filter_values,
                "ip_chooser": data.get("ip_chooser", {}),
                "table_id_conditions": data["table_id_conditions"],
                "space_uid": data["space_uid"],
            },
            "search_type": "default",
            "search_mode": data["search_mode"],
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
    # Scene user custom config (UI 偏好 JSON，与模板系统解耦)
    # ------------------------------------------------------------------

    @list_route(methods=["GET", "POST", "DELETE"], url_path="user_custom_config")
    def user_custom_config(self, request):
        """
        @api {get|post|delete} /search/scene/user_custom_config/ 场景化检索-用户UI偏好
        @apiName scene_user_custom_config
        @apiGroup 14_SceneSearch
        @apiDescription 读/写/删当前用户的场景 UI 偏好（7 字段 camelCase JSON），与模板系统解耦。
        """
        # username 故意只从请求上下文取（外部用户优先），不接受请求体/query 里传入的 username，
        # 防止伪造其他用户的偏好。对应 Serializer 也不暴露 username 字段。
        username = get_request_external_username() or get_request_username()

        if request.method.upper() == "POST":
            data = self.params_valid(SceneUserCustomConfigUpsertSerializer)
            return Response(
                UserSceneCustomConfigHandler.update_or_create(
                    bk_biz_id=data["bk_biz_id"],
                    username=username,
                    scene_id=data["scene_id"],
                    scope=data["scope"],
                    scene_config=data["scene_config"],
                )
            )

        if request.method.upper() == "DELETE":
            data = self.params_valid(SceneUserCustomConfigDeleteSerializer, params=request.query_params)
            return Response(
                UserSceneCustomConfigHandler.delete(
                    bk_biz_id=data["bk_biz_id"],
                    username=username,
                    scene_id=data["scene_id"],
                    scope=data["scope"],
                )
            )

        data = self.params_valid(SceneUserCustomConfigGetSerializer, params=request.query_params)
        return Response(
            UserSceneCustomConfigHandler.get(
                bk_biz_id=data["bk_biz_id"],
                username=username,
                scene_id=data["scene_id"],
                scope=data["scope"],
            )
        )

    @list_route(methods=["POST"], url_path="list_config")
    def list_config(self, request):
        """
        @api {post} /search/scene/list_config/ 场景化检索-字段模板列表
        """
        data = self.params_valid(SceneFieldsConfigListSerializer)
        return Response(
            SceneFieldsConfigHandler(
                bk_biz_id=data["bk_biz_id"],
                scene_id=data["scene_id"],
                scope=data["scope"],
            ).list()
        )

    @list_route(methods=["POST"], url_path="create_config")
    def create_config(self, request):
        """
        @api {post} /search/scene/create_config/ 场景化检索-创建字段模板
        """
        data = self.params_valid(CreateSceneFieldsConfigSerializer)
        return Response(
            SceneFieldsConfigHandler(
                bk_biz_id=data["bk_biz_id"],
                scene_id=data["scene_id"],
                scope=data["scope"],
            ).create_or_update(
                name=data["name"],
                display_fields=data["display_fields"],
                sort_list=data.get("sort_list") or [],
            )
        )

    @list_route(methods=["POST"], url_path="update_config")
    def update_config(self, request):
        """
        @api {post} /search/scene/update_config/ 场景化检索-更新字段模板
        """
        data = self.params_valid(UpdateSceneFieldsConfigSerializer)
        return Response(
            SceneFieldsConfigHandler(
                config_id=data["config_id"],
                bk_biz_id=data["bk_biz_id"],
                scene_id=data["scene_id"],
                scope=data["scope"],
            ).create_or_update(
                name=data["name"],
                display_fields=data["display_fields"],
                sort_list=data.get("sort_list") or [],
            )
        )

    @list_route(methods=["GET"], url_path="retrieve_config")
    def retrieve_config(self, request):
        """
        @api {get} /search/scene/retrieve_config/ 场景化检索-获取字段模板详情
        """
        config_id = request.GET.get("config_id")
        if not config_id:
            raise serializers.ValidationError("config_id 不能为空")
        return Response(SceneFieldsConfigHandler(config_id=int(config_id)).retrieve())

    @list_route(methods=["POST"], url_path="delete_config")
    def delete_config(self, request):
        """
        @api {post} /search/scene/delete_config/ 场景化检索-删除字段模板
        """
        data = self.params_valid(SceneFieldsConfigDeleteSerializer)
        SceneFieldsConfigHandler(config_id=data["config_id"]).delete()
        return Response(None)

    @list_route(methods=["POST"], url_path="config")
    def apply_config(self, request):
        """
        @api {post} /search/scene/config/ 场景化检索-应用字段模板
        """
        data = self.params_valid(SceneFieldsConfigApplySerializer)
        username = get_request_external_username() or get_request_username()
        return Response(SceneFieldsConfigHandler(config_id=data["config_id"]).apply(username))

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
        )

    @list_route(methods=["POST"], url_path="history")
    def scene_search_history(self, request):
        """
        @api {post} /search/scene/history/ 场景化检索-检索历史
        @apiName scene_search_history
        @apiGroup 14_SceneSearch
        @apiDescription 查询场景化检索历史，返回最近 30 条。

        过滤策略：
        - 按 `space_uid` 严格匹配
        - 按 `table_id_conditions` 中 `scene` 字段（场景分类）做交集匹配（宽松）；
          老历史记录如不含 `scene` 字段则视为匹配任意场景，保持向后兼容
        - 其余维度（cluster_id / namespace 等）不参与过滤，只参与下方去重

        去重策略（保留每组最新一条）：
        - keyword / addition / scene_filter_values / ip_chooser 完全一致
        - 且 `table_id_conditions` 中**除 scene 外**的维度筛选完全一致
        """
        data = self.params_valid(SceneSearchHistorySerializer)
        data["table_id_conditions"] = AllConditionsBuilder.from_raw(data["table_id_conditions"])

        username = get_request_external_username() or get_request_username()
        history_qs = UserIndexSetSearchHistory.objects.filter(
            is_deleted=False,
            created_by=username,
            index_set_id=0,
            search_type="default",
        ).order_by("-created_at").values(
            "id", "params", "search_mode", "created_by", "created_at"
        )

        target_space_uid = data.get("space_uid")
        target_scenes = _extract_scene_keys(data.get("table_id_conditions"))

        seen, result = set(), []
        for h in history_qs.iterator():
            params = h["params"] or {}
            if target_space_uid and params.get("space_uid") != target_space_uid:
                continue
            # Filter by `scene` category only — `table_id_conditions`'s other fields
            # (cluster_id / namespace / ...) are dimension filters, not classification.
            # Loose match: any overlap passes; legacy records with no `scene` field
            # are kept (target is over-permissive rather than dropping data silently).
            if target_scenes:
                history_scenes = _extract_scene_keys(params.get("table_id_conditions"))
                if history_scenes and not (target_scenes & history_scenes):
                    continue
            # Dedup key covers the full semantic surface of a scene query so that
            # only truly equivalent searches collapse; `table_id_conditions` itself
            # is excluded (scene is just a routing category) but its non-scene
            # dimension filters are included so c1/c2/c3 stay distinct.
            key = (
                params.get("keyword", ""),
                json.dumps(params.get("addition", []), sort_keys=True),
                json.dumps(params.get("scene_filter_values", []), sort_keys=True),
                json.dumps(params.get("ip_chooser", {}), sort_keys=True),
                json.dumps(
                    _extract_routing_dims(params.get("table_id_conditions")), sort_keys=True
                ),
            )
            if key in seen:
                continue
            seen.add(key)
            h["query_string"] = _build_scene_query_string(params)
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
