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

from bkmonitor.documents import AlertDocument
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from constants.alert import EventStatus
from core.drf_resource import resource

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
        return (
            super().get_queryset().filter(bk_biz_id=self.query_data["bk_biz_id"], app_name=self.query_data["app_name"])
        )

    def retrieve(self, *args, **kwargs) -> Response:
        return Response(self.serializer_class(self.get_object()).data)

    def destroy(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response({})
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
        bk_biz_id = self.query_data.get("bk_biz_id")
        app_name = self.query_data.get("app_name")
        template_ids = self.query_data.get("template_ids", [])
        need_strategies = self.query_data.get("need_strategies", False)

        # 查询启用的策略模板
        enabled_templates = self.get_queryset()
        # 查询策略实例，关联启用的策略模板
        strategy_instances = StrategyInstance.objects.filter(
            strategy_template_id__in=enabled_templates, bk_biz_id=bk_biz_id, app_name=app_name
        )
        # 批量查询启用的策略
        applied_strategy_ids = [instance.strategy_id for instance in strategy_instances]
        enabled_strategies_data = resource.strategies.plain_strategy_list_v2(
            bk_biz_id=bk_biz_id, ids=applied_strategy_ids, is_enabled=True
        )
        enabled_strategies_ids = set(strategy["id"] for strategy in enabled_strategies_data)

        # 获取启用的策略ID和模板映射
        enabled_template_strategy_map = {}
        for instance in strategy_instances:
            # 只处理启用的策略实例
            if instance.strategy_id not in enabled_strategies_ids:
                continue
            enabled_template_strategy_map.setdefault(instance.strategy_template_id, []).append(
                {"strategy_id": instance.strategy_id, "service_name": instance.service_name}
            )

        # 查询告警数量
        alert_numbers = {}
        if enabled_strategies_ids:
            search_object = (
                AlertDocument.search(all_indices=True)
                .filter("term", **{"event.bk_biz_id": bk_biz_id})
                .filter("term", status=EventStatus.ABNORMAL)
                .filter("terms", strategy_id=enabled_strategies_ids)[:0]
            )
            search_object.aggs.bucket("strategy_id", "terms", field="strategy_id", size=10000)
            search_result = search_object.execute()

            if search_result.aggs:
                for bucket in search_result.aggs.strategy_id.buckets:
                    alert_numbers[int(bucket.key)] = bucket.doc_count

        # 构建响应数据
        result_list = []
        for template_id in template_ids:
            if template_id not in enabled_template_strategy_map:
                template_alert_info = {"id": template_id, "alert_number": 0}
                if need_strategies:
                    template_alert_info["strategies"] = []
                result_list.append(template_alert_info)
                continue

            template_alert_number = 0
            strategies_data = []
            for strategy_info in enabled_template_strategy_map[template_id]:
                strategy_id = strategy_info["strategy_id"]
                service_name = strategy_info["service_name"]
                alert_number = alert_numbers.get(strategy_id, 0)
                template_alert_number += alert_number

                if need_strategies:
                    strategies_data.append(
                        {"strategy_id": strategy_id, "alert_number": alert_number, "service_name": service_name}
                    )

            template_alert_info = {"id": template_id, "alert_number": template_alert_number}
            if need_strategies:
                template_alert_info["strategies"] = strategies_data
            result_list.append(template_alert_info)

        return Response({"list": result_list})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateOptionValuesRequestSerializer)
    def option_values(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(mock_data.STRATEGY_TEMPLATE_OPTION_VALUES)
        return Response({})
