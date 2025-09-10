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

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.EXPLORE_METRIC, ActionEnum.MANAGE_RULE])]

    def get_serializer_class(self):
        action_serializer_map = {
            "retrieve": serializers.StrategyTemplateDetailRequestSerializer,
            "destroy": serializers.StrategyTemplateDeleteRequestSerializer,
            "update": serializers.StrategyTemplateUpdateRequestSerializer,
            "list": serializers.StrategyTemplateListRequestSerializer,
            "preview": serializers.StrategyTemplatePreviewRequestSerializer,
            "apply": serializers.StrategyTemplateApplyRequestSerializer,
            "check": serializers.StrategyTemplateCheckRequestSerializer,
            "clone": serializers.StrategyTemplateCloneRequestSerializer,
            "batch_partial_update": serializers.StrategyTemplateBatchPartialUpdateRequestSerializer,
            "compare": serializers.StrategyTemplateCompareRequestSerializer,
            "alerts": serializers.StrategyTemplateAlertsRequestSerializer,
        }
        return action_serializer_map.get(self.action) or self.serializer_class

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response(mock_data.CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE)
        return Response({})

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({})

    def update(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if validated_data.get("is_mock"):
            return Response(mock_data.CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE)
        return Response({})

    def list(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response(
                {
                    "total": 1,
                    "list": mock_data.STRATEGY_TEMPLATE_LIST,
                }
            )
        return Response({})

    @action(methods=["POST"], detail=True)
    def preview(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response(mock_data.CALLEE_SUCCESS_RATE_STRATEGY_PREVIEW)
        return Response({})

    @action(methods=["POST"], detail=False)
    def apply(self, request: Request, *args, **kwargs) -> Response:
        """模板下发"""

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response(
                {
                    "app_name": "demo",
                    "list": mock_data.STRATEGY_TEMPLATE_APPLY_LIST,
                }
            )
        return Response({})

    @action(methods=["POST"], detail=False)
    def check(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response(
                {
                    "list": mock_data.CHECK_STRATEGY_INSTANCE_LIST,
                }
            )
        return Response({})

    @action(methods=["POST"], detail=True)
    def clone(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response({"id": 2})
        return Response({})

    @action(methods=["POST"], detail=False)
    def batch_partial_update(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response({"ids": [1, 2]})
        return Response({})

    @action(methods=["POST"], detail=True)
    def compare(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response(mock_data.COMPARE_STRATEGY_INSTANCE)
        return Response({})

    @action(methods=["POST"], detail=False)
    def alerts(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_mock"):
            return Response(
                {
                    "list": mock_data.STRATEGY_TEMPLATE_RELATION_ALERTS,
                }
            )
        return Response({})
