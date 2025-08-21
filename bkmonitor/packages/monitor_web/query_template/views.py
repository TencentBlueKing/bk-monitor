"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from . import mock_data, serializers


class QueryTemplateViewSet(GenericViewSet):
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

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = {}
        query_template_id = int(kwargs[self.lookup_field])
        if validated_data.get("is_mock"):
            if query_template_id == 1:
                response_data = mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_DETAIL
            elif query_template_id == 2:
                response_data = mock_data.CALLEE_P99_QUERY_TEMPLATE_DETAIL
        return Response(response_data)

    def destroy(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_data = {}
        return Response(response_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = {}
        if validated_data.get("is_mock"):
            response_data = mock_data.CALLEE_P99_QUERY_TEMPLATE_DETAIL
        return Response(response_data)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = {}
        if validated_data.get("is_mock"):
            response_data = mock_data.CALLEE_P99_QUERY_TEMPLATE_DETAIL
        return Response(response_data)

    @action(methods=["POST"], detail=False)
    def search(self, request, *args, **kwargs):
        """查询模板列表"""

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = []
        if validated_data.get("is_mock"):
            response_data = mock_data.QUERY_TEMPLATE_LIST
        return Response(response_data)

    @action(methods=["POST"], detail=False)
    def preview(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = {}
        if validated_data.get("is_mock"):
            response_data = mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_PREVIEW
        return Response(response_data)

    @action(methods=["POST"], detail=True)
    def relation(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = []
        if validated_data.get("is_mock"):
            response_data = mock_data.CALLEE_P99_QUERY_TEMPLATE_RELATION
        return Response(response_data)

    @action(methods=["POST"], detail=False)
    def relations(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        response_data = []
        if validated_data.get("is_mock"):
            response_data = mock_data.QUERY_TEMPLATE_RELATIONS
        return Response(response_data)
