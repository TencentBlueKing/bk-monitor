"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from blueapps.utils.request_provider import get_request
from django.db.models import Q, QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models.query_template import QueryTemplate
from bkmonitor.query_template.core import QueryTemplateWrapper
from constants.query_template import GLOBAL_BIZ_ID

from . import serializers


class QueryTemplateViewSet(GenericViewSet):
    queryset = QueryTemplate.objects.all()
    serializer_class = serializers.QueryTemplateModelSerializer

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.EXPLORE_METRIC])]

    def get_serializer_class(self):
        action_serializer_map = {
            "retrieve": serializers.QueryTemplateDetailRequestSerializer,
            "destroy": serializers.QueryTemplateDetailRequestSerializer,
            "create": serializers.QueryTemplateCreateRequestSerializer,
            "update": serializers.QueryTemplateUpdateRequestSerializer,
            "search": serializers.QueryTemplateListRequestSerializer,
            "preview": serializers.QueryTemplatePreviewRequestSerializer,
            "relation": serializers.QueryTemplateRelationRequestSerializer,
            "relations": serializers.QueryTemplateRelationsRequestSerializer,
        }
        return action_serializer_map.get(self.action) or self.serializer_class

    def filter_queryset(self, queryset: QuerySet[QueryTemplate]) -> QuerySet[QueryTemplate]:
        bk_biz_id = int(get_request().biz_id)
        return queryset.filter(Q(bk_biz_id=bk_biz_id) | Q(space_scope__contains=bk_biz_id) | Q(bk_biz_id=GLOBAL_BIZ_ID))

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return Response(self.serializer_class(self.get_object()).data)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.get_object()
        if not self.serializer_class().get_can_delete(instance):
            raise Exception(_("权限不足，无法删除当前模板"))
        instance.delete()
        return Response({})

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.serializer_class().create(serializer.validated_data)
        return Response(self.serializer_class(instance).data)

    def update(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.serializer_class().update(self.get_object(), serializer.validated_data)
        return Response(self.serializer_class(instance).data)

    @staticmethod
    def _search_filter_by_conditions(
        queryset: QuerySet[QueryTemplate], conditions: list[dict[str, Any]]
    ) -> QuerySet[QueryTemplate]:
        fuzzy_match_fields = ["name", "alias", "description", "create_user", "update_user"]
        for cond in conditions:
            q = Q()
            if cond["key"] == "query":
                for v in cond["value"]:
                    for f in fuzzy_match_fields:
                        q |= Q(**{f"{f}__icontains": v})
            else:
                for v in cond["value"]:
                    q |= Q(**{f"{cond['key']}__icontains": v})
            queryset = queryset.filter(q)
        return queryset

    @staticmethod
    def _search_page(queryset: QuerySet[QueryTemplate], page: int, page_size: int) -> QuerySet[QueryTemplate]:
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        return queryset[start_index:end_index]

    @action(methods=["POST"], detail=False)
    def search(self, request: Request, *args, **kwargs) -> Response:
        """查询模板列表"""

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        queryset = self.filter_queryset(self.get_queryset()).order_by(*validated_data["order_by"])
        queryset = self._search_filter_by_conditions(queryset, validated_data["conditions"])
        total = queryset.count()
        queryset = self._search_page(queryset, validated_data["page"], validated_data["page_size"])
        return Response(
            {
                "total": total,
                "list": serializers.QueryTemplateListModelSerializer(queryset, many=True).data,
            }
        )

    @action(methods=["POST"], detail=False)
    def preview(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return Response(
            QueryTemplateWrapper.from_dict(validated_data["query_template"]).render(validated_data["context"])
        )

    @action(methods=["POST"], detail=True)
    def relation(self, request: Request, *args, **kwargs) -> Response:
        """获取单个模板关联资源列表"""

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"total": 0, "list": []})

    @action(methods=["POST"], detail=False)
    def relations(self, request: Request, *args, **kwargs) -> Response:
        """获取列表关联资源数量"""

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            [
                {"query_template_id": query_template_id, "relation_config_count": 0}
                for query_template_id in serializer.validated_data["query_template_ids"]
            ]
        )
