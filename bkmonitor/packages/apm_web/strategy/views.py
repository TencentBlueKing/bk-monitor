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

from django.db.models import Q, QuerySet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.serializers import Serializer

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission

from . import mock_data, serializers
from apm_web.models import StrategyTemplate, StrategyInstance


class StrategyTemplateViewSet(GenericViewSet):
    queryset = StrategyTemplate.objects.all()
    serializer_class = serializers.StrategyTemplateModelSerializer

    def __init__(self, *args, **kwargs):
        self._query_data = None
        super().__init__(*args, **kwargs)

    @property
    def query_data(self) -> dict:
        if self._query_data:
            return self._query_data
        original_data = self.request.query_params if self.request.method == "GET" else self.request.data
        serializer_inst = self.get_serializer(data=original_data)
        serializer_inst.is_valid(raise_exception=True)
        self._query_data = serializer_inst.validated_data
        return self._query_data

    def get_permissions(self) -> list[BusinessActionPermission]:
        return [BusinessActionPermission([ActionEnum.MANAGE_APM_APPLICATION])]

    def get_serializer_class(self) -> type[Serializer]:
        action_serializer_map = {
            "retrieve": serializers.StrategyTemplateDetailRequestSerializer,
            "destroy": serializers.StrategyTemplateDeleteRequestSerializer,
            "update": serializers.StrategyTemplateUpdateRequestSerializer,
        }
        return action_serializer_map.get(self.action) or self.serializer_class

    def get_queryset(self) -> QuerySet[StrategyTemplate]:
        queryset = super().get_queryset()
        return queryset.filter(bk_biz_id=self.query_data["bk_biz_id"], app_name=self.query_data["app_name"])

    def retrieve(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(mock_data.CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE)
        return Response({})

    def destroy(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response({})
        return Response({})

    def update(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(mock_data.CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE)
        return Response({})

    def _filter_by_conditions(
        self, queryset: QuerySet[StrategyTemplate], conditions: list[dict[str, Any]]
    ) -> QuerySet[StrategyTemplate]:
        bk_biz_id = self.query_data["bk_biz_id"]
        app_name = self.query_data["app_name"]
        fuzzy_match_fields = ["name"]
        exact_match_fields = ["type", "system", "update_user", "is_enabled", "is_auto_apply"]
        for cond in conditions:
            q = Q()
            field_name = cond["key"]
            if field_name == "query":
                for v in cond["value"]:
                    for f in fuzzy_match_fields:
                        q |= Q(**{f"{f}__icontains": v})
            elif field_name in fuzzy_match_fields:
                for v in cond["value"]:
                    q |= Q(**{f"{field_name}__icontains": v})
            elif field_name in exact_match_fields:
                for v in cond["value"]:
                    q |= Q(**{f"{field_name}__exact": v})
            elif field_name == "applied_service_name":
                strategy_template_ids = StrategyInstance.objects.filter(
                    bk_biz_id=bk_biz_id, app_name=app_name, service_name__in=cond["value"]
                ).values_list("strategy_template_id", flat=True)
                q |= Q(id__in=strategy_template_ids)
            elif field_name == "user_group_id":
                for v in cond["value"]:
                    q |= Q(**{"user_group_ids__contains": v})
            queryset = queryset.filter(q)
        return queryset

    @staticmethod
    def _search_page(queryset: QuerySet[StrategyTemplate], page: int, page_size: int) -> QuerySet[StrategyTemplate]:
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        return queryset[start_index:end_index]

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateSearchRequestSerializer)
    def search(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(
                {
                    "total": 1,
                    "list": mock_data.STRATEGY_TEMPLATE_LIST,
                }
            )
        queryset = self._filter_by_conditions(self.get_queryset(), self.query_data["conditions"])
        total = queryset.count()
        if self.query_data["simple"]:
            strategy_template_list = serializers.StrategyTemplateSimpleSearchModelSerializer(queryset, many=True).data
        else:
            queryset = self._search_page(queryset, self.query_data["page"], self.query_data["page_size"])
            strategy_template_list = serializers.StrategyTemplateSearchModelSerializer(queryset, many=True).data
        return Response(
            {
                "total": total,
                "list": strategy_template_list,
            }
        )

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplatePreviewRequestSerializer)
    def preview(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(mock_data.CALLEE_SUCCESS_RATE_STRATEGY_PREVIEW)
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateApplyRequestSerializer)
    def apply(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(
                {
                    "app_name": "demo",
                    "list": mock_data.STRATEGY_TEMPLATE_APPLY_LIST,
                }
            )
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateCheckRequestSerializer)
    def check(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(
                {
                    "list": mock_data.CHECK_STRATEGY_INSTANCE_LIST,
                }
            )
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateCloneRequestSerializer)
    def clone(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response({"id": 2})
        return Response({})

    @action(
        methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateBatchPartialUpdateRequestSerializer
    )
    def batch_partial_update(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response({"ids": [1, 2]})
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateCompareRequestSerializer)
    def compare(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(mock_data.COMPARE_STRATEGY_INSTANCE)
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateAlertsRequestSerializer)
    def alerts(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(
                {
                    "list": mock_data.STRATEGY_TEMPLATE_RELATION_ALERTS,
                }
            )
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateOptionValuesRequestSerializer)
    def option_values(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(mock_data.STRATEGY_TEMPLATE_OPTION_VALUES)
        return Response({})
