"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models.query_template import QueryTemplate
from bkmonitor.query_template.core import QueryTemplateWrapper
from constants.query_template import GLOBAL_BIZ_ID

from . import mock_data, serializers


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

    def filter_queryset(self, queryset):
        bk_biz_id = self.request.query_params.get("bk_biz_id") or self.request.data.get("bk_biz_id")
        if isinstance(bk_biz_id, str) and bk_biz_id.isdigit():
            bk_biz_id = int(bk_biz_id)
        return queryset.filter(Q(bk_biz_id=bk_biz_id) | Q(space_scope__contains=bk_biz_id) | Q(bk_biz_id=GLOBAL_BIZ_ID))

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        query_template_id = int(kwargs[self.lookup_field])
        if validated_data.get("is_mock"):
            if query_template_id == 1:
                response_data = mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_DETAIL
            elif query_template_id == 2:
                response_data = mock_data.CALLEE_P99_QUERY_TEMPLATE_DETAIL
        else:
            instance = self.get_object()
            response_data = self.serializer_class(instance).data
        return Response(response_data)

    def destroy(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.get_object()
        if self.serializer_class().get_can_delete(instance):
            instance.delete()
            return Response({})
        raise Exception("权限不足，无法删除当前模板")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get("is_mock"):
            response_data = mock_data.CALLEE_P99_QUERY_TEMPLATE_DETAIL
        else:
            validated_data.pop("is_mock", None)
            instance = self.serializer_class().create(validated_data)
            response_data = self.serializer_class(instance).data
        return Response(response_data)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get("is_mock"):
            response_data = mock_data.CALLEE_P99_QUERY_TEMPLATE_DETAIL
        else:
            instance = self.get_object()
            instance = self.serializer_class().update(instance, validated_data)
            response_data = self.serializer_class(instance).data
        return Response(response_data)

    @staticmethod
    def _search_filter_by_conditions(queryset, conditions):
        fuzzy_match_fields = ["name", "description", "create_user", "update_user"]
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
    def _search_page(queryset, page, page_size):
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        return queryset[start_index:end_index]

    @action(methods=["POST"], detail=False)
    def search(self, request, *args, **kwargs):
        """查询模板列表"""

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get("is_mock"):
            response_data = {"total": 2, "list": mock_data.QUERY_TEMPLATE_LIST}
        else:
            queryset = self.filter_queryset(self.get_queryset()).order_by(*validated_data.get("order_by", []))
            queryset = self._search_filter_by_conditions(queryset, validated_data.get("conditions", []))
            total = queryset.count()
            queryset = self._search_page(queryset, validated_data.get("page", 1), validated_data.get("page_size", 50))
            response_data = {
                "total": total,
                "list": self.serializer_class(queryset, many=True).data,
            }

        return Response(response_data)

    @action(methods=["POST"], detail=False)
    def preview(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get("is_mock"):
            response_data = mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_PREVIEW
        else:
            response_data = QueryTemplateWrapper.from_dict(validated_data["query_template"]).render(
                validated_data["context"]
            )
        return Response(response_data)

    @action(methods=["POST"], detail=True)
    def relation(self, request, *args, **kwargs):
        """获取单个模板关联资源列表"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get("is_mock"):
            response_data = {"total": 2, "list": mock_data.CALLEE_P99_QUERY_TEMPLATE_RELATION}
        else:
            response_data = {"total": 0, "list": []}

        return Response(response_data)

    @action(methods=["POST"], detail=False)
    def relations(self, request, *args, **kwargs):
        """获取列表关联资源数量"""

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = []
        if validated_data.get("is_mock"):
            response_data = mock_data.QUERY_TEMPLATE_RELATIONS
        else:
            for query_template_id in validated_data.get("query_template_ids", []):
                response_data.append({"query_template_id": query_template_id, "relation_count": 0})
        return Response(response_data)
