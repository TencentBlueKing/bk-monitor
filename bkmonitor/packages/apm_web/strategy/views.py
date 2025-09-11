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
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission

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
    def search(self, request: Request, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(
                {
                    "total": 1,
                    "list": mock_data.STRATEGY_TEMPLATE_LIST,
                }
            )
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplatePreviewRequestSerializer)
    def preview(self, request: Request, *args, **kwargs) -> Response:
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
    def check(self, request: Request, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(
                {
                    "list": mock_data.CHECK_STRATEGY_INSTANCE_LIST,
                }
            )
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateCloneRequestSerializer)
    def clone(self, request: Request, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response({"id": 2})
        return Response({})

    @action(
        methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateBatchPartialUpdateRequestSerializer
    )
    def batch_partial_update(self, request: Request, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response({"ids": [1, 2]})
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateCompareRequestSerializer)
    def compare(self, request: Request, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(mock_data.COMPARE_STRATEGY_INSTANCE)
        return Response({})

    @action(methods=["POST"], detail=False, serializer_class=serializers.StrategyTemplateAlertsRequestSerializer)
    def alerts(self, request: Request, *args, **kwargs) -> Response:
        if self.query_data.get("is_mock"):
            return Response(
                {
                    "list": mock_data.STRATEGY_TEMPLATE_RELATION_ALERTS,
                }
            )
        return Response({})
