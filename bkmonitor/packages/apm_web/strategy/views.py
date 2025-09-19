"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.models.strategy import StrategyModel
from bkmonitor.documents.alert import AlertDocument
from constants.alert import EventStatus
from apm_web.models.strategy import StrategyTemplate, StrategyInstance

from . import mock_data, serializers


class StrategyTemplateViewSet(GenericViewSet):
    queryset = None
    serializer_class = None

    def __init__(self, *args, **kwargs):
        self._query_data = None
        super().__init__(*args, **kwargs)

    @property
    def query_data(self) -> dict:
        if self._query_data:
            return self._query_data
        serializer_class = self.serializer_class or self.get_serializer_class()
        original_data = self.request.query_params if self.request.method == "GET" else self.request.data
        serializer_inst = serializer_class(data=original_data)
        serializer_inst.is_valid(raise_exception=True)
        self._query_data = serializer_inst.validated_data
        return self._query_data

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.MANAGE_APM_APPLICATION])]

    def get_serializer_class(self):
        action_serializer_map = {
            "retrieve": serializers.StrategyTemplateDetailRequestSerializer,
            "destroy": serializers.StrategyTemplateDeleteRequestSerializer,
            "update": serializers.StrategyTemplateUpdateRequestSerializer,
            "status": serializers.StrategyTemplateStatusRequestSerializer,
        }
        return action_serializer_map.get(self.action) or self.serializer_class

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

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateSearchRequestSerializer)
    def search(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(
                {
                    "total": 1,
                    "list": mock_data.STRATEGY_TEMPLATE_LIST,
                }
            )
        return Response({})

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

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateStatusRequestSerializer)
    def status(self, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response({"list": []})

        bk_biz_id = self.query_data["bk_biz_id"]
        app_name = self.query_data["app_name"]
        template_ids = self.query_data["ids"]
        need_strategies = self.query_data["need_strategies"]

        # 查询启用的策略模板
        enabled_templates = StrategyTemplate.objects.filter(
            id__in=template_ids, bk_biz_id=bk_biz_id, app_name=app_name, is_enabled=True
        ).values_list("id", flat=True)

        # 查询策略实例，关联启用的策略模板
        strategy_instances = StrategyInstance.objects.filter(
            strategy_template_id__in=enabled_templates, bk_biz_id=bk_biz_id, app_name=app_name
        ).select_related()

        # 获取启用的策略ID
        strategy_ids = []
        template_strategy_map = {}

        for instance in strategy_instances:
            # 检查策略是否启用
            strategy = StrategyModel.objects.get(id=instance.strategy_id)
            if strategy.is_enabled:
                strategy_ids.append(instance.strategy_id)
                if instance.strategy_template_id not in template_strategy_map:
                    template_strategy_map[instance.strategy_template_id] = []
                template_strategy_map[instance.strategy_template_id].append(
                    {"strategy_id": instance.strategy_id, "service_name": instance.service_name}
                )

        # 查询告警数量
        alert_counts = {}
        if strategy_ids:
            search_object = (
                AlertDocument.search(all_indices=True)
                .filter("term", **{"event.bk_biz_id": bk_biz_id})
                .filter("term", status=EventStatus.ABNORMAL)
                .filter("terms", strategy_id=strategy_ids)[:0]
            )
            search_object.aggs.bucket("strategy_id", "terms", field="strategy_id", size=10000)
            search_result = search_object.execute()

            if search_result.aggs:
                for bucket in search_result.aggs.strategy_id.buckets:
                    alert_counts[int(bucket.key)] = bucket.doc_count

        # 构建响应数据
        result_list = []

        for template_id in template_ids:
            if template_id not in template_strategy_map:
                continue

            template_alert_count = 0
            strategies_data = []

            for strategy_info in template_strategy_map[template_id]:
                strategy_id = strategy_info["strategy_id"]
                service_name = strategy_info["service_name"]
                strategy_alert_count = alert_counts.get(strategy_id, 0)
                template_alert_count += strategy_alert_count

                if need_strategies:
                    strategies_data.append(
                        {"strategy_id": strategy_id, "alert_number": strategy_alert_count, "service_name": service_name}
                    )

            template_data = {"id": template_id, "alert_number": template_alert_count}

            if need_strategies:
                template_data["strategies"] = strategies_data

            result_list.append(template_data)

        return Response({"list": result_list})
