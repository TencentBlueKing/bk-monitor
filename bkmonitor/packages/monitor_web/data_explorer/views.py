"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.db.models import Q
from django.http import Http404
from django.utils.translation import gettext as _
from pypinyin import lazy_pinyin
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apm_web.utils import generate_csv_file_download_response
from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.utils.request import get_request
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.data_explorer.event import resources as event_resources
from monitor_web.data_explorer.event.resources import EventTopKResource
from monitor_web.data_explorer.event.serializers import (
    EventDownloadTopKRequestSerializer,
)
from monitor_web.data_explorer.serializers import (
    BulkDeleteFavoriteSerializer,
    BulkUpdateFavoriteSerializer,
    CreateFavoriteGroupSerializer,
    CreateFavoriteSerializer,
    FavoriteGroupSerializer,
    FavoriteSerializer,
    GetFavoriteGroupListSerializer,
    GetFavoriteListSerializer,
    QueryHistoryListQuerySerializer,
    QueryHistorySerializer,
    ShareFavoriteSerializer,
    UpdateFavoriteGroupOrderSerializer,
    UpdateFavoriteGroupSerializer,
    UpdateFavoriteSerializer,
)
from monitor_web.models import FavoriteGroup, QueryHistory


def order_records_by_config(records: list[dict], order: list) -> list[dict]:
    """
    按排序配置对数据进行排序
    """
    if not order:
        return records

    order_dict = {group_id: index for index, group_id in enumerate(order)}
    return sorted(
        records,
        key=lambda x: order_dict.get(x["id"], len(order_dict))
        if x["id"]
        else (len(order_dict) + 1 if x["id"] is None else -1),
    )


def order_records_by_type(records: list[dict], order_type: str) -> list[dict]:
    """
    根据排序类型进行排序
    """
    reverse = False
    key_func = None

    if order_type == "update":
        reverse = True

        def key_func(x):
            return x["update_time"]

    elif order_type in ["asc", "desc"]:
        reverse = order_type == "asc"

        def key_func(x):
            return tuple(lazy_pinyin(x["name"]))

    if not key_func:
        return records

    return sorted(records, key=key_func, reverse=reverse)


class FavoriteGroupViewSet(ModelViewSet):
    """
    数据检索收藏组
    """

    queryset = FavoriteGroup.objects.all()
    serializer_class = FavoriteGroupSerializer

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise ValidationError(_("收藏组({})不存在").format(self.kwargs["pk"]))

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.EXPLORE_METRIC])]

    def get_queryset(self):
        bk_biz_id = self.request.query_params.get("bk_biz_id") or self.request.data.get("bk_biz_id")
        query_type = self.request.query_params.get("type") or self.request.data.get("type")
        return FavoriteGroup.objects.filter(bk_biz_id=bk_biz_id, type=query_type)

    def list(self, request, *args, **kwargs):
        s = GetFavoriteGroupListSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        params = s.validated_data

        queryset = self.get_queryset()

        # 模糊查询
        if params.get("query"):
            queryset = queryset.filter(name__contains=params["query"])

        groups = [
            {"id": 0, "name": _("个人收藏"), "editable": False},
            *FavoriteGroupSerializer(queryset, many=True).data,
            {"id": None, "name": _("未分组"), "editable": False},
        ]
        groups = order_records_by_config(groups, FavoriteGroup.get_group_order(params["bk_biz_id"], params["type"]))
        return Response(groups)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()

        # 解除关联的收藏记录
        QueryHistory.objects.filter(group_id=obj.id).update(group_id=None)

        obj.delete()
        return Response({})

    def create(self, request, *args, **kwargs):
        s = CreateFavoriteGroupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        instance = FavoriteGroupSerializer().create(s.validated_data)
        return Response(FavoriteGroupSerializer(instance).data)

    def update(self, request, *args, **kwargs):
        s = UpdateFavoriteGroupSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        instance = FavoriteGroupSerializer().update(self.get_object(), s.validated_data)
        return Response(FavoriteGroupSerializer(instance).data)

    @action(methods=["POST"], detail=False)
    def update_group_order(self, request, *args, **kwargs):
        """
        更新收藏组排序
        """
        s = UpdateFavoriteGroupOrderSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        params = s.validated_data

        FavoriteGroup.set_group_order(params["bk_biz_id"], params["type"], params["order"])
        return Response(params["order"])


class FavoriteViewSet(ModelViewSet):
    """
    数据检索收藏记录
    """

    queryset = QueryHistory.objects.all()
    serializer_class = FavoriteSerializer

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.EXPLORE_METRIC])]

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise ValidationError(_("收藏记录({})不存在").format(self.kwargs["pk"]))

    def get_queryset(self):
        # 获取当前用户名
        request = get_request(peaceful=True)
        if not request:
            raise ValidationError("username not found")
        username = request.user.username

        # 获取所有公开的或个人私有的收藏记录
        bk_biz_id = self.request.query_params.get("bk_biz_id") or self.request.data.get("bk_biz_id")
        query_type = self.request.query_params.get("type") or self.request.data.get("type")
        return QueryHistory.objects.filter(bk_biz_id=bk_biz_id, type=query_type).filter(
            ~Q(group_id=0) | Q(group_id=0, create_user=username)
        )

    def list(self, request, *args, **kwargs):
        s = GetFavoriteListSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        params = s.validated_data
        queryset = self.get_queryset()

        # 模糊搜索
        if params["query"]:
            queryset = queryset.filter(name__contains=params["query"])

        # 按分组ID查询
        if "group_id" in params:
            if params["group_id"] is None:
                queryset = queryset.filter(group_id__isnull=True)
            else:
                queryset = queryset.filter(group_id=params["group_id"])

        # 替换无效的group_id
        favorites = FavoriteSerializer(queryset, many=True).data
        group_ids = (
            FavoriteGroup.objects.filter(bk_biz_id=params["bk_biz_id"], type=params["type"])
            .values_list("id", flat=True)
            .distinct()
        )
        for favorite in favorites:
            if favorite["group_id"] and favorite["group_id"] not in group_ids:
                favorite["group_id"] = None

        favorites = order_records_by_type(favorites, params["order_type"])

        return Response(favorites)

    @action(methods=["GET"], url_path="list_by_group", detail=False)
    def list_by_group(self, request, *args, **kwargs):
        s = GetFavoriteListSerializer(data=request.query_params)
        s.is_valid(raise_exception=True)
        params = s.validated_data
        queryset = self.get_queryset()

        group_dict = {
            0: {"id": 0, "name": _("个人收藏"), "editable": False, "favorites": []},
            **{
                obj.id: {"id": obj.id, "name": obj.name, "editable": True, "favorites": []}
                for obj in FavoriteGroup.objects.filter(bk_biz_id=params["bk_biz_id"], type=params["type"])
            },
            None: {"id": None, "name": _("未分组"), "editable": False, "favorites": []},
        }

        no_group_favorite_ids = []

        # 分组
        for instance in queryset:
            # 如果分组不存在，则归入未分组
            if instance.group_id not in group_dict:
                instance.group_id = None
                no_group_favorite_ids.append(instance.id)
            group_dict[instance.group_id]["favorites"].append(FavoriteSerializer(instance).data)
        QueryHistory.objects.filter(id__in=no_group_favorite_ids).update(group_id=None)

        # 组内排序
        for group_id, group in group_dict.items():
            group["favorites"] = order_records_by_type(group["favorites"], params["order_type"])

        # 组间排序
        group_order = FavoriteGroup.get_group_order(params["bk_biz_id"], params["type"])
        groups = order_records_by_config(list(group_dict.values()), group_order)
        return Response(groups)

    def create(self, request, *args, **kwargs):
        s = CreateFavoriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        instance = FavoriteSerializer().create(s.validated_data)
        return Response(FavoriteSerializer(instance).data)

    def update(self, request, *args, **kwargs):
        s = UpdateFavoriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        instance = self.get_object()
        instance = FavoriteSerializer().update(instance, s.validated_data)
        return Response(FavoriteSerializer(instance).data)

    @action(methods=["POST"], detail=False)
    def bulk_update(self, request, *args, **kwargs):
        s = BulkUpdateFavoriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        params = s.validated_data

        # 查询存在的收藏记录
        queryset = self.get_queryset()
        instances = {
            instance.id: instance for instance in queryset.filter(id__in=[config["id"] for config in params["configs"]])
        }

        # 批量更新收藏记录
        for config in params["configs"]:
            if config["id"] not in instances:
                continue
            FavoriteSerializer().update(instances[config["id"]], config)
        return Response()

    @action(methods=["POST"], detail=False)
    def bulk_delete(self, request, *args, **kwargs):
        s = BulkDeleteFavoriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        favorite_ids = s.validated_data["ids"]
        self.get_queryset().filter(id__in=favorite_ids).delete()
        return Response()

    @action(methods=["POST"], detail=False)
    def share(self, request, *args, **kwargs):
        s = ShareFavoriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        bk_biz_id = s.validated_data["bk_biz_id"]
        favorite_type = s.validated_data["type"]
        share_bk_biz_ids = s.validated_data["share_bk_biz_ids"]
        duplicate_mode = s.validated_data["duplicate_mode"]
        config = s.validated_data["config"]
        name = s.validated_data["name"]

        # 检查是否有权限分享到目标业务
        permission = Permission()
        for share_bk_biz_id in share_bk_biz_ids:
            if permission.is_allowed_by_biz(bk_biz_id, ActionEnum.EXPLORE_METRIC):
                continue
            raise ValidationError(_("您没有权限分享到业务ID为{bk_biz_id}的业务").format(bk_biz_id=share_bk_biz_id))

        # 检查是否有重复的收藏记录
        duplicate_bk_biz_ids = set(
            QueryHistory.objects.filter(name=name, bk_biz_id__in=share_bk_biz_ids, type=favorite_type).values_list(
                "bk_biz_id", flat=True
            )
        )

        # 分享收藏记录
        for share_bk_biz_id in share_bk_biz_ids:
            if duplicate_mode == "copy" or share_bk_biz_id not in duplicate_bk_biz_ids:
                # 如果是复制模式，需要修改收藏记录名称
                if duplicate_mode == "copy":
                    favorite_name = f"{name}_copy"
                else:
                    favorite_name = name
                config["bk_biz_id"] = share_bk_biz_id
                FavoriteSerializer().create(
                    {
                        "name": favorite_name,
                        "bk_biz_id": share_bk_biz_id,
                        "type": favorite_type,
                        "config": config,
                    }
                )
                continue

            # 如果是跳过模式，跳过重复的收藏记录
            if duplicate_mode == "skip":
                continue

            # 如果是覆盖模式，覆盖重复的收藏记录
            instance = QueryHistory.objects.get(name=name, bk_biz_id=share_bk_biz_id, type=favorite_type)
            FavoriteSerializer().update(instance, {"config": config})

        return Response()


class QueryHistoryViewSet(ModelViewSet):
    """
    旧版的收藏接口，待废弃（2025-05-20，目前只有 trace 仍然在调用）
    """

    queryset = QueryHistory.objects.all().order_by("-id")
    serializer_class = QueryHistorySerializer

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.EXPLORE_METRIC])]

    def list(self, request: Request, *args, **kwargs) -> Response:
        serializer = QueryHistoryListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        bk_biz_id = serializer.validated_data["bk_biz_id"]
        record_type = serializer.validated_data["type"]
        records = self.queryset.filter(bk_biz_id=bk_biz_id, type=record_type)
        if record_type == "trace":
            # trace 的旧版收藏不展示有分组的情况，只展示在旧版创建的收藏
            records = records.filter(group_id=None)

        response_serializer = self.get_serializer(records, many=True)
        return Response(response_serializer.data)


class DataExplorerViewSet(ResourceViewSet):
    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.EXPLORE_METRIC])]

    resource_routes = [
        ResourceRoute("POST", resource.data_explorer.get_graph_query_config, endpoint="get_graph_query_config"),
        ResourceRoute("POST", resource.data_explorer.get_promql_query_config, endpoint="get_promql_query_config"),
        ResourceRoute("POST", resource.data_explorer.get_event_view_config, endpoint="get_event_view_config"),
        ResourceRoute("POST", resource.data_explorer.get_group_by_count, endpoint="get_group_by_count"),
        ResourceRoute("POST", event_resources.EventLogsResource, endpoint="event/logs"),
        ResourceRoute("POST", event_resources.EventTopKResource, endpoint="event/topk"),
        ResourceRoute("POST", event_resources.EventTotalResource, endpoint="event/total"),
        ResourceRoute("POST", event_resources.EventViewConfigResource, endpoint="event/view_config"),
        ResourceRoute("POST", event_resources.EventTimeSeriesResource, endpoint="event/time_series"),
        ResourceRoute("POST", event_resources.EventStatisticsInfoResource, endpoint="event/statistics_info"),
        ResourceRoute("POST", event_resources.EventStatisticsGraphResource, endpoint="event/statistics_graph"),
        ResourceRoute("POST", event_resources.EventTagDetailResource, endpoint="event/tag_detail"),
        ResourceRoute("POST", event_resources.EventGenerateQueryStringResource, endpoint="event/generate_query_string"),
    ]

    @action(methods=["POST"], detail=False, url_path="event/download_topk")
    def download_topk(self, request, *args, **kwargs):
        serializer = EventDownloadTopKRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data: dict[str, Any] = serializer.validated_data
        api_topk_response = EventTopKResource().perform_request(validated_data)
        return generate_csv_file_download_response(
            f"bkmonitor_{validated_data['query_configs'][0]['table']}_{validated_data['fields'][0]}.csv",
            ([item["value"], item["count"], f"{item['proportions']}%"] for item in api_topk_response[0]["list"]),
        )
