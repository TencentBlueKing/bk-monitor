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
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.generics import get_object_or_404
from rest_framework.serializers import Serializer, ValidationError

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.utils.user import get_global_user

from constants.query_template import GLOBAL_BIZ_ID

from . import mock_data, serializers
from apm_web.models import StrategyTemplate, StrategyInstance
from apm_web.strategy.constants import StrategyTemplateType
from apm_web.strategy.query_template.core import QueryTemplateWrapperFactory
from apm_web.strategy.handler import StrategyTemplateOptionValues, StrategyInstanceOptionValues


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
        return (
            super().get_queryset().filter(bk_biz_id=self.query_data["bk_biz_id"], app_name=self.query_data["app_name"])
        )

    def retrieve(self, *args, **kwargs) -> Response:
        strategy_template_data: dict[str, Any] = self.serializer_class(self.get_object()).data
        query_template_data: dict[str, Any] = strategy_template_data["query_template"]
        qtw = QueryTemplateWrapperFactory.get_wrapper(
            query_template_data.get("bk_biz_id", GLOBAL_BIZ_ID), query_template_data.get("name", "")
        )
        if qtw is not None:
            query_template_data.update(qtw.to_dict())
        return Response(strategy_template_data)

    def destroy(self, *args, **kwargs) -> Response:
        strategy_template_obj: StrategyTemplate = self.get_object()
        if strategy_template_obj.type == StrategyTemplateType.BUILTIN_TEMPLATE.value:
            raise ValidationError(_("内置模板不允许删除"))
        if StrategyInstance.objects.filter(strategy_template_id=strategy_template_obj.id).exists():
            raise ValidationError(_("已下发的模板不允许删除"))
        strategy_template_obj.delete()
        return Response({})

    def update(self, *args, **kwargs) -> Response:
        instance = self.serializer_class().update(self.get_object(), self.query_data)
        return Response(self.serializer_class(instance).data)

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
        # TODO 比较两个模板是否一致
        source_obj = get_object_or_404(self.get_queryset(), id=self.query_data["source_id"])
        edit_data: dict[str, Any] = self.query_data["edit_data"]
        edit_data["bk_biz_id"] = self.query_data["bk_biz_id"]
        edit_data["app_name"] = self.query_data["app_name"]
        edit_data["parent_id"] = source_obj.id
        edit_data["type"] = StrategyTemplateType.APP_TEMPLATE.value
        update_field_names: list[str] = ["code", "root_id", "system", "category", "monitor_type", "query_template"]
        for field_name in update_field_names:
            edit_data[field_name] = getattr(source_obj, field_name)
        return Response({"id": serializers.StrategyTemplateModelSerializer().create(edit_data).id})

    @action(
        methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateBatchPartialUpdateRequestSerializer
    )
    def batch_partial_update(self, *args, **kwargs) -> Response:
        update_user: str | None = get_global_user()
        if not update_user:
            raise ValueError(_("未获取到用户信息"))
        edit_data: dict[str, Any] = self.query_data["edit_data"]
        edit_data["update_user"] = update_user
        edit_data["update_time"] = timezone.now()
        strategy_template_qs = self.get_queryset().filter(id__in=self.query_data["ids"])
        strategy_template_qs.update(**edit_data)
        return Response({"ids": list(strategy_template_qs.values_list("id", flat=True))})

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
        template_fields: list[str] = []
        instance_fields: list[str] = []
        for field_name in self.query_data["fields"]:
            if StrategyTemplateOptionValues.is_matched(field_name):
                template_fields.append(field_name)
            elif StrategyInstanceOptionValues.is_matched(field_name):
                instance_fields.append(field_name)

        strategy_template_qs = self.get_queryset()

        option_values: dict[str, list[dict[str, Any]]] = {}
        if template_fields:
            option_values.update(
                StrategyTemplateOptionValues(strategy_template_qs).get_fields_option_values(template_fields)
            )
        if instance_fields:
            strategy_instance_qs = StrategyInstance.objects.filter(
                bk_biz_id=self.query_data["bk_biz_id"],
                app_name=self.query_data["app_name"],
                strategy_template_id__in=list(strategy_template_qs.values_list("id", flat=True)),
            )
            option_values.update(
                StrategyInstanceOptionValues(strategy_instance_qs).get_fields_option_values(instance_fields)
            )

        return Response(option_values)
